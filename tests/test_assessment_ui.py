"""Persisted assessment UI with isolated SQLite and real backend grading."""
import ast
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session, sessionmaker
from streamlit.testing.v1 import AppTest

from database import db, models as m
from database.seed import seed_database
from data.sql_questions import SQL_QUESTIONS
from data.statistics_questions import STATISTICS_QUESTIONS
from services import assessment_service as service, user_service, career_service

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def store(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'assessment_ui.db'}", connect_args={"check_same_thread": False})
    db.configure_sqlite_foreign_keys(engine)
    db.Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(db, "SessionLocal", factory)
    with factory() as session:
        seed_database(session)
        uid = user_service.create_user(session, "Assessment Student", "student@example.com", "BSc", "CS", 2)["user_id"]
        cid = user_service.list_careers(session)[0]["career_id"]
        user_service.set_target_career(session, uid, cid)
        other = user_service.create_user(session, "Other", "other@example.com", "BSc", "CS", 2)["user_id"]
        session.commit()
    yield dict(engine=engine, factory=factory, uid=uid, cid=cid, other=other)
    engine.dispose()


def page(store, skill="SQL", user=True, attempt_id=None):
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=10).run()
    if user:
        at.session_state["user_id"] = store["uid"]
    if skill is not None:
        at.session_state["assessment_skill"] = skill
    if attempt_id is not None:
        at.session_state["assessment_attempt_id"] = attempt_id
    return at.switch_page("pages/Assessment.py").run()


def start(at):
    at.button(key="assessment_start").click().run()
    assert not at.exception
    return at.session_state["assessment_attempt_id"]


def submit(at):
    next(b for b in at.button if b.label == "Submit Assessment").click().run()
    return at


def fill(at, skill, form="A", correct=True):
    bank = SQL_QUESTIONS if skill == "SQL" else STATISTICS_QUESTIONS
    for q in bank:
        if (q.get("form") if skill == "SQL" else q["question_id"].split("-")[1]) != form:
            continue
        key = f"assessment_{at.session_state['assessment_attempt_id']}_{q['question_id']}"
        if skill == "SQL":
            at.text_area(key=key).set_value(q["expected_answer"] if correct else "SELECT 999 AS wrong")
        else:
            value = q["correct_answer"] if correct else next(o for o in q["options"] if o != q["correct_answer"])
            at.radio(key=key).set_value(value)
    return at


def counts(store):
    with store["factory"]() as session:
        return tuple(session.scalar(select(func.count()).select_from(model)) for model in (m.AssessmentAttempt, m.AttemptAnswer, m.ProgressEvent))


@pytest.mark.parametrize("skill,user", [("SQL", False), (None, True), ("Python", True), ("Communication", True)])
def test_safe_missing_or_unsupported_state(store, skill, user):
    at = page(store, skill=skill, user=user)
    assert not at.exception and at.info
    assert not at.button and counts(store) == (0, 0, 0)


@pytest.mark.parametrize("skill", ["SQL", "Statistics"])
def test_start_resume_questions_and_unanswered_validation(store, skill):
    at = page(store, skill)
    assert counts(store) == (0, 0, 0)
    aid = start(at)
    at.run()
    assert at.session_state["assessment_attempt_id"] == aid
    assert counts(store) == (1, 0, 0)
    if skill == "SQL":
        assert len(at.text_area) == 8
        assert any("employees" in c.value for c in at.code)
    else:
        assert len(at.radio) == 8
        assert all(r.value is None for r in at.radio)
        assert at.radio[0].options == STATISTICS_QUESTIONS[0]["options"]
    submit(at)
    assert not at.exception and at.error
    assert counts(store) == (1, 0, 0)
    fresh = page(store, skill)
    assert fresh.session_state["assessment_attempt_id"] == aid
    assert not any(b.key == "assessment_start" for b in fresh.button)


@pytest.mark.parametrize("skill", ["SQL", "Statistics"])
def test_complete_retakes_lower_result_and_single_event(store, skill):
    at = page(store, skill)
    aid = start(at)
    fill(at, skill)
    submit(at)
    assert not at.exception and at.success
    assert counts(store) == (1, 8, 1)
    with store["factory"]() as session:
        original = service.get_attempt(session, aid)
        assert original["status"] == "completed" and original["resulting_level"] >= 2
        sid = original["skill_id"]
        assert career_service.get_latest_demonstrated_level(session, store["uid"], sid) == original["resulting_level"]
    at.run()  # Replaying the result render must not resubmit anything.
    assert counts(store) == (1, 8, 1)
    assert not any(b.label == "Submit Assessment" for b in at.button)
    at.button(key="assessment_retake").click().run()
    assert counts(store) == (1, 8, 1)
    second = start(at)
    with store["factory"]() as session:
        attempt = service.get_attempt(session, second)
        assert attempt["form_name"] == ("B" if skill == "SQL" else "A")
    fill(at, skill, attempt["form_name"], correct=False)
    submit(at)
    assert not at.exception and at.success
    assert counts(store) == (2, 16, 2)
    with store["factory"]() as session:
        assert service.get_attempt(session, aid) == original
        assert service.get_attempt(session, second)["resulting_level"] == 0
        assert career_service.get_latest_demonstrated_level(session, store["uid"], sid) == 0
        summary = career_service.get_user_career_summary(session, store["uid"], store["cid"])
        assert next(s for s in summary["skills"] if s["skill_id"] == sid)["demonstrated_level"] == 0
    assert all(not isinstance(v, (Session, db.Base)) for v in at.session_state._state.filtered_state.values())


@pytest.mark.parametrize("failure", ["answer", "complete", "commit"])
def test_submission_failure_rolls_back_and_retry_succeeds(store, monkeypatch, failure):
    at = page(store)
    aid = start(at)
    fill(at, "SQL")
    with monkeypatch.context() as patch:
        if failure == "answer":
            original = service.record_answer
            called = []
            def fail(*args, **kwargs):
                result = original(*args, **kwargs)
                called.append(1)
                if len(called) == 2:
                    raise RuntimeError("forced")
                return result
            patch.setattr(service, "record_answer", fail)
        elif failure == "complete":
            original = service.complete_assessment
            def fail(*args):
                original(*args)
                raise RuntimeError("forced")
            patch.setattr(service, "complete_assessment", fail)
        else:
            class FailingSession(Session):
                def commit(self):
                    raise RuntimeError("forced commit")
            patch.setattr(db, "SessionLocal", sessionmaker(bind=store["engine"], class_=FailingSession))
        submit(at)
        assert not at.exception and at.error
        assert counts(store) == (1, 0, 0)
        assert at.text_area[0].value.strip()
        with store["factory"]() as session:
            assert service.get_attempt(session, aid)["status"] == "in_progress"
    submit(at)
    assert not at.exception and at.success and counts(store) == (1, 8, 1)


def test_start_commit_failure_no_id_or_attempt(store, monkeypatch):
    class FailingSession(Session):
        def commit(self):
            raise RuntimeError("commit failed")
    at = page(store)
    monkeypatch.setattr(db, "SessionLocal", sessionmaker(bind=store["engine"], class_=FailingSession))
    at.button(key="assessment_start").click().run()
    assert not at.exception and at.error
    assert "assessment_attempt_id" not in at.session_state
    assert counts(store) == (0, 0, 0)


def test_wrong_owner_fails_without_answers_or_writes(store):
    with store["factory"]() as session:
        aid = service.start_assessment(session, store["other"], "SQL", "A")["attempt_id"]
        session.commit()
    at = page(store, attempt_id=aid)
    assert not at.exception and at.error
    assert not at.text_area and not at.radio
    assert counts(store) == (1, 0, 0)


@pytest.mark.parametrize("source", ["Dashboard.py", "my_career.py"])
def test_navigation_from_integrated_pages(store, source):
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=10).run()
    at.session_state["user_id"] = store["uid"]
    at.switch_page(f"pages/{source}").run()
    if source == "Dashboard.py":
        at.button(key="dashboard_start_assessment").click().run()
    else:
        next(b for b in at.button if b.label == "Assess").click().run()
    assert not at.exception
    assert at.session_state["assessment_skill"] in {"SQL", "Statistics"}
    assert at.button(key="assessment_start")
    assert counts(store) == (0, 0, 0)


def test_safe_payloads_only_reach_ui(store, monkeypatch):
    captured = []
    original = service.get_assessment_questions
    def track(*args):
        result = original(*args)
        captured.extend(result)
        return result
    monkeypatch.setattr(service, "get_assessment_questions", track)
    at = page(store)
    start(at)
    assert captured
    assert all(not any(k in repr(q) for k in ("expected_answer", "correct_answer", "student_result", "expected_result")) for q in captured)
    assert not any("SELECT name FROM employees WHERE salary" in e.value for e in at.code)


def test_ui_does_not_grade_query_orm_or_record_activity():
    tree = ast.parse((ROOT / "pages/Assessment.py").read_text(encoding="utf-8-sig"))
    forbidden = {"database.models", "services.sql_grader", "services.sql_assessment", "services.statistics_assessment", "services.assessment_history"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert node.module not in forbidden
        if isinstance(node, ast.Attribute):
            assert node.attr not in {"query", "execute", "scalar", "scalars", "grade_sql", "grade_answer", "record_progress_event"}
        if isinstance(node, ast.Call):
            assert all(kw.arg not in {"correct", "runtime_ms", "question_results", "error_message"} for kw in node.keywords)

@pytest.mark.parametrize("skill", ["SQL", "Statistics"])
def test_start_sets_attempt_id_only_after_commit(store, monkeypatch, skill):
    from sqlalchemy import event
    at = page(store, skill)
    observed = []
    def before_commit(session):
        import streamlit as st
        observed.append(st.session_state.get("assessment_attempt_id"))
    event.listen(store["factory"].class_, "before_commit", before_commit)
    try:
        start(at)
    finally:
        event.remove(store["factory"].class_, "before_commit", before_commit)
    assert observed == [None]
    assert type(at.session_state["assessment_attempt_id"]) is int


def test_sql_whitespace_submission_writes_no_answers(store):
    at = page(store)
    start(at)
    fill(at, "SQL")
    at.text_area[0].set_value("  \n ")
    submit(at)
    assert not at.exception and at.error
    assert counts(store) == (1, 0, 0)


def test_resume_existing_recorded_answer_without_duplicate(store):
    with store["factory"]() as session:
        aid = service.start_assessment(session, store["uid"], "Statistics", "A")["attempt_id"]
        first = STATISTICS_QUESTIONS[0]
        service.record_answer(session, aid, first["question_id"], first["correct_answer"])
        session.commit()
    at = page(store, "Statistics")
    assert at.radio[0].disabled and at.radio[0].value == first["correct_answer"]
    for question in STATISTICS_QUESTIONS[1:]:
        at.radio(key=f"assessment_{aid}_{question['question_id']}").set_value(question["correct_answer"])
    submit(at)
    assert not at.exception and at.success
    assert counts(store) == (1, 8, 1)


def test_invalid_user_does_not_start(store):
    at = page(store)
    at.session_state["user_id"] = 99999
    at.run()
    assert not at.exception and at.error
    assert not at.button and counts(store) == (0, 0, 0)
