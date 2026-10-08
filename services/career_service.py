"""Read database career state and delegate all scoring to pure helpers."""

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from database.models import (
    AssessmentAttempt, Career, CareerSkillRequirement, Skill, SkillPrerequisite,
    User, UserSkillClaim,
)
from services.scoring_service import (
    are_prerequisites_satisfied, calculate_assessment_coverage,
    calculate_career_readiness, calculate_confirmed_skill_gap,
    list_confirmed_gaps, select_next_action,
)


ASSESSABLE_SKILL_NAMES = {"SQL", "Statistics"}
STABLE_PRIORITY = {
    "Python": 1,
    "SQL": 2,
    "Statistics": 3,
    "Machine Learning Fundamentals": 4,
    "Pandas/Data Handling": 5,
    "Git": 6,
    "Data Structures & Algorithms": 7,
    "Object-Oriented Programming": 8,
    "Excel": 9,
    "Data Visualization": 10,
}


class UserNotFoundError(LookupError):
    """The requested user does not exist."""


class CareerNotFoundError(LookupError):
    """The requested career does not exist."""


def get_latest_demonstrated_level(
    session: Session, user_id: int, skill_id: int,
) -> int | None:
    """Use the latest completed attempt, even when an older score is higher."""
    with session.no_autoflush:
        return session.scalar(
            select(AssessmentAttempt.resulting_level)
            .where(AssessmentAttempt.user_id == user_id,
                   AssessmentAttempt.skill_id == skill_id,
                   AssessmentAttempt.status == "completed")
            .order_by(AssessmentAttempt.completed_at.desc(), AssessmentAttempt.id.desc())
            .limit(1)
        )


def get_user_skill_states(session: Session, user_id: int, skill_ids: list[int]) -> dict[int, dict]:
    """Read claims and latest completed evidence for requested catalog skills.

    Unknown skill IDs are omitted; duplicate requested IDs produce one entry.
    """
    with session.no_autoflush:
        if session.get(User, user_id) is None:
            raise UserNotFoundError(f"User {user_id} was not found")
        skills = list(session.scalars(select(Skill).where(Skill.id.in_(skill_ids)).order_by(Skill.id)))
        claims = dict(session.execute(
            select(UserSkillClaim.skill_id, UserSkillClaim.claimed_level)
            .where(UserSkillClaim.user_id == user_id, UserSkillClaim.skill_id.in_(skill_ids))
        ).all())
        states = {skill.id: dict(skill_id=skill.id, name=skill.name,
                                 claimed_level=claims.get(skill.id, 0),
                                 demonstrated_level=None, latest_attempt_id=None) for skill in skills}
        for skill_id, level, attempt_id in session.execute(
            select(AssessmentAttempt.skill_id, AssessmentAttempt.resulting_level, AssessmentAttempt.id)
            .where(AssessmentAttempt.user_id == user_id, AssessmentAttempt.skill_id.in_(skill_ids),
                   AssessmentAttempt.status == "completed")
            .order_by(AssessmentAttempt.completed_at.desc(), AssessmentAttempt.id.desc())
        ):
            if skill_id in states and states[skill_id]["latest_attempt_id"] is None:
                states[skill_id]["demonstrated_level"] = level
                states[skill_id]["latest_attempt_id"] = attempt_id
        return states


def build_career_skill_state(
    session: Session, user_id: int, career_id: int,
) -> list[dict]:
    """Build scoring inputs without flushing or changing database rows."""
    with session.no_autoflush:
        if session.get(User, user_id) is None:
            raise UserNotFoundError(f"User {user_id} was not found")
        if session.get(Career, career_id) is None:
            raise CareerNotFoundError(f"Career {career_id} was not found")

        requirements = list(session.scalars(
            select(CareerSkillRequirement)
            .options(joinedload(CareerSkillRequirement.skill))
            .where(CareerSkillRequirement.career_id == career_id,
                   CareerSkillRequirement.required_level > 0,
                   CareerSkillRequirement.importance > 0)
            .order_by(CareerSkillRequirement.id)
        ))
        if not requirements:
            raise ValueError(f"Career {career_id} has no valid skill requirements")

        skill_ids = [requirement.skill_id for requirement in requirements]
        user_states = get_user_skill_states(session, user_id, skill_ids)

        prerequisites = {skill_id: [] for skill_id in skill_ids}
        for prerequisite in session.scalars(
            select(SkillPrerequisite)
            .options(joinedload(SkillPrerequisite.prerequisite_skill))
            .where(SkillPrerequisite.skill_id.in_(skill_ids))
            .order_by(SkillPrerequisite.id)
        ):
            if prerequisite.minimum_level > 0 and prerequisite.prerequisite_skill_id not in skill_ids:
                raise ValueError(
                    "A prerequisite skill is outside the valid career requirements; "
                    "the current select_next_action API cannot resolve it"
                )
            prerequisites[prerequisite.skill_id].append({
                "skill_name": prerequisite.prerequisite_skill.name,
                "minimum_level": prerequisite.minimum_level,
            })

        skills = [{
            "skill_id": requirement.skill_id,
            "name": requirement.skill.name,
            "required_level": requirement.required_level,
            "importance": requirement.importance,
            "claimed_level": user_states[requirement.skill_id]["claimed_level"],
            "demonstrated_level": user_states[requirement.skill_id]["demonstrated_level"],
            "latest_attempt_id": user_states[requirement.skill_id]["latest_attempt_id"],
            "assessable": requirement.skill.name in ASSESSABLE_SKILL_NAMES,
            "stable_priority": STABLE_PRIORITY.get(requirement.skill.name, float("inf")),
            "prerequisites": prerequisites[requirement.skill_id],
        } for requirement in requirements]
        return sorted(skills, key=lambda skill: skill["stable_priority"])


def get_user_career_summary(
    session: Session, user_id: int, career_id: int,
) -> dict:
    """Return readiness, assessed gaps and next action for the selected career."""
    with session.no_autoflush:
        skills = build_career_skill_state(session, user_id, career_id)
        claimed_skills = [dict(skill, demonstrated_level=None) for skill in skills]
        demonstrated = {skill["name"]: skill["demonstrated_level"] for skill in skills}
        enriched_skills = [dict(
            skill,
            gap=calculate_confirmed_skill_gap(skill["required_level"], skill["demonstrated_level"]),
            prerequisites_met=are_prerequisites_satisfied(skill["prerequisites"], demonstrated),
        ) for skill in skills]
        return {
            "career_id": career_id,
            "career_name": session.get(Career, career_id).name,
            "claimed_readiness": calculate_career_readiness(claimed_skills, unassessed_factor=1.0),
            "effective_readiness": calculate_career_readiness(skills),
            "assessment_coverage": calculate_assessment_coverage(skills),
            "skills": enriched_skills,
            "confirmed_gaps": list_confirmed_gaps(skills),
            "next_action": select_next_action(skills),
        }
