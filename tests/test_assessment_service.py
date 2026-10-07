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