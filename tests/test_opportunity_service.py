"""Opportunity matching contracts tested against isolated seeded SQLite."""

import ast
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from database.db import Base, configure_sqlite_foreign_keys
from database import models as m
from database.seed import seed_database
from services import opportunity_service as service
from services.career_service import UserNotFoundError, CareerNotFoundError


TODAY = date(2030, 1, 1)
STAMP = datetime(2025, 1, 1, tzinfo=timezone.utc)


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:", poolclass=StaticPool,
                           connect_args={"check_same_thread": False})
    configure_sqlite_foreign_keys(engine)
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            seed_database(session)
            # Fixed dates keep seeded visibility tests independent of the calendar.
            for opportunity in session.scalars(select(m.Opportunity)):
                opportunity.deadline = TODAY + timedelta(days=30)
            session.commit()
            yield session
    finally:
        engine.dispose()


@pytest.fixture
def persona(session):
    skills = {s.name: s for s in session.scalars(select(m.Skill))}
    careers = {c.name: c.id for c in session.scalars(select(m.Career))}
    opportunities = {o.title: o.id for o in session.scalars(select(m.Opportunity))}
    user = m.User(name="Student", email="student@example.com", degree="BSc", branch="CS", year_of_study=1,
                  target_career_id=careers["AI/ML Engineer"])
    session.add(user)
    session.flush()
    for name, level in {"Python": 2, "SQL": 3, "Statistics": 1, "Machine Learning Fundamentals": 1,
                        "Pandas/Data Handling": 2, "Git": 1}.items():
        session.add(m.UserSkillClaim(user_id=user.id, skill_id=skills[name].id, claimed_level=level))
    session.commit()
    result = dict(user_id=user.id, skills=skills, careers=careers, opportunities=opportunities)
    add_attempt(session, result, "Python", 2, 0)
    return result


def add_attempt(session, persona, name, level, day, status="completed"):
    attempt = m.AssessmentAttempt(user_id=persona["user_id"], skill_id=persona["skills"][name].id,
                                  form_name="fixture", status=status, resulting_level=level,
                                  started_at=STAMP + timedelta(days=day),
                                  completed_at=STAMP + timedelta(days=day) if status == "completed" else None)
    session.add(attempt)
    session.commit()
    return attempt.id


def match(session, persona, title="Data Engineering Intern", career="AI/ML Engineer", **kwargs):
    return service.get_opportunity_match(session, persona["user_id"], persona["careers"][career],
                                         persona["opportunities"][title], today=TODAY, **kwargs)


def ranked(session, persona, career="AI/ML Engineer", **kwargs):
    return service.get_ranked_opportunities(session, persona["user_id"], persona["careers"][career], today=TODAY, **kwargs)


def listing(session, persona, title, requirements, deadline=None, source="live"):
    row = m.Opportunity(title=title, company="Demo", location=None, opportunity_type="internship",
                        source=source, source_url="https://example.com/listing" if source != "seed" else None,
                        deadline=deadline, is_seeded=source == "seed")
    session.add(row)
    session.flush()
    for name, level, required in requirements:
        session.add(m.OpportunitySkill(opportunity_id=row.id, skill_id=persona["skills"][name].id,
                                       required_level=level, is_required=required))
    session.commit()
    return row.id


def single(session, persona, opportunity_id, **kwargs):
    return service.get_opportunity_match(session, persona["user_id"], persona["careers"]["AI/ML Engineer"],
                                         opportunity_id, today=TODAY, **kwargs)


def snapshot(session):
    return {table.name: session.execute(select(table)).all() for table in Base.metadata.sorted_tables}


def test_required_and_optional_skill_states(session, persona):
    state = service.build_opportunity_skill_state(session, persona["user_id"],
                                                  persona["opportunities"]["Data Engineering Intern"])
    assert state == dict(required_skills=[
        dict(skill_id=persona["skills"]["Python"].id, skill_name="Python", required_level=2,
             is_required=True, claimed_level=2, demonstrated_level=2),
        dict(skill_id=persona["skills"]["SQL"].id, skill_name="SQL", required_level=2,
             is_required=True, claimed_level=3, demonstrated_level=None),
    ], optional_skills=[dict(skill_id=persona["skills"]["Git"].id, skill_name="Git", required_level=1,
                             is_required=False, claimed_level=1, demonstrated_level=None)])


def test_opportunity_only_skills_and_missing_claim(session, persona):
    state = service.build_opportunity_skill_state(session, persona["user_id"], persona["opportunities"]["Data Analyst Intern"])
    excel = next(s for s in state["required_skills"] if s["skill_name"] == "Excel")
    assert excel["claimed_level"] == 0 and excel["demonstrated_level"] is None
    add_attempt(session, persona, "Excel", 2, 1)
    state = service.build_opportunity_skill_state(session, persona["user_id"], persona["opportunities"]["Data Analyst Intern"])
    assert next(s for s in state["required_skills"] if s["skill_name"] == "Excel")["demonstrated_level"] == 2


def test_latest_completed_not_highest_and_incomplete_ignored(session, persona):
    add_attempt(session, persona, "SQL", 3, 0)
    add_attempt(session, persona, "SQL", 1, 1)
    add_attempt(session, persona, "SQL", 3, 2, "in_progress")
    add_attempt(session, persona, "SQL", 3, 3, "abandoned")
    assert match(session, persona)["match_band"] == "stretch"
    add_attempt(session, persona, "SQL", 0, 1)  # Timestamp tie: later ID wins.
    assert next(s for s in match(session, persona)["required_skills"] if s["skill_name"] == "SQL")["demonstrated_level"] == 0


def test_golden_good_stretch_strong_flow_and_reasons(session, persona):
    initial = match(session, persona)
    assert initial["match_band"] == "good" and initial["eligibility_checked"] is False
    assert initial["source"] == "seed" and initial["source_url"] is None and initial["is_seeded"] is True
    assert initial["reasons"] == [dict(code="unverified_but_claimed", skill_name="SQL",
                                       text="SQL: claimed Advanced meets the Intermediate requirement, but remains unverified.")]
    add_attempt(session, persona, "SQL", 1, 1)
    form_a = match(session, persona)
    assert form_a["match_band"] == "stretch"
    assert form_a["reasons"] == [dict(code="demonstrated_gap", skill_name="SQL",
                                      text="SQL: demonstrated Beginner; Intermediate is required.")]
    add_attempt(session, persona, "SQL", 2, 2)
    strong = match(session, persona)
    assert strong["match_band"] == "strong"
    assert strong["reasons"] == [dict(code="all_required_skills_met", text="Demonstrated levels meet all required skills.")]


@pytest.mark.parametrize("sql_level,expected", [(None, "good"), (1, "stretch"), (2, "strong")])
def test_optional_skill_never_changes_band_or_relevance(session, persona, sql_level, expected):
    if sql_level is not None:
        add_attempt(session, persona, "SQL", sql_level, 1)
    initial = match(session, persona)
    git_claim = session.scalar(select(m.UserSkillClaim).where(m.UserSkillClaim.skill_id == persona["skills"]["Git"].id))
    git_claim.claimed_level = 0
    session.commit()
    add_attempt(session, persona, "Git", 0, 2)
    result = match(session, persona)
    assert result["match_band"] == initial["match_band"] == expected
    assert result["career_relevance"] == initial["career_relevance"] == dict(matched=2, total=2)
    assert sum(reason["code"] == "optional_skills_missing" for reason in result["reasons"]) == 1


def test_low_claim_reason_and_level_labels(session, persona):
    claim = session.scalar(select(m.UserSkillClaim).where(m.UserSkillClaim.skill_id == persona["skills"]["SQL"].id))
    claim.claimed_level = 0
    session.commit()
    result = match(session, persona)
    assert result["match_band"] == "stretch"
    assert result["reasons"] == [dict(code="claimed_below_requirement", skill_name="SQL",
                                      text="SQL: unverified claim is Not Known, below the Intermediate requirement.")]


def test_hard_filters_and_deterministic_reasons(session, persona):
    result = match(session, persona, hard_filter_results={"location": False, "degree": True, "batch": False})
    assert result["match_band"] == "not_eligible" and result["eligibility_checked"] is True
    assert result["reasons"] == [dict(code="hard_filter_failed", filter="batch", text="Batch eligibility requirement is not met."),
                                  dict(code="hard_filter_failed", filter="location", text="Location eligibility requirement is not met.")]
    assert match(session, persona, hard_filter_results={})["eligibility_checked"] is True
    assert match(session, persona, hard_filter_results={"degree": True})["match_band"] == "good"


def test_no_required_skills_skips_classifier_and_ranked_visibility(session, persona, monkeypatch):
    opportunity_id = listing(session, persona, "Optional only", [("Git", 1, False), ("Python", 0, True)])
    classifier = Mock(side_effect=AssertionError("Classifier called without required skills"))
    with monkeypatch.context() as context:
        context.setattr(service, "classify_opportunity_match", classifier)
        result = single(session, persona, opportunity_id)
    assert result["match_band"] is None
    assert result["career_relevance"] == dict(matched=0, total=0)
    assert "no_required_skills" in {r["code"] for r in result["reasons"]}
    assert opportunity_id not in {r["opportunity_id"] for r in ranked(session, persona)}


@pytest.mark.parametrize("career,expected_ids,expected_titles", [
    ("AI/ML Engineer", {1, 2, 3, 4, 10}, {"Machine Learning Intern", "AI Research Assistant Intern", "Junior Data Scientist Trainee", "Data Engineering Intern", "Junior Data Analyst"}),
    ("Software Engineer", {4, 5, 6, 7}, {"Data Engineering Intern", "Software Development Intern", "Backend Developer Intern", "Associate Software Engineer"}),
    ("Data Analyst", {3, 4, 8, 9, 10}, {"Junior Data Scientist Trainee", "Data Engineering Intern", "Data Analyst Intern", "Business Analytics Intern", "Junior Data Analyst"}),
])
def test_pinned_seeded_visible_sets(session, persona, career, expected_ids, expected_titles):
    results = ranked(session, persona, career)
    assert {result["opportunity_id"] for result in results} == expected_ids
    assert {result["title"] for result in results} == expected_titles


def test_relevance_only_counts_valid_required_skills():
    assert service.calculate_career_relevance([1, 2], [
        dict(skill_id=1, required_level=2, is_required=True),
        dict(skill_id=3, required_level=2, is_required=True),
        dict(skill_id=2, required_level=3, is_required=False),
        dict(skill_id=2, required_level=0, is_required=True),
    ]) == dict(matched=1, total=2)
    assert service.calculate_career_relevance([], []) == dict(matched=0, total=0)


def test_same_band_across_careers_relevance_and_visibility_change(session, persona):
    title = "Machine Learning Intern"
    results = [match(session, persona, title, career) for career in persona["careers"]]
    assert {result["match_band"] for result in results} == {"good"}
    assert [r["career_relevance"] for r in results] == [dict(matched=3, total=3), dict(matched=1, total=3), dict(matched=2, total=3)]
    assert title in {r["title"] for r in ranked(session, persona, "AI/ML Engineer")}
    assert title not in {r["title"] for r in ranked(session, persona, "Software Engineer")}


def test_relevance_threshold_at_exact_four_fifths(session, persona):
    accepted = listing(session, persona, "Exactly four fifths", [(name, 1, True) for name in ["Python", "SQL", "Statistics", "Git", "Excel"]])
    rejected = listing(session, persona, "Three fifths", [(name, 1, True) for name in ["Python", "SQL", "Git", "Excel", "Data Visualization"]])
    ids = {r["opportunity_id"] for r in ranked(session, persona)}
    assert accepted in ids and rejected not in ids
    assert single(session, persona, accepted)["career_relevance"] == dict(matched=4, total=5)


def test_band_ranking_strong_good_stretch_not_eligible(session, persona):
    strong = listing(session, persona, "Strong", [("Python", 2, True)])
    good = listing(session, persona, "Good", [("SQL", 2, True)])
    stretch = listing(session, persona, "Stretch", [("Statistics", 2, True)])
    blocked = listing(session, persona, "Blocked", [("Python", 2, True)])
    results = ranked(session, persona, hard_filters_by_opportunity={blocked: {"batch": False}})
    selected = [r for r in results if r["opportunity_id"] in {strong, good, stretch, blocked}]
    assert [r["opportunity_id"] for r in selected] == [strong, good, stretch, blocked]
    assert [r["match_band"] for r in selected] == ["strong", "good", "stretch", "not_eligible"]


def test_relevance_ranks_by_exact_fraction_before_unmet_and_deadline(session, persona):
    five = listing(session, persona, "Four fifths", [(n, 1, True) for n in ["Python", "SQL", "Statistics", "Git", "Excel"]], TODAY)
    six = listing(session, persona, "Five sixths", [(n, 1, True) for n in ["Python", "SQL", "Statistics", "Git", "Pandas/Data Handling", "Excel"]], TODAY + timedelta(days=2))
    full = listing(session, persona, "Full overlap", [("Python", 3, True)], None)
    results = [r["opportunity_id"] for r in ranked(session, persona) if r["opportunity_id"] in {five, six, full}]
    assert results == [full, six, five]


def test_fewer_unmet_required_skills_rank_first(session, persona):
    two = listing(session, persona, "Two gaps", [("Python", 3, True), ("Statistics", 2, True)], TODAY)
    one = listing(session, persona, "One gap", [("Python", 3, True), ("Statistics", 1, True)], None)
    results = [r["opportunity_id"] for r in ranked(session, persona) if r["opportunity_id"] in {one, two}]
    assert results == [one, two]


def test_deadline_none_and_id_tiebreak(session, persona):
    no_deadline = listing(session, persona, "No deadline", [("Python", 2, True)])
    later = listing(session, persona, "Later", [("Python", 2, True)], TODAY + timedelta(days=5))
    earlier = listing(session, persona, "Earlier", [("Python", 2, True)], TODAY)
    same = listing(session, persona, "Same", [("Python", 2, True)], TODAY)
    result = [r["opportunity_id"] for r in ranked(session, persona) if r["opportunity_id"] in {no_deadline, later, earlier, same}]
    assert result == [earlier, same, later, no_deadline]
    assert single(session, persona, no_deadline)["is_expired"] is False
    assert single(session, persona, earlier)["is_expired"] is False


def test_expired_single_lookup_and_hidden_rankings(session, persona):
    expired = listing(session, persona, "Expired", [("Python", 2, True)], TODAY - timedelta(days=1))
    assert single(session, persona, expired)["is_expired"] is True
    assert expired not in {r["opportunity_id"] for r in ranked(session, persona)}


def test_today_defaults_to_calendar_date(session, persona):
    opportunity_id = listing(session, persona, "Yesterday", [("Python", 2, True)], date.today() - timedelta(days=1))
    result = service.get_opportunity_match(session, persona["user_id"], persona["careers"]["AI/ML Engineer"], opportunity_id)
    assert result["is_expired"] is True


def test_live_normalized_rows_share_seed_matching_logic(session, persona):
    live = listing(session, persona, "Live Data Engineering", [("Python", 2, True), ("SQL", 2, True), ("Git", 1, False)])
    for sql_level in [None, 1, 2]:
        if sql_level is not None:
            add_attempt(session, persona, "SQL", sql_level, sql_level)
        result, seeded = single(session, persona, live), match(session, persona)
        assert result["match_band"] == seeded["match_band"]
        assert result["career_relevance"] == seeded["career_relevance"]
        assert result["reasons"] == seeded["reasons"]
        assert result["is_seeded"] is False and result["source"] == "live"
        assert result["source_url"] == "https://example.com/listing"


@pytest.mark.parametrize("missing", ["user", "career", "opportunity"])
def test_unknown_entities(session, persona, missing):
    exception = {"user": UserNotFoundError, "career": CareerNotFoundError, "opportunity": service.OpportunityNotFoundError}[missing]
    with pytest.raises(exception, match="was not found"):
        service.get_opportunity_match(session, 99999 if missing == "user" else persona["user_id"],
                                      99999 if missing == "career" else persona["careers"]["AI/ML Engineer"],
                                      99999 if missing == "opportunity" else persona["opportunities"]["Data Engineering Intern"])


@pytest.mark.parametrize("missing", ["user", "career"])
def test_ranked_verifies_entities_even_at_zero_limit(session, persona, missing):
    exception = UserNotFoundError if missing == "user" else CareerNotFoundError
    with pytest.raises(exception):
        service.get_ranked_opportunities(session, 99999 if missing == "user" else persona["user_id"],
                                          99999 if missing == "career" else persona["careers"]["AI/ML Engineer"], limit=0)


def test_limits_and_determinism(session, persona):
    all_results = ranked(session, persona)
    assert ranked(session, persona, limit=None) == all_results
    assert ranked(session, persona, limit=0) == []
    assert ranked(session, persona, limit=2) == all_results[:2]
    assert ranked(session, persona, limit=99) == all_results
    with pytest.raises(ValueError, match="negative"):
        ranked(session, persona, limit=-1)


def test_empty_opportunity_database(session, persona):
    for opportunity in session.scalars(select(m.Opportunity)):
        session.delete(opportunity)
    session.commit()
    assert ranked(session, persona) == []


def test_read_only_even_with_pending_changes(session, persona, monkeypatch):
    user_id = persona["user_id"]
    career_id = persona["careers"]["AI/ML Engineer"]
    opportunity_id = persona["opportunities"]["Data Engineering Intern"]
    before = snapshot(session)
    session.get(m.User, user_id).name = "Unflushed edit"
    with monkeypatch.context() as context:
        for method in ["add", "flush", "commit"]:
            context.setattr(session, method, Mock(side_effect=AssertionError(method)))
        service.build_opportunity_skill_state(session, user_id, opportunity_id)
        service.get_opportunity_match(session, user_id, career_id, opportunity_id, today=TODAY)
        service.get_ranked_opportunities(session, user_id, career_id, today=TODAY)
    assert session.get(m.User, user_id).name == "Unflushed edit"
    session.rollback()
    assert snapshot(session) == before


def test_no_streamlit_or_network_dependencies():
    tree = ast.parse(Path(service.__file__).read_text(encoding="utf-8"))
    forbidden = {"streamlit", "serpapi", "requests", "httpx", "urllib", "socket", "aiohttp"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(alias.name.split(".")[0] not in forbidden for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert (node.module or "").split(".")[0] not in forbidden
