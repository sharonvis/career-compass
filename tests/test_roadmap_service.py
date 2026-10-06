"""Roadmap acceptance tests using real career summaries and isolated SQLite."""

import ast
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from database.db import Base, configure_sqlite_foreign_keys
from database import models as m
from database.seed import seed_database
from services import roadmap_service as roadmap
from services.career_service import CareerNotFoundError, UserNotFoundError, get_user_career_summary


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
            session.commit()
            yield session
    finally:
        engine.dispose()


@pytest.fixture
def persona(session):
    skills = {s.name: s for s in session.scalars(select(m.Skill))}
    careers = {c.name: c for c in session.scalars(select(m.Career))}
    user = m.User(name="Student", email="student@example.com", degree="BSc", branch="CS",
                  year_of_study=1, target_career=careers["AI/ML Engineer"])
    session.add(user)
    session.flush()
    for name, level in {"Python": 2, "SQL": 3, "Statistics": 1, "Machine Learning Fundamentals": 1,
                        "Pandas/Data Handling": 2, "Git": 1}.items():
        session.add(m.UserSkillClaim(user_id=user.id, skill_id=skills[name].id, claimed_level=level))
    session.commit()
    data = dict(user_id=user.id, skills=skills, careers=careers)
    add_attempt(session, data, "Python", 2, 0)
    return data


def add_attempt(session, persona, name, level, day):
    attempt = m.AssessmentAttempt(user_id=persona["user_id"], skill_id=persona["skills"][name].id,
                                  form_name="fixture", status="completed", resulting_level=level,
                                  completed_at=STAMP + timedelta(days=day))
    session.add(attempt)
    session.commit()
    return attempt.id


def get_roadmap(session, persona, career="AI/ML Engineer", limit=5):
    return roadmap.get_user_roadmap(session, persona["user_id"], persona["careers"][career].id, limit)


def summary(session, persona, career="AI/ML Engineer"):
    return get_user_career_summary(session, persona["user_id"], persona["careers"][career].id)


def current(items):
    active = [item for item in items if item["status"] == "current"]
    assert len(active) == 1
    return active[0]


def snapshot(session):
    return {table.name: session.execute(select(table)).all() for table in Base.metadata.sorted_tables}


def test_initial_persona_order_and_plain_item_structure(session, persona):
    items = get_roadmap(session, persona)
    assert items[0]["title"] == "Assess SQL" and items[0]["status"] == "current"
    assert items[0]["item_key"] == f"assess:{persona['skills']['SQL'].id}"
    assert items[1]["title"] == "Assess Statistics" and items[1]["status"] == "up_next"
    assert items[0]["current_level"] is None and items[0]["gap"] is None
    fields = {"item_key", "position", "action_type", "skill_id", "skill_name", "title", "reason",
              "required_level", "current_level", "gap", "status", "prerequisites_met"}
    for position, item in enumerate(items, 1):
        assert set(item) == fields and item["position"] == position
        assert all(value is None or isinstance(value, (str, int, bool)) for value in item.values())


@pytest.mark.parametrize("new_level", [1, 2])
def test_improve_reassess_golden_loop_and_attempt_specific_history(session, persona, new_level):
    sql_id = persona["skills"]["SQL"].id
    old_attempt = add_attempt(session, persona, "SQL", 1, 1)
    items = get_roadmap(session, persona)
    key = f"improve:{sql_id}:{old_attempt}"
    assert items[0]["item_key"] == key and items[0]["title"] == "Improve SQL"
    assert current(items)["item_key"] == key
    before = summary(session, persona)
    row = roadmap.mark_roadmap_item_completed(session, persona["user_id"], key)
    session.commit()
    assert summary(session, persona) == before
    items = get_roadmap(session, persona, limit=1)
    assert [item["item_key"] for item in items] == [key, f"reassess:{sql_id}:{old_attempt}"]
    assert items[0]["status"] == "completed"
    assert current(items)["title"] == "Reassess SQL"
    assert current(items)["action_type"] == "assess"
    assert session.get(m.AssessmentAttempt, old_attempt).resulting_level == 1
    new_attempt = add_attempt(session, persona, "SQL", new_level, 2)
    items = get_roadmap(session, persona)
    assert session.get(m.RoadmapCompletion, row.id).completed is True
    assert any(item["item_key"] == key and item["status"] == "completed" for item in items)
    if new_level == 2:
        assert current(items)["title"] == "Assess Statistics"
        assert not any(item["skill_name"] == "SQL" and item["status"] != "completed" for item in items)
    else:
        assert current(items)["item_key"] == f"improve:{sql_id}:{new_attempt}"
        assert current(items)["item_key"] != key


@pytest.mark.parametrize("helper", [roadmap.mark_roadmap_item_completed, roadmap.mark_roadmap_item_incomplete])
@pytest.mark.parametrize("key", ["assess:1", "reassess:1:2", "unknown:1", "", None])
def test_forbidden_manual_keys(session, persona, helper, key):
    before = snapshot(session)
    with pytest.raises(ValueError, match="Only improve: and learn:"):
        helper(session, persona["user_id"], key)
    assert snapshot(session) == before


def test_learn_self_reported_gap_completed_without_changing_evidence(session, persona):
    items = get_roadmap(session, persona, "Software Engineer", limit=20)
    oop = next(item for item in items if item["skill_name"] == "Object-Oriented Programming")
    assert oop["action_type"] == "learn" and oop["title"] == "Learn Object-Oriented Programming"
    assert "unverified" in oop["reason"]
    assert oop["current_level"] == 0 and oop["gap"] == 2
    before = summary(session, persona, "Software Engineer")
    roadmap.mark_roadmap_item_completed(session, persona["user_id"], oop["item_key"])
    session.commit()
    assert summary(session, persona, "Software Engineer") == before
    for _ in range(2):
        items = get_roadmap(session, persona, "Software Engineer", limit=20)
        matches = [item for item in items if item["item_key"] == oop["item_key"]]
        assert len(matches) == 1 and matches[0]["status"] == "completed"
    skill = next(s for s in before["skills"] if s["name"] == "Object-Oriented Programming")
    assert skill["demonstrated_level"] is None


def test_locked_learning_never_current_and_prerequisite_unlocks(session, persona):
    items = get_roadmap(session, persona)
    ml = next(item for item in items if item["skill_name"] == "Machine Learning Fundamentals")
    assert ml["status"] == "locked" and ml["prerequisites_met"] is False
    add_attempt(session, persona, "Statistics", 1, 1)
    items = get_roadmap(session, persona)
    ml = next(item for item in items if item["skill_name"] == "Machine Learning Fundamentals")
    assert ml["status"] != "locked" and ml["prerequisites_met"] is True


def test_locked_improve_and_assess_use_summary_prerequisites(session, persona):
    add_attempt(session, persona, "Machine Learning Fundamentals", 0, 1)
    items = get_roadmap(session, persona)
    assert current(items)["title"] == "Assess SQL"
    ml = next(item for item in items if item["skill_name"] == "Machine Learning Fundamentals")
    assert ml["action_type"] == "improve" and ml["status"] == "locked"
    # Make SQL require Statistics to test an assess lock through the real summary.
    session.add(m.SkillPrerequisite(skill_id=persona["skills"]["SQL"].id,
                                   prerequisite_skill_id=persona["skills"]["Statistics"].id, minimum_level=1))
    session.commit()
    items = get_roadmap(session, persona)
    assert current(items)["title"] == "Assess Statistics"
    assert next(i for i in items if i["skill_name"] == "SQL")["status"] == "locked"


@pytest.mark.parametrize("limit", [1, 2, 5, 20])
def test_limit_counts_active_items_and_preserves_current(session, persona, limit):
    items = get_roadmap(session, persona, limit=limit)
    assert current(items)["title"] == "Assess SQL"
    assert len([i for i in items if i["status"] != "completed"]) <= limit
    assert items == get_roadmap(session, persona, limit=limit)


def test_completed_history_does_not_consume_limit(session, persona):
    attempt_id = add_attempt(session, persona, "SQL", 1, 1)
    key = f"improve:{persona['skills']['SQL'].id}:{attempt_id}"
    roadmap.mark_roadmap_item_completed(session, persona["user_id"], key)
    session.commit()
    items = get_roadmap(session, persona, limit=2)
    assert len(items) == 3
    assert len([i for i in items if i["status"] != "completed"]) == 2
    assert current(items)["item_key"].startswith("reassess:")


def test_limit_preserves_completed_history_of_deferred_reassessments(session, persona):
    sql_attempt = add_attempt(session, persona, "SQL", 1, 1)
    git_attempt = add_attempt(session, persona, "Git", 0, 1)
    keys = [f"improve:{persona['skills']['SQL'].id}:{sql_attempt}",
            f"improve:{persona['skills']['Git'].id}:{git_attempt}"]
    for key in keys:
        roadmap.mark_roadmap_item_completed(session, persona["user_id"], key)
    session.commit()
    items = get_roadmap(session, persona, limit=1)
    assert {item["item_key"] for item in items if item["status"] == "completed"} == set(keys)
    assert len([item for item in items if item["status"] != "completed"]) == 1
    assert current(items)["title"] == "Reassess SQL"


def test_career_switch_shared_completion_and_irrelevant_stale_rows(session, persona):
    attempt_id = add_attempt(session, persona, "SQL", 1, 1)
    key = f"improve:{persona['skills']['SQL'].id}:{attempt_id}"
    roadmap.mark_roadmap_item_completed(session, persona["user_id"], key)
    for stale_key in ["improve:999:999", "improve:bad:key", "learn:999", "reassess:999:999"]:
        session.add(m.RoadmapCompletion(user_id=persona["user_id"], roadmap_item_key=stale_key, completed=True))
    oop_key = f"learn:{persona['skills']['Object-Oriented Programming'].id}"
    roadmap.mark_roadmap_item_completed(session, persona["user_id"], oop_key)
    session.commit()
    before = snapshot(session)
    ai = get_roadmap(session, persona)
    analyst = get_roadmap(session, persona, "Data Analyst")
    assert current(ai)["item_key"] == current(analyst)["item_key"] == key.replace("improve:", "reassess:")
    assert any(i["skill_name"] == "Excel" for i in analyst)
    assert not any(i["item_key"] == oop_key for i in analyst)
    assert get_roadmap(session, persona) == ai
    assert snapshot(session) == before


@pytest.mark.parametrize("missing", ["user", "career"])
def test_unknown_entities(session, persona, missing):
    exception = UserNotFoundError if missing == "user" else CareerNotFoundError
    with pytest.raises(exception):
        roadmap.get_user_roadmap(session, 99999 if missing == "user" else persona["user_id"],
                                 99999 if missing == "career" else persona["careers"]["AI/ML Engineer"].id)


def test_empty_roadmap_and_completed_only_return_empty(session, persona):
    career = m.Career(name="Only Python")
    session.add(career)
    session.flush()
    session.add(m.CareerSkillRequirement(career_id=career.id, skill_id=persona["skills"]["Python"].id,
                                       required_level=2, importance=1))
    session.commit()
    assert roadmap.get_user_roadmap(session, persona["user_id"], career.id) == []
    career2 = m.Career(name="Only OOP")
    session.add(career2)
    session.flush()
    session.add(m.CareerSkillRequirement(career_id=career2.id, skill_id=persona["skills"]["Object-Oriented Programming"].id,
                                       required_level=2, importance=1))
    session.add(m.CareerSkillRequirement(career_id=career2.id, skill_id=persona["skills"]["Python"].id,
                                       required_level=2, importance=1))
    session.commit()
    key = f"learn:{persona['skills']['Object-Oriented Programming'].id}"
    roadmap.mark_roadmap_item_completed(session, persona["user_id"], key)
    session.commit()
    assert roadmap.get_user_roadmap(session, persona["user_id"], career2.id) == []


def test_generation_read_only_and_uses_career_summary(session, persona, monkeypatch):
    before = snapshot(session)
    original = roadmap.get_user_career_summary
    summary_spy = Mock(wraps=original)
    monkeypatch.setattr(roadmap, "get_user_career_summary", summary_spy)
    career_id = persona["careers"]["AI/ML Engineer"].id
    session.get(m.User, persona["user_id"]).name = "Pending edit"
    with monkeypatch.context() as context:
        for method in ["add", "flush", "commit"]:
            context.setattr(session, method, Mock(side_effect=AssertionError(f"Unexpected {method}")))
        roadmap.get_user_roadmap(session, persona["user_id"], career_id)
    summary_spy.assert_called_once()
    assert session.get(m.User, persona["user_id"]).name == "Pending edit"
    session.rollback()
    assert snapshot(session) == before


def test_completion_helpers_only_change_completion_and_do_not_commit(session, persona, monkeypatch):
    before = snapshot(session)
    key = f"learn:{persona['skills']['Object-Oriented Programming'].id}"
    with monkeypatch.context() as context:
        context.setattr(session, "commit", Mock(side_effect=AssertionError("Unexpected commit")))
        row = roadmap.mark_roadmap_item_completed(session, persona["user_id"], key, STAMP)
        assert row.completed is True and row.completed_at == STAMP
        assert roadmap.mark_roadmap_item_completed(session, persona["user_id"], key, STAMP) is row
        session.flush()
        assert roadmap.mark_roadmap_item_incomplete(session, persona["user_id"], key) is row
        assert row.completed is False and row.completed_at is None
        row = roadmap.mark_roadmap_item_completed(session, persona["user_id"], key)
        assert row.completed_at.tzinfo is timezone.utc
        session.flush()
    after = snapshot(session)
    assert {k: v for k, v in before.items() if k != "roadmap_completions"} == {
        k: v for k, v in after.items() if k != "roadmap_completions"}
    assert len(after["roadmap_completions"]) == 1
    session.rollback()
    assert snapshot(session) == before


def test_incomplete_get_or_create_and_unknown_user(session, persona):
    key = f"learn:{persona['skills']['Excel'].id}"
    row = roadmap.mark_roadmap_item_incomplete(session, persona["user_id"], key)
    assert row.completed is False and row.completed_at is None
    with pytest.raises(UserNotFoundError):
        roadmap.mark_roadmap_item_completed(session, 99999, key)


@pytest.mark.parametrize("limit", [0, -1, None, 1.5, True])
def test_limit_must_be_positive_integer(session, persona, limit):
    with pytest.raises(ValueError, match="positive integer"):
        get_roadmap(session, persona, limit=limit)


def test_no_streamlit_import():
    tree = ast.parse(Path(roadmap.__file__).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(alias.name.split(".")[0] != "streamlit" for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert (node.module or "").split(".")[0] != "streamlit"
