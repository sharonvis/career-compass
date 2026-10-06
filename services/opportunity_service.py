"""Read-only matching of seeded and normalized live opportunities.

Person 4 ingestion contract: write normalized Opportunity rows with non-empty
title/company, nullable location, agreed opportunity_type (internship/entry_level),
a non-seed source and required source_url for live rows, date-or-None deadline,
and is_seeded=False. OpportunitySkill uses an existing catalog skill, level 1–3,
and boolean is_required. Rows without mapped required skills may be stored but
are excluded from rankings. Person 4 owns live deduplication; the suggested
natural key is (source, title, company, location). No schema enforcement here.
"""

from datetime import date
from functools import cmp_to_key

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from database.models import Career, CareerSkillRequirement, Opportunity, OpportunitySkill, User
from services.career_service import CareerNotFoundError, UserNotFoundError, get_user_skill_states
from services.scoring_service import classify_opportunity_match, classify_required_skill_statuses


LEVEL_LABELS = {0: "Not Known", 1: "Beginner", 2: "Intermediate", 3: "Advanced"}
BAND_PRIORITY = {"strong": 0, "good": 1, "stretch": 2, "not_eligible": 3}


class OpportunityNotFoundError(LookupError):
    """The requested opportunity does not exist."""


def _verify_user_and_career(session, user_id, career_id):
    if session.get(User, user_id) is None:
        raise UserNotFoundError(f"User {user_id} was not found")
    if session.get(Career, career_id) is None:
        raise CareerNotFoundError(f"Career {career_id} was not found")


def build_opportunity_skill_state(session: Session, user_id: int, opportunity_id: int) -> dict:
    """Load required and optional skills without depending on a chosen career."""
    with session.no_autoflush:
        if session.get(User, user_id) is None:
            raise UserNotFoundError(f"User {user_id} was not found")
        if session.get(Opportunity, opportunity_id) is None:
            raise OpportunityNotFoundError(f"Opportunity {opportunity_id} was not found")
        requirements = list(session.scalars(
            select(OpportunitySkill).options(joinedload(OpportunitySkill.skill))
            .where(OpportunitySkill.opportunity_id == opportunity_id, OpportunitySkill.required_level > 0)
            .order_by(OpportunitySkill.skill_id)
        ))
        states = get_user_skill_states(session, user_id, [r.skill_id for r in requirements])
        result = {"required_skills": [], "optional_skills": []}
        for requirement in requirements:
            state = states[requirement.skill_id]
            item = dict(skill_id=requirement.skill_id, skill_name=requirement.skill.name,
                        required_level=requirement.required_level, is_required=requirement.is_required,
                        claimed_level=state["claimed_level"], demonstrated_level=state["demonstrated_level"])
            key = "required_skills" if requirement.is_required else "optional_skills"
            result[key].append(item)
        return result


def calculate_career_relevance(career_skill_ids, required_opportunity_skills) -> dict:
    """Return an exact required-skill overlap fraction, without percentages."""
    career_skill_ids = set(career_skill_ids)
    required = [skill for skill in required_opportunity_skills
                if skill["required_level"] > 0 and skill.get("is_required", True)]
    return dict(matched=sum(skill["skill_id"] in career_skill_ids for skill in required), total=len(required))


def _match_reasons(statuses, optional_skills, filters, match_band):
    reasons = []
    for name in sorted(filters):
        if filters[name] is False:
            reasons.append(dict(code="hard_filter_failed", filter=name,
                                text=f"{name.capitalize()} eligibility requirement is not met."))
    if match_band == "not_eligible":
        return reasons
    if not statuses:
        reasons.append(dict(code="no_required_skills", text="No valid required skills are mapped; a match band cannot be determined."))
    for skill in statuses:
        name = skill["skill_name"]
        required = LEVEL_LABELS[skill["required_level"]]
        claimed = LEVEL_LABELS[skill["claimed_level"]]
        if skill["status"] == "gap":
            demonstrated = LEVEL_LABELS[skill["demonstrated_level"]]
            reasons.append(dict(code="demonstrated_gap", skill_name=name,
                                text=f"{name}: demonstrated {demonstrated}; {required} is required."))
        elif skill["status"] == "unverified_ok":
            reasons.append(dict(code="unverified_but_claimed", skill_name=name,
                                text=f"{name}: claimed {claimed} meets the {required} requirement, but remains unverified."))
        elif skill["status"] == "unverified_low":
            reasons.append(dict(code="claimed_below_requirement", skill_name=name,
                                text=f"{name}: unverified claim is {claimed}, below the {required} requirement."))
    if match_band == "strong":
        reasons.append(dict(code="all_required_skills_met", text="Demonstrated levels meet all required skills."))
    missing_optional = [skill["skill_name"] for skill in optional_skills
                        if (skill["demonstrated_level"] if skill["demonstrated_level"] is not None
                            else skill["claimed_level"]) < skill["required_level"]]
    if missing_optional:
        reasons.append(dict(code="optional_skills_missing",
                            text=f"Optional skills below requirement: {', '.join(missing_optional)}. These do not affect the match band."))
    return reasons


def get_opportunity_match(session: Session, user_id: int, career_id: int, opportunity_id: int,
                          hard_filter_results: dict[str, bool] | None = None,
                          today: date | None = None) -> dict:
    """Explain a single match, including expired or unmapped listings."""
    with session.no_autoflush:
        _verify_user_and_career(session, user_id, career_id)
        state = build_opportunity_skill_state(session, user_id, opportunity_id)
        opportunity = session.get(Opportunity, opportunity_id)
        career_skill_ids = session.scalars(select(CareerSkillRequirement.skill_id).where(
            CareerSkillRequirement.career_id == career_id, CareerSkillRequirement.required_level > 0,
            CareerSkillRequirement.importance > 0))
        relevance = calculate_career_relevance(career_skill_ids, state["required_skills"])
        statuses = classify_required_skill_statuses(state["required_skills"])
        filters = {} if hard_filter_results is None else hard_filter_results
        band = classify_opportunity_match(filters, state["required_skills"]) if statuses else None
        current_date = date.today() if today is None else today
        return dict(
            opportunity_id=opportunity.id, title=opportunity.title, company=opportunity.company,
            location=opportunity.location, opportunity_type=opportunity.opportunity_type,
            source=opportunity.source, source_url=opportunity.source_url, deadline=opportunity.deadline,
            is_seeded=opportunity.is_seeded, match_band=band, career_relevance=relevance,
            eligibility_checked=hard_filter_results is not None,
            is_expired=opportunity.deadline is not None and opportunity.deadline < current_date,
            **state, reasons=_match_reasons(statuses, state["optional_skills"], filters, band),
        )


def _compare_matches(left, right):
    band_difference = BAND_PRIORITY[left["match_band"]] - BAND_PRIORITY[right["match_band"]]
    if band_difference:
        return band_difference
    a, b = left["career_relevance"], right["career_relevance"]
    cross_difference = a["matched"] * b["total"] - b["matched"] * a["total"]
    if cross_difference:
        return -1 if cross_difference > 0 else 1
    def remaining_key(match):
        statuses = classify_required_skill_statuses(match["required_skills"])
        unmet = sum(skill["status"] in {"gap", "unverified_low"} for skill in statuses)
        deadline = match["deadline"]
        return (unmet, deadline is None, deadline or date.max, match["opportunity_id"])
    left_key, right_key = remaining_key(left), remaining_key(right)
    return (left_key > right_key) - (left_key < right_key)


def get_ranked_opportunities(session: Session, user_id: int, career_id: int,
                             limit: int | None = None,
                             hard_filters_by_opportunity: dict[int, dict[str, bool]] | None = None,
                             today: date | None = None) -> list[dict]:
    """Rank non-expired relevant listings using exact fractions and skill bands."""
    if limit is not None and limit < 0:
        raise ValueError("limit must not be negative")
    with session.no_autoflush:
        _verify_user_and_career(session, user_id, career_id)
        if limit == 0:
            return []
        filters = {} if hard_filters_by_opportunity is None else hard_filters_by_opportunity
        current_date = date.today() if today is None else today
        matches = []
        for opportunity_id in session.scalars(select(Opportunity.id).order_by(Opportunity.id)):
            match = get_opportunity_match(session, user_id, career_id, opportunity_id,
                                          hard_filter_results=filters.get(opportunity_id), today=current_date)
            relevance = match["career_relevance"]
            if (not match["is_expired"] and match["match_band"] is not None
                    and relevance["total"] > 0
                    and relevance["matched"] * 5 >= relevance["total"] * 4):
                matches.append(match)
        matches.sort(key=cmp_to_key(_compare_matches))
        return matches if limit is None else matches[:limit]
