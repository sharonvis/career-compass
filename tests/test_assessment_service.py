import pytest

from database.db import SessionLocal, init_db
from database.models import AssessmentAttempt, AttemptAnswer, ProgressEvent
from database.seed import seed_database
from data.sql_questions import SQL_QUESTIONS
from data.statistics_questions import STATISTICS_QUESTIONS
from services.assessment_service import (
    start_assessment,
    record_answer,
    complete_assessment,
    get_attempt,
    get_attempt_answers,
    get_user_assessment_history,
)


def record_form_answers(session, attempt_id, skill_name, form_name):
    questions = SQL_QUESTIONS if skill_name == "SQL" else STATISTICS_QUESTIONS
    for question in questions:
        if skill_name == "SQL":
            if question["form"] != form_name:
                continue
            submitted_answer = question["expected_answer"]
        else:
            if not question["question_id"].startswith(f"STAT-{form_name}-"):
                continue
            submitted_answer = question["correct_answer"]
        record_answer(
            session=session,
            attempt_id=attempt_id,
            question_id=question["question_id"],
            submitted_answer=submitted_answer,
            correct=False,
        )


def create_test_user(session):
    """Create a simple user for assessment-service tests."""
    from database.models import User

    user = User(
    name="Test User",
    email="assessment_test@example.com",
    degree="B.Tech",
    branch="CSE",
    year_of_study=1,
)
    session.add(user)
    session.flush()
    return user


def test_start_assessment():
    init_db()

    session = SessionLocal()
    seed_database(session)

    try:
        user = create_test_user(session)

        attempt = start_assessment(
            session=session,
            user_id=user.id,
            skill_name="SQL",
            form_name="A",
        )

        assert attempt["attempt_id"] is not None
        assert attempt["user_id"] == user.id
        assert attempt["skill_name"] == "SQL"
        assert attempt["form_name"] == "A"
        assert attempt["status"] == "in_progress"

    finally:
        session.rollback()
        session.close()


def test_starting_same_skill_twice_creates_separate_attempts():
    init_db()

    session = SessionLocal()
    seed_database(session)

    try:
        user = create_test_user(session)

        first_attempt = start_assessment(
            session=session,
            user_id=user.id,
            skill_name="SQL",
            form_name="A",
        )
        second_attempt = start_assessment(
            session=session,
            user_id=user.id,
            skill_name="SQL",
            form_name="B",
        )
        third_attempt = start_assessment(
            session=session,
            user_id=user.id,
            skill_name="SQL",
            form_name="A",
        )

        assert first_attempt["attempt_id"] != second_attempt["attempt_id"]
        assert second_attempt["attempt_id"] != third_attempt["attempt_id"]
        assert session.query(AssessmentAttempt).filter(
            AssessmentAttempt.user_id == user.id,
            AssessmentAttempt.skill_id == first_attempt["skill_id"],
        ).count() == 3

    finally:
        session.rollback()
        session.close()


def test_record_answer():
    init_db()

    session = SessionLocal()
    seed_database(session)

    try:
        user = create_test_user(session)

        attempt = start_assessment(
            session=session,
            user_id=user.id,
            skill_name="SQL",
            form_name="A",
        )

        answer = record_answer(
            session=session,
            attempt_id=attempt["attempt_id"],
            question_id="SQL-A-001",
            submitted_answer="SELECT name FROM employees WHERE salary > 50000;",
            correct=False,
            runtime_ms=5,
        )

        assert answer["attempt_id"] == attempt["attempt_id"]
        assert answer["question_reference"] == "SQL-A-001"
        assert answer["is_correct"] is True
        assert answer["runtime_ms"] is not None
        assert answer["error_message"] is None

    finally:
        session.rollback()
        session.close()


def test_record_statistics_answer_uses_statistics_grader():
    init_db()

    session = SessionLocal()
    seed_database(session)

    try:
        user = create_test_user(session)
        attempt = start_assessment(
            session=session,
            user_id=user.id,
            skill_name="Statistics",
            form_name="A",
        )

        answer = record_answer(
            session=session,
            attempt_id=attempt["attempt_id"],
            question_id="STAT-A-001",
            submitted_answer="30",
            correct=False,
        )

        assert answer["is_correct"] is True
        assert answer["error_message"] is None
        assert answer["runtime_ms"] is not None

    finally:
        session.rollback()
        session.close()


def test_incorrect_sql_answer_and_unsafe_error_are_stored():
    init_db()

    session = SessionLocal()
    seed_database(session)

    try:
        user = create_test_user(session)
        attempt = start_assessment(
            session=session,
            user_id=user.id,
            skill_name="SQL",
            form_name="A",
        )

        answer = record_answer(
            session=session,
            attempt_id=attempt["attempt_id"],
            question_id="SQL-A-001",
            submitted_answer="DROP TABLE employees;",
            correct=True,
        )

        assert answer["is_correct"] is False
        assert answer["error_message"]
        assert answer["runtime_ms"] is not None

    finally:
        session.rollback()
        session.close()


def test_incorrect_statistics_answer_ignores_caller_correctness():
    init_db()

    session = SessionLocal()
    seed_database(session)

    try:
        user = create_test_user(session)
        attempt = start_assessment(
            session=session,
            user_id=user.id,
            skill_name="Statistics",
            form_name="A",
        )

        answer = record_answer(
            session=session,
            attempt_id=attempt["attempt_id"],
            question_id="STAT-A-001",
            submitted_answer="not 30",
            correct=True,
        )

        assert answer["is_correct"] is False

    finally:
        session.rollback()
        session.close()


def test_sql_form_selection_must_alternate():
    init_db()

    session = SessionLocal()
    seed_database(session)

    try:
        user = create_test_user(session)

        with pytest.raises(ValueError, match="SQL Form A is required"):
            start_assessment(session, user.id, "SQL", "B")

        start_assessment(session, user.id, "SQL", "A")

        with pytest.raises(ValueError, match="SQL Form B is required"):
            start_assessment(session, user.id, "SQL", "A")

    finally:
        session.rollback()
        session.close()


def test_complete_assessment_creates_progress_event():
    init_db()

    session = SessionLocal()
    seed_database(session)

    try:
        user = create_test_user(session)

        attempt = start_assessment(
            session=session,
            user_id=user.id,
            skill_name="SQL",
            form_name="A",
        )

        record_form_answers(session, attempt["attempt_id"], "SQL", "A")
        result = complete_assessment(
            session=session,
            attempt_id=attempt["attempt_id"],
        )

        assert result["status"] == "completed"
        assert result["resulting_level"] == 2
        assert result["estimated_level"] == "Intermediate"

        event = session.query(ProgressEvent).filter(
            ProgressEvent.user_id == user.id,
            ProgressEvent.event_type == "assessment_completed",
        ).first()

        assert event is not None
        assert event.description == "Completed SQL assessment."

    finally:
        session.rollback()
        session.close()


def test_complete_statistics_assessment_stores_resulting_level():
    init_db()

    session = SessionLocal()
    seed_database(session)

    try:
        user = create_test_user(session)
        attempt = start_assessment(
            session=session,
            user_id=user.id,
            skill_name="Statistics",
            form_name="A",
        )
        record_form_answers(session, attempt["attempt_id"], "Statistics", "A")
        result = complete_assessment(
            session=session,
            attempt_id=attempt["attempt_id"],
        )

        assert result["estimated_level"] == "Intermediate"
        assert result["resulting_level"] == 2
        assert session.get(AssessmentAttempt, attempt["attempt_id"]).resulting_level == 2

    finally:
        session.rollback()
        session.close()


def test_get_attempt_answers():
    init_db()

    session = SessionLocal()
    seed_database(session)

    try:
        user = create_test_user(session)

        attempt = start_assessment(
            session=session,
            user_id=user.id,
            skill_name="SQL",
            form_name="A",
        )

        record_answer(
            session=session,
            attempt_id=attempt["attempt_id"],
            question_id="SQL-A-001",
            submitted_answer="SELECT name FROM employees WHERE salary > 50000;",
            correct=False,
        )

        answers = get_attempt_answers(
            session=session,
            attempt_id=attempt["attempt_id"],
        )

        assert len(answers) == 1
        assert answers[0]["question_reference"] == "SQL-A-001"
        assert answers[0]["is_correct"] is True

    finally:
        session.rollback()
        session.close()


def test_get_user_assessment_history():
    init_db()

    session = SessionLocal()
    seed_database(session)

    try:
        user = create_test_user(session)

        attempt = start_assessment(
            session=session,
            user_id=user.id,
            skill_name="SQL",
            form_name="A",
        )

        record_form_answers(session, attempt["attempt_id"], "SQL", "A")
        complete_assessment(
            session=session,
            attempt_id=attempt["attempt_id"],
        )

        history = get_user_assessment_history(
            session=session,
            user_id=user.id,
            skill_name="SQL",
        )

        assert len(history) == 1
        assert history[0]["skill_name"] == "SQL"
        assert history[0]["form_name"] == "A"
        assert history[0]["resulting_level"] == 2

    finally:
        session.rollback()
        session.close()


def test_incomplete_attempt_cannot_be_completed():
    init_db()

    session = SessionLocal()
    seed_database(session)

    try:
        user = create_test_user(session)
        attempt = start_assessment(
            session=session,
            user_id=user.id,
            skill_name="SQL",
            form_name="A",
        )
        record_answer(
            session=session,
            attempt_id=attempt["attempt_id"],
            question_id="SQL-A-001",
            submitted_answer="SELECT name FROM employees WHERE salary > 50000;",
            correct=True,
        )

        with pytest.raises(ValueError, match="missing answers"):
            complete_assessment(session, attempt["attempt_id"])

        persisted_attempt = session.get(AssessmentAttempt, attempt["attempt_id"])
        assert persisted_attempt.status == "in_progress"
        assert session.query(ProgressEvent).filter(
            ProgressEvent.user_id == user.id,
            ProgressEvent.event_type == "assessment_completed",
        ).count() == 0

    finally:
        session.rollback()
        session.close()


def test_completion_scores_from_persisted_answer_records():
    init_db()

    session = SessionLocal()
    seed_database(session)

    try:
        user = create_test_user(session)
        attempt = start_assessment(
            session=session,
            user_id=user.id,
            skill_name="SQL",
            form_name="A",
        )
        record_answer(
            session=session,
            attempt_id=attempt["attempt_id"],
            question_id="SQL-A-001",
            submitted_answer="SELECT name FROM employees WHERE salary < 0;",
            correct=True,
        )
        for question in SQL_QUESTIONS:
            if question["form"] == "A" and question["question_id"] != "SQL-A-001":
                record_answer(
                    session=session,
                    attempt_id=attempt["attempt_id"],
                    question_id=question["question_id"],
                    submitted_answer=question["expected_answer"],
                )

        saved_first_answer = session.query(AttemptAnswer).filter_by(
            attempt_id=attempt["attempt_id"],
            question_reference="SQL-A-001",
        ).one()
        assert saved_first_answer.is_correct is False

        result = complete_assessment(session, attempt["attempt_id"])

        assert result["estimated_level"] == "Not Demonstrated"
        assert result["resulting_level"] == 0

    finally:
        session.rollback()
        session.close()
# UI-facing contracts use isolated SQLite, independently of legacy fixtures above.
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from database import db, models as m
from services import assessment_service as service, user_service
from unittest.mock import Mock


@pytest.fixture
def assessment_store(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'assessment_contracts.db'}")
    db.configure_sqlite_foreign_keys(engine)
    db.Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed_database(session)
        first = user_service.create_user(session, "First", "first@example.com", "BSc", "CS", 1)
        second = user_service.create_user(session, "Second", "second@example.com", "BSc", "CS", 1)
        session.commit()
        yield session, first["user_id"], second["user_id"]
    engine.dispose()


def test_supported_metadata_is_configured_and_fresh():
    expected = [{"skill_name": "SQL", "forms": ["A", "B"]}, {"skill_name": "Statistics", "forms": ["A"]}]
    assert service.list_supported_assessments() == expected
    changed = service.list_supported_assessments()
    changed[0]["forms"].clear()
    assert service.list_supported_assessments() == expected


@pytest.mark.parametrize("status", ["in_progress", "completed", "abandoned"])
def test_next_sql_form_counts_all_attempts(assessment_store, status):
    session, uid, _ = assessment_store
    assert service.get_next_assessment_form(session, uid, "SQL") == "A"
    attempt = service.start_assessment(session, uid, "SQL", "A")
    row = session.get(m.AssessmentAttempt, attempt["attempt_id"])
    row.status = status
    if status == "completed":
        from datetime import datetime, timezone
        row.resulting_level = 1
        row.completed_at = datetime.now(timezone.utc)
    session.flush()
    assert service.get_next_assessment_form(session, uid, "SQL") == "B"
    service.start_assessment(session, uid, "SQL", "B")
    assert service.get_next_assessment_form(session, uid, "SQL") == "A"


def test_statistics_next_form_stays_a(assessment_store):
    session, uid, _ = assessment_store
    assert service.get_next_assessment_form(session, uid, "Statistics") == "A"
    service.start_assessment(session, uid, "Statistics", "A")
    assert service.get_next_assessment_form(session, uid, "Statistics") == "A"


@pytest.mark.parametrize("helper", [service.get_next_assessment_form, service.get_active_assessment_attempt])
def test_helpers_reject_unsupported_skills(assessment_store, helper):
    session, uid, _ = assessment_store
    with pytest.raises(ValueError, match="Unsupported assessment"):
        helper(session, uid, "Python")


def test_active_attempt_is_newest_and_owned(assessment_store):
    session, uid, other = assessment_store
    assert service.get_active_assessment_attempt(session, uid, "SQL") is None
    first = service.start_assessment(session, uid, "SQL", "A")
    second = service.start_assessment(session, uid, "SQL", "B")
    assert service.get_active_assessment_attempt(session, uid, "SQL")["attempt_id"] == second["attempt_id"]
    assert service.get_active_assessment_attempt(session, other, "SQL") is None
    record_form_answers(session, second["attempt_id"], "SQL", "B")
    service.complete_assessment(session, second["attempt_id"])
    assert service.get_active_assessment_attempt(session, uid, "SQL")["attempt_id"] == first["attempt_id"]
    record_form_answers(session, first["attempt_id"], "SQL", "A")
    service.complete_assessment(session, first["attempt_id"])
    assert service.get_active_assessment_attempt(session, uid, "SQL") is None


@pytest.mark.parametrize("skill,form", [("SQL", "A"), ("SQL", "B"), ("Statistics", "A")])
def test_question_payload_allowlist_and_freshness(assessment_store, skill, form):
    session, uid, _ = assessment_store
    if form == "B":
        service.start_assessment(session, uid, "SQL", "A")
    attempt = service.start_assessment(session, uid, skill, form)
    questions = service.get_assessment_questions(session, uid, attempt["attempt_id"])
    assert len(questions) == 8
    common = {"question_id", "prompt", "topic", "difficulty", "input_type"}
    for question in questions:
        if skill == "SQL":
            assert set(question) == common | {"dataset_id", "schema"}
            assert question["input_type"] == "sql"
            assert all(set(table) == {"table", "columns"} for table in question["schema"])
            assert all(isinstance(col, str) for table in question["schema"] for col in table["columns"])
            question["schema"][0]["columns"].clear()
        else:
            assert set(question) == common | {"options"}
            bank = next(q for q in STATISTICS_QUESTIONS if q["question_id"] == question["question_id"])
            assert question["options"] == bank["options"]
            question["options"].clear()
    again = service.get_assessment_questions(session, uid, attempt["attempt_id"])
    assert all(q["schema"][0]["columns"] for q in again) if skill == "SQL" else all(q["options"] for q in again)


def test_question_access_rejects_wrong_owner_completed_missing(assessment_store):
    session, uid, other = assessment_store
    attempt = service.start_assessment(session, uid, "Statistics", "A")
    with pytest.raises(ValueError, match="not available"):
        service.get_assessment_questions(session, other, attempt["attempt_id"])
    with pytest.raises(ValueError, match="not found"):
        service.get_assessment_questions(session, uid, 99999)
    record_form_answers(session, attempt["attempt_id"], "Statistics", "A")
    service.complete_assessment(session, attempt["attempt_id"])
    with pytest.raises(ValueError, match="in-progress"):
        service.get_assessment_questions(session, uid, attempt["attempt_id"])


def test_ui_read_helpers_never_flush_commit_or_write(assessment_store, monkeypatch):
    session, uid, _ = assessment_store
    attempt = service.start_assessment(session, uid, "SQL", "A")
    for method in ("flush", "commit", "add"):
        monkeypatch.setattr(session, method, Mock(side_effect=AssertionError(method)))
    assert service.get_next_assessment_form(session, uid, "SQL") == "B"
    assert service.get_active_assessment_attempt(session, uid, "SQL")
    assert service.get_assessment_questions(session, uid, attempt["attempt_id"])
