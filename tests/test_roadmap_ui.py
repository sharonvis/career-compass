"""Roadmap UI integration against isolated SQLite and real services."""
import ast
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker
from streamlit.testing.v1 import AppTest

from database import db, models as m
from database.seed import seed_database
from services import user_service, roadmap_service, career_service, assessment_service
from data.sql_questions import SQL_QUESTIONS

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def store(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'roadmap.db'}", connect_args={"check_same_thread": False})
    db.configure_sqlite_foreign_keys(engine)
    db.Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(db, "SessionLocal", factory)
    with factory() as session:
        seed_database(session)
        uid = user_service.create_user(session, "Roadmap Student", "roadmap@example.com", "BSc", "CS", 2)["user_id"]
        cid = user_service.list_careers(session)[0]["career_id"]
        user_service.set_target_career(session, uid, cid)
        session.commit()
    yield dict(factory=factory, uid=uid, cid=cid)
    engine.dispose()


def page(store, user=True):
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=10).run()
    if user:
        at.session_state["user_id"] = store["uid"]
    return at.switch_page("pages/Roadmap.py").run()


def roadmap(store):
    with store["factory"]() as session:
        return roadmap_service.get_user_roadmap(session, store["uid"], store["cid"])


def summary(store):
    with store["factory"]() as session:
        return career_service.get_user_career_summary(session, store["uid"], store["cid"])


def improve(store):
    with store["factory"]() as session:
        skill = next(s for s in user_service.list_career_skills(session, store["cid"]) if s["name"] == "SQL")
        session.add(m.AssessmentAttempt(user_id=store["uid"], skill_id=skill["skill_id"], form_name="A", status="completed", resulting_level=1, completed_at=datetime.now(timezone.utc)))
        session.commit()
    return next(i for i in roadmap(store) if i["action_type"] == "improve" and i["skill_name"] == "SQL")


def text(at):
    return " ".join(str(x.value) for group in (at.markdown, at.caption, at.info, at.success, at.error) for x in group)


@pytest.mark.parametrize("state", ["missing", "no_career", "invalid"])
def test_safe_states(store, state):
    if state == "no_career":
        with store["factory"]() as session:
            session.get(m.User, store["uid"]).target_career_id = None
            session.commit()
    if state == "invalid":
        store["uid"] = 99999
    at = page(store, user=state != "missing")
    assert not at.exception and not at.button
    assert any(link.proto.label == "Go to Onboarding" for link in at.get("page_link"))


def test_real_items_and_no_mocks(store):
    at = page(store)
    assert not at.exception
    for item in roadmap(store):
        assert item["title"] in text(at) and item["item_key"] in text(at)
        if item["action_type"] == "assess":
            assert not any(b.key == f"roadmap_toggle_{item['item_key']}" for b in at.button)
    for mock in ("2 of 6", "4 weeks", "3 hours", "Practice SQL joins", "Explore a dataset with Python", "Data analyst foundations"):
        assert mock not in text(at)
    for item in roadmap(store):
        if item["status"] == "locked":
            assert all(b.disabled for b in at.button if b.key.endswith(item["item_key"]))


@pytest.mark.parametrize("skill", ["SQL", "Statistics"])
@pytest.mark.parametrize("reassessment", [False, True])
def test_assessment_navigation(store, skill, reassessment):
    if reassessment:
        with store["factory"]() as session:
            sid = next(s["skill_id"] for s in user_service.list_career_skills(session, store["cid"]) if s["name"] == skill)
            session.add(m.AssessmentAttempt(user_id=store["uid"], skill_id=sid, form_name="A", status="completed", resulting_level=1, completed_at=datetime.now(timezone.utc)))
            session.commit()
        item = next(i for i in roadmap(store) if i["action_type"] == "improve" and i["skill_name"] == skill)
        with db.session_scope() as session:
            roadmap_service.mark_roadmap_item_completed(session, store["uid"], item["item_key"])
    at = page(store)
    item = next(i for i in roadmap(store) if i["action_type"] == "assess" and i["skill_name"] == skill)
    assert item["title"] == f"{'Reassess' if reassessment else 'Assess'} {skill}"
    assert not any(b.key == f"roadmap_toggle_{item['item_key']}" for b in at.button)
    at.session_state["assessment_attempt_id"] = 99999
    at.button(key=f"roadmap_assess_{item['item_key']}").click().run()
    assert not at.exception and at.session_state["assessment_skill"] == skill
    assert at.button(key="assessment_start")
    with store["factory"]() as session:
        assert session.scalar(select(func.count()).select_from(m.AssessmentAttempt)) == int(reassessment)


@pytest.mark.parametrize("action", ["learn", "improve"])
def test_complete_reopen_persistence_and_scoring_neutrality(store, action):
    item = improve(store) if action == "improve" else next(i for i in roadmap(store) if i["action_type"] == "learn" and i["prerequisites_met"])
    before = summary(store)
    at = page(store)
    at.button(key=f"roadmap_toggle_{item['item_key']}").click().run()
    assert not at.exception
    fresh = page(store)
    assert fresh.button(key=f"roadmap_toggle_{item['item_key']}").label == "Reopen"
    assert next(i for i in roadmap(store) if i["item_key"] == item["item_key"])["status"] == "completed"
    assert summary(store) == before
    if action == "improve":
        assert any(i["title"] == "Reassess SQL" for i in roadmap(store))
    fresh.button(key=f"roadmap_toggle_{item['item_key']}").click().run()
    assert not fresh.exception
    assert next(i for i in roadmap(store) if i["item_key"] == item["item_key"])["status"] != "completed"
    assert summary(store) == before
    if action == "improve":
        assert not any(i["title"] == "Reassess SQL" for i in roadmap(store))


def test_write_failure_rolls_back(store, monkeypatch):
    item = improve(store)
    original = roadmap_service.mark_roadmap_item_completed
    def fail(session, uid, key):
        original(session, uid, key)
        session.flush()
        raise RuntimeError("simulated failure after SQL write")
    monkeypatch.setattr(roadmap_service, "mark_roadmap_item_completed", fail)
    at = page(store)
    at.button(key=f"roadmap_toggle_{item['item_key']}").click().run()
    assert not at.exception and at.error
    with store["factory"]() as session:
        assert session.scalar(select(func.count()).select_from(m.RoadmapCompletion)) == 0
    assert next(i for i in roadmap(store) if i["item_key"] == item["item_key"])["status"] != "completed"


def test_reload_after_real_assessment_completion(store):
    item = improve(store)
    at = page(store)
    at.button(key=f"roadmap_toggle_{item['item_key']}").click().run()
    with db.session_scope() as session:
        form = assessment_service.get_next_assessment_form(session, store["uid"], "SQL")
        attempt = assessment_service.start_assessment(session, store["uid"], "SQL", form)
        for question in SQL_QUESTIONS:
            if question["form"] == form:
                assessment_service.record_answer(session, attempt["attempt_id"], question["question_id"], question["expected_answer"])
        result = assessment_service.complete_assessment(session, attempt["attempt_id"])
        assert result["resulting_level"] >= 2
    at.run()
    assert not at.exception and "Reassess SQL" not in text(at)
    assert any(i["item_key"] == item["item_key"] and i["status"] == "completed" for i in roadmap(store))


@pytest.mark.parametrize("all_complete", [False, True])
def test_empty_and_all_displayed_complete(store, monkeypatch, all_complete):
    items = roadmap(store)[:1] if all_complete else []
    for item in items:
        item["status"] = "completed"
    monkeypatch.setattr(roadmap_service, "get_user_roadmap", lambda *args, **kwargs: items)
    at = page(store)
    assert not at.exception
    assert ("All displayed roadmap items are complete" if all_complete else "No roadmap steps") in text(at)


def test_service_boundary_and_simple_state(store):
    source = (ROOT / "pages/Roadmap.py").read_text(encoding="utf-8-sig")
    tree = ast.parse(source)
    assert "database.models" not in source and "sqlalchemy" not in source
    for forbidden in ("rank_next_actions", "calculate_confirmed_skill_gap", "get_latest_demonstrated_level", "start_assessment", "record_answer", "complete_assessment"):
        assert forbidden not in source
    assert not any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in ("query", "execute", "scalar", "scalars", "commit") for n in ast.walk(tree))
    at = page(store)
    assert all(isinstance(value, (int, bool, str, float, type(None)))
               for value in dict(at.session_state).values())
