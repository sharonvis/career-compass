"""Dashboard/My Career UI integration against isolated SQLite."""
import ast
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker
from streamlit.testing.v1 import AppTest

from database import db, models as m
from database.seed import seed_database
from services import (user_service, career_service, roadmap_service,
                      opportunity_service, application_service, progress_service)

ROOT = Path(__file__).resolve().parents[1]
PAGES = ("Dashboard.py", "my_career.py")


@pytest.fixture
def store(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'career_ui.db'}", connect_args={"check_same_thread": False})
    db.configure_sqlite_foreign_keys(engine)
    db.Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(db, "SessionLocal", factory)
    with factory() as session:
        seed_database(session)
        careers = user_service.list_careers(session)
        user = user_service.create_user(session, "Integration Student", "ui@example.com", "BSc", "CS", 2)
        uid = user["user_id"]
        cid = careers[0]["career_id"]
        user_service.set_target_career(session, uid, cid)
        skills = user_service.list_career_skills(session, cid)
        sql_id = next(s["skill_id"] for s in skills if s["name"] == "SQL")
        for skill in skills:
            user_service.set_skill_claim(session, uid, skill["skill_id"], 3)
        attempt = m.AssessmentAttempt(user_id=uid, skill_id=sql_id, form_name="A", status="completed",
                                      resulting_level=1, completed_at=datetime.now(timezone.utc))
        session.add(attempt)
        session.flush()
        attempt_id = attempt.id
        session.add(m.AttemptAnswer(attempt_id=attempt_id, question_reference="fixture", submitted_answer="answer"))
        roadmap_service.mark_roadmap_item_completed(session, uid, f"improve:{sql_id}:{attempt_id}")
        opportunity_id = session.scalar(select(m.Opportunity.id).where(m.Opportunity.title == "Data Engineering Intern"))
        saved = application_service.save_opportunity(session, uid, opportunity_id)
        application_service.update_application_status(session, uid, saved["application_id"], "interview")
        progress_service.record_progress_event(session, uid, "assessment_completed", subject="SQL")
        session.commit()
    yield dict(engine=engine, factory=factory, uid=uid, cid=cid, sql_id=sql_id, attempt_id=attempt_id, careers=careers)
    engine.dispose()


def page(name, user_id=None):
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=10).run()
    if user_id is not None:
        at.session_state["user_id"] = user_id
    return at.switch_page(f"pages/{name}").run()


def text(at):
    return "\n".join(e.value for kind in ("markdown", "caption", "info", "success", "error") for e in getattr(at, kind))


@pytest.mark.parametrize("name", PAGES)
def test_missing_user_safe(name, store):
    at = page(name)
    assert not at.exception
    assert "onboarding" in text(at).lower()
    assert any(link.proto.page == "Onboarding" or "Onboarding" in str(link.proto) for link in at.get("page_link"))
    assert not at.metric
    assert "Sharon" not in text(at)


@pytest.mark.parametrize("name", PAGES)
def test_unknown_user_safe(name, store):
    at = page(name, 99999)
    assert not at.exception and at.error
    assert not at.metric


@pytest.mark.parametrize("name", PAGES)
def test_real_profile_and_readiness(name, store):
    with store["factory"]() as session:
        summary = career_service.get_user_career_summary(session, store["uid"], store["cid"])
    at = page(name, store["uid"])
    assert not at.exception
    assert "Integration Student" in text(at)
    assert "AI/ML Engineer" in text(at)
    assert {metric.label: metric.value for metric in at.metric} == {
        "Claimed Readiness": f"{summary['claimed_readiness']:.1%}",
        "Effective Readiness": f"{summary['effective_readiness']:.1%}",
        "Assessment Coverage": f"{summary['assessment_coverage']:.1%}",
    }
    assert "Sharon" not in text(at) and "81%" not in text(at)


def test_dashboard_real_sections(store):
    with store["factory"]() as session:
        summary = career_service.get_user_career_summary(session, store["uid"], store["cid"])
        roadmap = roadmap_service.get_user_roadmap(session, store["uid"], store["cid"])
        opportunities = opportunity_service.get_ranked_opportunities(session, store["uid"], store["cid"], limit=3)
        counts = application_service.get_application_status_counts(session, store["uid"])
        activity = progress_service.list_recent_progress_events(session, store["uid"], limit=5)
    at = page("Dashboard.py", store["uid"])
    displayed = text(at)
    action = summary["next_action"]
    assert f"{action['action_type'].capitalize()} {action['skill_name']}" in displayed
    for gap in summary["confirmed_gaps"]:
        assert gap["skill_name"] in displayed and f"Gap: {gap['gap']}" in displayed
    for item in roadmap:
        assert item["title"] in displayed and item["reason"] in displayed
    completed = sum(i["status"] == "completed" for i in roadmap)
    assert f"{completed} of {len(roadmap)} displayed items completed" in displayed
    assert opportunities
    for opportunity in opportunities:
        assert opportunity["title"] in displayed and opportunity["company"] in displayed
        assert f"{opportunity['match_band'].title()} match" in displayed
        assert opportunity["deadline"].isoformat() in displayed
    for status, count in counts.items():
        assert f"{status.capitalize()}: {count}" in displayed
    for entry in activity:
        assert entry["description"] in displayed
    assert "TechCorp" not in displayed


@pytest.mark.parametrize("action_type", ["assess", "improve", "learn", None])
def test_next_action_uses_service_only(store, monkeypatch, action_type):
    original = career_service.get_user_career_summary
    def summary(*args):
        result = original(*args)
        result["next_action"] = None if action_type is None else {"action_type": action_type, "skill_name": "Catalog action sentinel"}
        return result
    monkeypatch.setattr(career_service, "get_user_career_summary", summary)
    at = page("Dashboard.py", store["uid"])
    assert not at.exception
    if action_type is None:
        assert "no next action" in text(at)
    else:
        assert f"{action_type.capitalize()} Catalog action sentinel" in text(at)
    if action_type == "assess":
        assert at.button(key="dashboard_start_assessment").disabled
        assert "next integration block" in text(at)


def test_dashboard_empty_states(store, monkeypatch):
    original = career_service.get_user_career_summary
    def summary(*args):
        result = original(*args)
        result.update(next_action=None, confirmed_gaps=[])
        return result
    monkeypatch.setattr(career_service, "get_user_career_summary", summary)
    monkeypatch.setattr(roadmap_service, "get_user_roadmap", lambda *args: [])
    monkeypatch.setattr(opportunity_service, "get_ranked_opportunities", lambda *args, **kwargs: [])
    monkeypatch.setattr(progress_service, "list_recent_progress_events", lambda *args, **kwargs: [])
    at = page("Dashboard.py", store["uid"])
    displayed = text(at)
    assert not at.exception
    for phrase in ("No confirmed skill gaps", "No roadmap items", "No matching opportunities", "No recent activity"):
        assert phrase in displayed
    for fake in ("TechCorp", "Python Basics", "Sharon", "2 days ago"):
        assert fake not in displayed


def test_dashboard_service_limits(store, monkeypatch):
    ranked = Mock(wraps=opportunity_service.get_ranked_opportunities)
    recent = Mock(wraps=progress_service.list_recent_progress_events)
    monkeypatch.setattr(opportunity_service, "get_ranked_opportunities", ranked)
    monkeypatch.setattr(progress_service, "list_recent_progress_events", recent)
    at = page("Dashboard.py", store["uid"])
    assert not at.exception
    assert ranked.call_args.kwargs == {"limit": 3}
    assert recent.call_args.kwargs == {"limit": 5}


def test_career_real_requirements_evidence_and_prerequisites(store):
    with store["factory"]() as session:
        summary = career_service.get_user_career_summary(session, store["uid"], store["cid"])
    at = page("my_career.py", store["uid"])
    displayed = text(at)
    assert not at.exception
    for skill in summary["skills"]:
        assert skill["name"] in displayed
    assert "Machine Learning Fundamentals" in displayed
    assert "Pandas/Data Handling" in displayed
    assert "Communication" not in displayed
    assert "Required: Intermediate" in displayed
    assert "Claimed: Advanced" in displayed
    assert "Demonstrated: Beginner" in displayed
    assert "Confirmed gap: 1" in displayed
    assert "Assessed" in displayed and "Unassessed" in displayed
    assert f"Latest completed attempt: #{store['attempt_id']}" in displayed
    assert "Blocked by prerequisites" in displayed
    assert len(at.button) == 3  # Change career plus only SQL/Statistics assessment actions.
    assert all(button.disabled for button in at.button if button.label != "Change career")


def test_career_switch_persists_and_dashboard_refreshes(store):
    at = page("my_career.py", store["uid"])
    target = store["careers"][2]
    at.selectbox(key="career_switch_id").set_value(target["career_id"])
    next(b for b in at.button if b.label == "Change career").click().run()
    assert not at.exception
    assert at.session_state["user_id"] == store["uid"]
    assert target["description"] in text(at)
    assert "Data Visualization" in text(at)
    with store["factory"]() as session:
        assert user_service.get_user_profile(session, store["uid"])["target_career_id"] == target["career_id"]
        attempt = session.get(m.AssessmentAttempt, store["attempt_id"])
        assert attempt.resulting_level == 1 and len(attempt.answers) == 1
        assert career_service.get_user_skill_states(session, store["uid"], [store["sql_id"]])[store["sql_id"]]["claimed_level"] == 3
        expected = career_service.get_user_career_summary(session, store["uid"], target["career_id"])
    at.switch_page("pages/Dashboard.py").run()
    assert target["name"] in text(at)
    assert at.metric[1].value == f"{expected['effective_readiness']:.1%}"


@pytest.mark.parametrize("failure", ["write", "commit"])
def test_switch_failure_keeps_career_and_user(store, monkeypatch, failure):
    at = page("my_career.py", store["uid"])
    if failure == "write":
        original = user_service.set_target_career
        def fail(*args):
            original(*args)
            raise RuntimeError("forced")
        monkeypatch.setattr(user_service, "set_target_career", fail)
    else:
        class FailingSession(Session):
            def commit(self):
                raise RuntimeError("forced commit")
        monkeypatch.setattr(db, "SessionLocal", sessionmaker(bind=store["engine"], class_=FailingSession))
    at.selectbox(key="career_switch_id").set_value(store["careers"][2]["career_id"])
    next(b for b in at.button if b.label == "Change career").click().run()
    assert not at.exception and at.error
    assert at.session_state["user_id"] == store["uid"]
    with store["factory"]() as session:
        assert user_service.get_user_profile(session, store["uid"])["target_career_id"] == store["cid"]


@pytest.mark.parametrize("name", PAGES)
def test_reads_do_not_commit_or_write_or_store_orm(store, name, monkeypatch):
    def forbidden(*args):
        raise AssertionError("Read page committed")
    monkeypatch.setattr(store["factory"].class_, "commit", forbidden)
    statements = []
    def track(conn, cursor, statement, params, context, many):
        statements.append(statement)
    event.listen(store["engine"], "before_cursor_execute", track)
    at = page(name, store["uid"])
    assert not at.exception and not at.error
    assert not any(sql.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")) for sql in statements)
    assert all(not isinstance(v, (Session, db.Base)) for v in at.session_state._state.filtered_state.values())


@pytest.mark.parametrize("name", PAGES)
def test_no_target_career_safe(store, name):
    with store["factory"]() as session:
        session.get(m.User, store["uid"]).target_career_id = None
        session.commit()
    at = page(name, store["uid"])
    assert not at.exception and at.info
    assert not at.metric


@pytest.mark.parametrize("name", PAGES)
def test_ui_has_no_queries_or_scoring(name):
    tree = ast.parse((ROOT / "pages" / name).read_text(encoding="utf-8-sig"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert node.module not in {"database.models", "sqlalchemy", "services.scoring_service"}
        if isinstance(node, ast.Attribute):
            assert node.attr not in {"query", "execute", "scalar", "scalars", "calculate_career_readiness", "calculate_confirmed_skill_gap", "calculate_assessment_coverage", "select_next_action"}
