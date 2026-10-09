"""Actual onboarding UI against isolated temporary SQLite."""
import ast
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session, sessionmaker
from streamlit.testing.v1 import AppTest

from database import db, models as m
from database.seed import seed_database
from services import user_service as users
from services.career_service import get_user_skill_states

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'onboarding.db'}", connect_args={"check_same_thread": False})
    db.configure_sqlite_foreign_keys(engine)
    db.Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(db, "SessionLocal", factory)
    with factory() as session:
        seed_database(session)
        session.commit()
    yield engine, factory
    engine.dispose()


def page():
    return AppTest.from_file(str(ROOT / "app.py")).run().switch_page("pages/Onboarding.py").run()


def fill(at, email=" New@Example.COM "):
    at.text_input(key="onboarding_email").set_value(email).run()
    for field, value in [("name", " New Student "), ("degree", " BSc "), ("branch", " CS ")]:
        at.text_input(key=f"onboarding_{field}").set_value(value)
    at.selectbox(key="onboarding_year").set_value(2)
    at.run()
    return at


def submit(at):
    return at.button(key="build_career_compass").click().run()


def test_new_user_persists_fresh_session_and_simple_state(isolated):
    engine, factory = isolated
    at = fill(page())
    assert not at.exception
    expected = dict(at.session_state["onboarding_claims"])
    for radio in list(at.radio):
        at.radio(key=radio.key).set_value(3).run()
    submit(at)
    assert not at.exception
    user_id = at.session_state["user_id"]
    assert type(user_id) is int
    with factory() as session:
        profile = users.get_user_profile(session, user_id)
        assert profile["email"] == "new@example.com"
        assert (profile["name"], profile["degree"], profile["branch"], profile["year_of_study"]) == ("New Student", "BSc", "CS", 2)
        assert profile["target_career_name"] == "AI/ML Engineer"
        states = get_user_skill_states(session, user_id, list(expected))
        assert set(states) == set(expected)
        assert all(s["claimed_level"] == 3 for s in states.values())
    assert all(not isinstance(v, (Session, db.Base)) for v in at.session_state._state.filtered_state.values())


def test_returning_user_prefill_switch_and_history(isolated):
    _, factory = isolated
    with factory() as session:
        user = users.create_user(session, "Original", "old@example.com", "BA", "Math", 4)
        careers = users.list_careers(session)
        users.set_target_career(session, user["user_id"], careers[0]["career_id"])
        skills = users.list_career_skills(session, careers[0]["career_id"])
        sql_id = next(s["skill_id"] for s in skills if s["name"] == "SQL")
        users.set_skill_claim(session, user["user_id"], sql_id, 3)
        session.add(m.AssessmentAttempt(user_id=user["user_id"], skill_id=sql_id, form_name="A", status="completed", resulting_level=1, completed_at=datetime.now(timezone.utc)))
        session.commit()
    at = page()
    at.text_input(key="onboarding_email").set_value(" OLD@EXAMPLE.COM ").run()
    assert at.text_input(key="onboarding_name").value == "Original"
    assert at.text_input(key="onboarding_name").disabled
    assert at.selectbox(key="onboarding_year").disabled
    assert at.radio(key=f"onboarding_claim_{sql_id}").value == 3
    at.radio(key=f"onboarding_claim_{sql_id}").set_value(2).run()
    at.button(key="target_career_select_2").click().run()
    assert at.radio(key=f"onboarding_claim_{sql_id}").value == 2
    at.button(key="target_career_select_1").click().run()
    at.button(key="target_career_select_2").click().run()
    assert at.radio(key=f"onboarding_claim_{sql_id}").value == 2
    submit(at)
    assert not at.exception
    assert at.session_state["user_id"] == user["user_id"]
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(m.User)) == 1
        profile = users.get_user_profile(session, user["user_id"])
        assert (profile["name"], profile["degree"], profile["branch"], profile["year_of_study"]) == ("Original", "BA", "Math", 4)
        assert profile["target_career_name"] == "Data Analyst"
        assert get_user_skill_states(session, user["user_id"], [sql_id])[sql_id]["claimed_level"] == 2
        assert session.scalar(select(func.count()).select_from(m.AssessmentAttempt)) == 1


@pytest.mark.parametrize("field,value", [("name", " "), ("email", "bad"), ("email", ""), ("degree", ""), ("branch", " ")])
def test_invalid_fields_no_writes(isolated, field, value):
    _, factory = isolated
    at = fill(page())
    at.text_input(key=f"onboarding_{field}").set_value(value).run()
    submit(at)
    assert at.error and not at.exception
    assert "user_id" not in at.session_state
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(m.User)) == 0


@pytest.mark.parametrize("failure", ["write", "commit"])
def test_failure_rolls_back_and_preserves_context(isolated, monkeypatch, failure):
    _, factory = isolated
    at = fill(page())
    at.session_state["user_id"] = 987
    if failure == "write":
        original = users.set_skill_claim
        calls = []
        def fail(session, *args):
            original(session, *args)
            calls.append(1)
            if len(calls) == 2:
                raise RuntimeError("forced")
        monkeypatch.setattr(users, "set_skill_claim", fail)
    else:
        class FailingSession(Session):
            def commit(self):
                raise RuntimeError("forced commit")
        monkeypatch.setattr(db, "SessionLocal", sessionmaker(bind=isolated[0], class_=FailingSession))
    submit(at)
    assert at.error and not at.exception
    assert at.session_state["user_id"] == 987
    assert at.button(key="build_career_compass")
    assert at.text_input(key="onboarding_name").value == " New Student "
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(m.User)) == 0
        assert session.scalar(select(func.count()).select_from(m.UserSkillClaim)) == 0


def test_user_id_not_set_until_commit(isolated, monkeypatch):
    _, factory = isolated
    at = fill(page())
    observed = []
    from sqlalchemy import event
    def before_commit(session):
        import streamlit as st
        observed.append(st.session_state.get("user_id"))
    event.listen(factory.class_, "before_commit", before_commit)
    try:
        submit(at)
    finally:
        event.remove(factory.class_, "before_commit", before_commit)
    assert observed == [None]
    assert type(at.session_state["user_id"]) is int


def test_ui_uses_services_without_orm_or_scoring():
    tree = ast.parse((ROOT / "pages/Onboarding.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert node.module not in {"database.models", "services.scoring_service"}
        if isinstance(node, ast.Attribute):
            assert node.attr not in {"query", "calculate_career_readiness", "resulting_level"}


@pytest.mark.parametrize("index,count", [(0, 6), (1, 5), (2, 6)])
def test_each_career_renders_catalog(isolated, index, count):
    at = page()
    at.button(key=f"target_career_select_{index}").click().run()
    assert not at.exception
    assert len(at.radio) == count
    assert all(r.value == 0 for r in at.radio)
    assert all(type(k) is int for k in at.session_state["onboarding_claims"])


@pytest.mark.parametrize("kind", ["year", "career", "level", "empty"])
def test_invalid_non_widget_values_rejected_before_writes(isolated, kind):
    _, factory = isolated
    tree = ast.parse((ROOT / "pages/Onboarding.py").read_text(encoding="utf-8"))
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in {"_valid_email", "_validate_submission"}]
    import re
    scope = {"re": re}
    exec(compile(ast.Module(body=functions, type_ignores=[]), "onboarding_validation", "exec"), scope)
    profile = dict(name="Student", email="student@example.com", degree="BSc", branch="CS", year_of_study=1)
    with factory() as session:
        careers = users.list_careers(session)
        career_id = careers[0]["career_id"]
        skills = users.list_career_skills(session, career_id)
    claims = {s["skill_id"]: 0 for s in skills}
    if kind == "year": profile["year_of_study"] = 5
    if kind == "career": career_id = -1
    if kind == "level": claims[skills[0]["skill_id"]] = True
    if kind == "empty": skills = []
    with pytest.raises(ValueError):
        scope["_validate_submission"](profile, career_id, skills, claims, careers)
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(m.User)) == 0


def test_explicit_initialization_only_when_requested(isolated, monkeypatch):
    engine, factory = isolated
    db.Base.metadata.drop_all(engine)
    import database.seed as seed
    calls = []
    original = seed.seed_database
    def tracked(session):
        calls.append(1)
        return original(session)
    monkeypatch.setattr(seed, "seed_database", tracked)
    monkeypatch.setattr(db, "init_db", lambda: db.Base.metadata.create_all(engine))
    at = page()
    assert not at.exception and calls == []
    at.button(key="initialize_onboarding_database").click().run()
    assert not at.exception and calls == [1]
    at.run()
    assert calls == [1]
