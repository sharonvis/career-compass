"""Read-only integration between seeded catalog rows and pure scoring."""

import ast
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from database.db import Base, configure_sqlite_foreign_keys
from database import models as m
from database.seed import seed_database
from services import career_service as service
from services.scoring_service import select_next_action


STAMP = datetime(2025, 1, 1, tzinfo=timezone.utc)
SKILL_ORDER = ["Python", "SQL", "Statistics", "Machine Learning Fundamentals", "Pandas/Data Handling",
               "Git", "Data Structures & Algorithms", "Object-Oriented Programming", "Excel", "Data Visualization"]


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:", poolclass=StaticPool,
                           connect_args={"check_same_thread": False})
    configure_sqlite_foreign_keys(engine)
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            seed_database(session)
            session.commit()
            yield session
    finally:
        engine.dispose()


@pytest.fixture
def catalog(session):
    user = m.User(name="Student", email="student@example.com", degree="BSc", branch="CS", year_of_study=1)
    session.add(user)
    session.commit()
    return dict(user=user,
                skills={s.name: s for s in session.scalars(select(m.Skill))},
                careers={c.name: c for c in session.scalars(select(m.Career))})


def attempt(session, catalog, name, level, day, status="completed", user_id=None):
    row = m.AssessmentAttempt(
        user_id=catalog["user"].id if user_id is None else user_id,
        skill_id=catalog["skills"][name].id, form_name="fixture",
        status=status, resulting_level=level, started_at=STAMP + timedelta(days=day),
        completed_at=STAMP + timedelta(days=day) if status == "completed" else None,
    )
    session.add(row)
    session.commit()
    return row


def summary(session, catalog, career="AI/ML Engineer"):
    return service.get_user_career_summary(session, catalog["user"].id, catalog["careers"][career].id)


@pytest.fixture
def persona(session, catalog):
    for name, level in {"Python": 2, "SQL": 3, "Statistics": 1, "Machine Learning Fundamentals": 1,
                        "Pandas/Data Handling": 2, "Git": 1}.items():
        session.add(m.UserSkillClaim(user_id=catalog["user"].id,
                                    skill_id=catalog["skills"][name].id, claimed_level=level))
    catalog["user"].target_career = catalog["careers"]["AI/ML Engineer"]
    session.commit()
    # Python assessment is fixture state, not a change to v1 assessability.
    attempt(session, catalog, "Python", 2, 0)
    return catalog


@pytest.mark.parametrize("older,newer,insertion_order", [(2, 1, [0, 1]), (1, 2, [0, 1]), (2, 1, [1, 0])])
def test_latest_completed_not_highest_or_insertion_order(session, catalog, older, newer, insertion_order):
    for day in insertion_order:
        attempt(session, catalog, "SQL", [older, newer][day], day)
    assert service.get_latest_demonstrated_level(session, catalog["user"].id, catalog["skills"]["SQL"].id) == newer
    state = service.build_career_skill_state(session, catalog["user"].id, catalog["careers"]["AI/ML Engineer"].id)
    assert next(s for s in state if s["name"] == "SQL")["demonstrated_level"] == newer
    latest_id = session.scalar(select(m.AssessmentAttempt.id)
                               .where(m.AssessmentAttempt.skill_id == catalog["skills"]["SQL"].id)
                               .order_by(m.AssessmentAttempt.completed_at.desc(), m.AssessmentAttempt.id.desc()))
    assert next(s for s in state if s["name"] == "SQL")["latest_attempt_id"] == latest_id


def test_latest_completed_tie_uses_id_descending(session, catalog):
    attempt(session, catalog, "SQL", 3, 0)
    attempt(session, catalog, "SQL", 0, 0)
    assert service.get_latest_demonstrated_level(session, catalog["user"].id, catalog["skills"]["SQL"].id) == 0
    assert next(s for s in summary(session, catalog)["skills"] if s["name"] == "SQL")["demonstrated_level"] == 0
    latest_id = session.scalar(select(m.AssessmentAttempt.id).order_by(m.AssessmentAttempt.id.desc()))
    assert next(s for s in summary(session, catalog)["skills"] if s["name"] == "SQL")["latest_attempt_id"] == latest_id


@pytest.mark.parametrize("status", ["in_progress", "abandoned"])
def test_newer_uncompleted_ignored(session, catalog, status):
    attempt(session, catalog, "SQL", 1, 0)
    attempt(session, catalog, "SQL", 3, 1, status=status)
    assert service.get_latest_demonstrated_level(session, catalog["user"].id, catalog["skills"]["SQL"].id) == 1
    assert next(s for s in summary(session, catalog)["skills"] if s["name"] == "SQL")["demonstrated_level"] == 1


def test_no_completed_and_other_users_and_skills_ignored(session, catalog):
    other = m.User(name="Other", email="other@example.com", degree="BSc", branch="CS", year_of_study=1)
    session.add(other)
    session.commit()
    attempt(session, catalog, "SQL", 3, 1, user_id=other.id)
    attempt(session, catalog, "Python", 3, 1)
    attempt(session, catalog, "SQL", None, 2, status="in_progress")
    assert service.get_latest_demonstrated_level(session, catalog["user"].id, catalog["skills"]["SQL"].id) is None


def test_skill_state_fields_priorities_claim_defaults_and_prerequisites(session, catalog):
    state = service.build_career_skill_state(session, catalog["user"].id, catalog["careers"]["AI/ML Engineer"].id)
    assert [s["name"] for s in state] == SKILL_ORDER[:6]
    assert [s["stable_priority"] for s in state] == [1, 2, 3, 4, 5, 6]
    for skill in state:
        assert set(skill) == {"skill_id", "name", "required_level", "importance", "claimed_level",
                              "demonstrated_level", "latest_attempt_id", "assessable", "stable_priority", "prerequisites"}
        assert skill["skill_id"] == catalog["skills"][skill["name"]].id
        assert skill["claimed_level"] == 0 and skill["demonstrated_level"] is None
        assert skill["latest_attempt_id"] is None
        assert skill["assessable"] == (skill["name"] in {"SQL", "Statistics"})
    by_name = {s["name"]: s for s in state}
    assert by_name["Machine Learning Fundamentals"]["prerequisites"] == [
        {"skill_name": "Python", "minimum_level": 1},
        {"skill_name": "Statistics", "minimum_level": 1},
    ]
    assert by_name["Pandas/Data Handling"]["prerequisites"] == [{"skill_name": "Python", "minimum_level": 1}]


def test_priority_mapping_matches_catalog_not_ids(session, catalog):
    assert list(session.scalars(select(m.Skill.name).order_by(m.Skill.id))) == SKILL_ORDER
    assert service.STABLE_PRIORITY == {name: index for index, name in enumerate(SKILL_ORDER, 1)}
    # Insert requirements in reverse priority order; their row IDs must not decide priority.
    career = m.Career(name="Custom")
    session.add(career)
    session.flush()
    for name in reversed(SKILL_ORDER):
        session.add(m.CareerSkillRequirement(career_id=career.id, skill_id=catalog["skills"][name].id,
                                           required_level=1, importance=1))
    session.commit()
    state = service.build_career_skill_state(session, catalog["user"].id, career.id)
    assert [s["name"] for s in state] == SKILL_ORDER
    assert {s["name"] for s in state if s["assessable"]} == {"SQL", "Statistics"}


def test_summary_copies_states_and_delegates_next_action(session, persona, monkeypatch):
    states = service.build_career_skill_state(session, persona["user"].id, persona["careers"]["AI/ML Engineer"].id)
    original = deepcopy(states)
    monkeypatch.setattr(service, "build_career_skill_state", lambda *args: states)
    next_action = Mock(wraps=select_next_action)
    monkeypatch.setattr(service, "select_next_action", next_action)
    result = summary(session, persona)
    assert states == original
    next_action.assert_called_once_with(states)
    assert set(result) == {"career_id", "career_name", "claimed_readiness", "effective_readiness",
                           "assessment_coverage", "skills", "confirmed_gaps", "next_action"}
    assert result["claimed_readiness"] == 0.8125
    assert result["effective_readiness"] == pytest.approx(12.25 / 24)
    result["skills"][0]["demonstrated_level"] = 0
    assert states == original


def test_golden_persona_and_career_switch(session, persona):
    initial = summary(session, persona)
    assert initial["career_name"] == "AI/ML Engineer"
    assert initial["claimed_readiness"] == 0.8125
    assert initial["effective_readiness"] == pytest.approx(12.25 / 24)
    assert initial["assessment_coverage"] == pytest.approx(5 / 24)
    assert initial["confirmed_gaps"] == []
    assert initial["next_action"] == {"action_type": "assess", "skill_name": "SQL"}
    by_name = {s["name"]: s for s in initial["skills"]}
    assert by_name["Python"]["assessable"] is False
    assert by_name["Pandas/Data Handling"]["prerequisites_met"] is True
    assert by_name["Machine Learning Fundamentals"]["prerequisites_met"] is False
    assert by_name["SQL"]["gap"] is None
    attempt(session, persona, "SQL", 1, 1)
    form_a = summary(session, persona)
    assert form_a["claimed_readiness"] == 0.8125
    assert form_a["effective_readiness"] == pytest.approx(12.25 / 24)
    assert form_a["assessment_coverage"] == pytest.approx(9 / 24)
    assert form_a["confirmed_gaps"] == [dict(skill_name="SQL", required_level=2,
                                            demonstrated_level=1, gap=1, importance=4)]
    assert form_a["next_action"] == {"action_type": "improve", "skill_name": "SQL"}
    attempt(session, persona, "SQL", 2, 2)
    form_b = summary(session, persona)
    assert form_b["claimed_readiness"] == 0.8125
    assert form_b["effective_readiness"] == pytest.approx(14.25 / 24)
    assert form_b["assessment_coverage"] == pytest.approx(9 / 24)
    assert form_b["confirmed_gaps"] == []
    assert next(s for s in form_b["skills"] if s["name"] == "SQL")["gap"] == 0
    assert form_b["next_action"] == {"action_type": "assess", "skill_name": "Statistics"}
    counts_before = (session.scalar(select(func.count()).select_from(m.UserSkillClaim)),
                     session.scalar(select(func.count()).select_from(m.AssessmentAttempt)))
    target = persona["user"].target_career_id
    analyst = summary(session, persona, "Data Analyst")
    assert analyst["effective_readiness"] == pytest.approx(10.5 / 23)
    assert analyst["claimed_readiness"] == pytest.approx(13 / 23)
    assert analyst["assessment_coverage"] == pytest.approx(8 / 23)
    assert analyst["next_action"] == {"action_type": "assess", "skill_name": "Statistics"}
    assert counts_before == (session.scalar(select(func.count()).select_from(m.UserSkillClaim)),
                             session.scalar(select(func.count()).select_from(m.AssessmentAttempt)))
    session.refresh(persona["user"])
    assert persona["user"].target_career_id == target
    assert summary(session, persona) == form_b


def test_zero_assessed_and_gaps_sorted(session, persona):
    attempt(session, persona, "SQL", 0, 1)
    attempt(session, persona, "Statistics", 1, 1)
    attempt(session, persona, "Git", 0, 1)
    result = summary(session, persona)
    assert result["assessment_coverage"] == pytest.approx(15 / 24)
    assert [g["skill_name"] for g in result["confirmed_gaps"]] == ["SQL", "Statistics", "Git"]
    assert [g["gap"] for g in result["confirmed_gaps"]] == [2, 1, 1]
    attempt(session, persona, "SQL", 1, 2)
    result = summary(session, persona)
    assert [g["skill_name"] for g in result["confirmed_gaps"]] == ["SQL", "Statistics", "Git"]


def test_prerequisite_filtering_remains_in_scoring(session, persona):
    # A large ML gap cannot outrank SQL until demonstrated Statistics unlocks it.
    attempt(session, persona, "Machine Learning Fundamentals", 0, 1)
    attempt(session, persona, "SQL", 1, 1)
    blocked = summary(session, persona)
    assert blocked["next_action"] == {"action_type": "improve", "skill_name": "SQL"}
    attempt(session, persona, "Statistics", 1, 2)
    unlocked = summary(session, persona)
    assert unlocked["next_action"] == {"action_type": "improve", "skill_name": "Machine Learning Fundamentals"}


@pytest.mark.parametrize("function", [service.build_career_skill_state, service.get_user_career_summary])
@pytest.mark.parametrize("missing", ["user", "career"])
def test_missing_entities(session, catalog, function, missing):
    user_id = 99999 if missing == "user" else catalog["user"].id
    career_id = 99999 if missing == "career" else catalog["careers"]["AI/ML Engineer"].id
    exception = service.UserNotFoundError if missing == "user" else service.CareerNotFoundError
    with pytest.raises(exception, match="was not found"):
        function(session, user_id, career_id)


@pytest.mark.parametrize("zero_requirement", [False, True])
def test_no_valid_requirements(session, catalog, zero_requirement):
    career = m.Career(name="Empty")
    session.add(career)
    session.flush()
    if zero_requirement:
        session.add(m.CareerSkillRequirement(career_id=career.id, skill_id=catalog["skills"]["Python"].id,
                                           required_level=0, importance=1))
    session.commit()
    with pytest.raises(ValueError, match="no valid skill requirements"):
        service.get_user_career_summary(session, catalog["user"].id, career.id)


def test_zero_level_requirement_skipped(session, catalog):
    career = catalog["careers"]["AI/ML Engineer"]
    git = next(r for r in career.skill_requirements if r.skill.name == "Git")
    git.required_level = 0
    session.commit()
    state = service.build_career_skill_state(session, catalog["user"].id, career.id)
    assert "Git" not in {s["name"] for s in state}


def test_read_only_even_with_pending_changes(session, persona, monkeypatch):
    before = {table.name: session.execute(select(table)).all() for table in Base.metadata.sorted_tables}
    user_id, career_id, skill_id = persona["user"].id, persona["careers"]["AI/ML Engineer"].id, persona["skills"]["SQL"].id
    persona["user"].name = "Unflushed change"
    pending = m.Skill(name="Unflushed skill")
    session.add(pending)
    original_dirty, original_new = set(session.dirty), set(session.new)
    statements = []
    event.listen(session.bind, "before_cursor_execute", lambda *args: statements.append(args[2]))
    with monkeypatch.context() as context:
        for method in ["commit", "add", "flush"]:
            context.setattr(session, method, Mock(side_effect=AssertionError(f"Unexpected {method}")))
        service.get_latest_demonstrated_level(session, user_id, skill_id)
        service.build_career_skill_state(session, user_id, career_id)
        service.get_user_career_summary(session, user_id, career_id)
    assert all(statement.lstrip().upper().startswith("SELECT") for statement in statements)
    assert set(session.dirty) == original_dirty and set(session.new) == original_new
    assert persona["user"].name == "Unflushed change"
    session.rollback()
    after = {table.name: session.execute(select(table)).all() for table in Base.metadata.sorted_tables}
    assert after == before


def test_external_prerequisite_is_reported_not_silently_filtered(session, catalog):
    career = m.Career(name="External prerequisite")
    session.add(career)
    session.flush()
    session.add(m.CareerSkillRequirement(career_id=career.id,
                                       skill_id=catalog["skills"]["Pandas/Data Handling"].id,
                                       required_level=2, importance=1))
    session.commit()
    with pytest.raises(ValueError, match="outside the valid career requirements"):
        service.get_user_career_summary(session, catalog["user"].id, career.id)


def test_no_streamlit_dependency():
    tree = ast.parse(Path(service.__file__).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(alias.name.split(".")[0] != "streamlit" for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert (node.module or "").split(".")[0] != "streamlit"


def test_public_skill_states_outside_career_and_missing_claim(session, catalog):
    excel = catalog["skills"]["Excel"]
    older = attempt(session, catalog, "Excel", 3, 0)
    latest = attempt(session, catalog, "Excel", 1, 1)
    attempt(session, catalog, "Excel", 3, 2, status="abandoned")
    states = service.get_user_skill_states(session, catalog["user"].id, [excel.id, excel.id, 99999])
    assert states == {excel.id: dict(skill_id=excel.id, name="Excel", claimed_level=0,
                                    demonstrated_level=1, latest_attempt_id=latest.id)}
    assert latest.id != older.id
    assert service.get_user_skill_states(session, catalog["user"].id, []) == {}
    with pytest.raises(service.UserNotFoundError):
        service.get_user_skill_states(session, 99999, [])


def test_public_skill_states_tie_zero_and_no_autoflush(session, catalog, monkeypatch):
    sql = catalog["skills"]["SQL"]
    attempt(session, catalog, "SQL", 3, 0)
    latest = attempt(session, catalog, "SQL", 0, 0)
    user_id, sql_id, latest_id = catalog["user"].id, sql.id, latest.id
    catalog["user"].name = "Pending"
    with monkeypatch.context() as context:
        for method in ["flush", "commit", "add"]:
            context.setattr(session, method, Mock(side_effect=AssertionError(method)))
        states = service.get_user_skill_states(session, user_id, [sql_id])
    assert states[sql_id]["demonstrated_level"] == 0
    assert states[sql_id]["latest_attempt_id"] == latest_id
    session.rollback()
