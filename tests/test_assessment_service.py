from database.db import SessionLocal, init_db
from database.models import AssessmentAttempt, AttemptAnswer, ProgressEvent
from database.seed import seed_database
from services.assessment_service import (
    start_assessment,
    record_answer,
    complete_assessment,
    get_attempt,
    get_attempt_answers,
    get_user_assessment_history,
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

        assert first_attempt["attempt_id"] != second_attempt["attempt_id"]
        assert session.query(AssessmentAttempt).filter(
            AssessmentAttempt.user_id == user.id,
            AssessmentAttempt.skill_id == first_attempt["skill_id"],
        ).count() == 2

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
            question_id="A-001",
            submitted_answer="SELECT * FROM employees WHERE salary > 50000",
            correct=True,
            runtime_ms=5,
        )

        assert answer["attempt_id"] == attempt["attempt_id"]
        assert answer["question_reference"] == "A-001"
        assert answer["is_correct"] is True

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

        question_results = [
            {
                "question_id": "A-001",
                "topic": "Filtering",
                "difficulty": "Beginner",
                "correct": True,
            },
            {
                "question_id": "A-002",
                "topic": "Filtering",
                "difficulty": "Beginner",
                "correct": True,
            },
            {
                "question_id": "A-003",
                "topic": "Filtering",
                "difficulty": "Beginner",
                "correct": True,
            },
        ]

        result = complete_assessment(
            session=session,
            attempt_id=attempt["attempt_id"],
            question_results=question_results,
        )

        assert result["status"] == "completed"
        assert result["resulting_level"] == 1
        assert result["estimated_level"] == "Beginner"

        event = session.query(ProgressEvent).filter(
            ProgressEvent.user_id == user.id,
            ProgressEvent.event_type == "assessment_completed",
        ).first()

        assert event is not None
        assert event.description == "Completed SQL assessment."

    finally:
        session.rollback()
        session.close()


def test_complete_statistics_assessment_stores_resulting_level(monkeypatch):
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
        question_results = [
            {
                "question_id": f"STAT-A-{index:03}",
                "topic": "Beginner topic",
                "difficulty": "Beginner",
                "correct": index < 4,
            }
            for index in range(1, 5)
        ] + [
            {
                "question_id": f"STAT-A-{index:03}",
                "topic": "Intermediate topic",
                "difficulty": "Intermediate",
                "correct": index < 8,
            }
            for index in range(5, 9)
        ]

        def unexpected_sql_scorer(_):
            raise AssertionError("Statistics assessments must use the Statistics scorer")

        monkeypatch.setattr(
            "services.assessment_service.calculate_sql_level",
            unexpected_sql_scorer,
        )
        result = complete_assessment(
            session=session,
            attempt_id=attempt["attempt_id"],
            question_results=question_results,
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
            question_id="A-001",
            submitted_answer="SELECT * FROM employees",
            correct=True,
        )

        answers = get_attempt_answers(
            session=session,
            attempt_id=attempt["attempt_id"],
        )

        assert len(answers) == 1
        assert answers[0]["question_reference"] == "A-001"
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

        question_results = [
            {
                "question_id": "A-001",
                "topic": "Filtering",
                "difficulty": "Beginner",
                "correct": True,
            },
            {
                "question_id": "A-002",
                "topic": "Filtering",
                "difficulty": "Beginner",
                "correct": True,
            },
            {
                "question_id": "A-003",
                "topic": "Filtering",
                "difficulty": "Beginner",
                "correct": True,
            },
        ]

        complete_assessment(
            session=session,
            attempt_id=attempt["attempt_id"],
            question_results=question_results,
        )

        history = get_user_assessment_history(
            session=session,
            user_id=user.id,
            skill_name="SQL",
        )

        assert len(history) == 1
        assert history[0]["skill_name"] == "SQL"
        assert history[0]["form_name"] == "A"
        assert history[0]["resulting_level"] == 1

    finally:
        session.rollback()
        session.close()