"""
Tests for Assessment Attempt and History Service.
"""

from services.assessment_history import (
    AssessmentHistory,
    IN_PROGRESS,
    COMPLETED,
    ABANDONED,
)


# ============================================================
# TEST 1 — START ATTEMPT
# ============================================================

def test_start_attempt():

    history = AssessmentHistory()

    attempt = history.start_attempt(
        user_id="student_001",
        skill="SQL",
        form="A",
    )

    assert attempt["user_id"] == "student_001"
    assert attempt["skill"] == "SQL"
    assert attempt["form"] == "A"
    assert attempt["status"] == IN_PROGRESS
    assert attempt["completion_time"] is None
    assert attempt["resulting_level"] is None


# ============================================================
# TEST 2 — RECORD ANSWER
# ============================================================

def test_record_answer():

    history = AssessmentHistory()

    attempt = history.start_attempt(
        user_id="student_001",
        skill="SQL",
        form="A",
    )

    answer = history.record_answer(
        attempt_id=attempt["attempt_id"],
        question_id="SQL-A-001",
        submitted_answer="SELECT name FROM employees;",
        correct=True,
        error_message=None,
        runtime=0.01,
        topic="Filtering",
        difficulty="Beginner",
    )

    assert answer["question_id"] == "SQL-A-001"
    assert answer["correct"] is True
    assert answer["topic"] == "Filtering"
    assert answer["difficulty"] == "Beginner"

    answers = history.get_answers(
        attempt["attempt_id"]
    )

    assert len(answers) == 1


# ============================================================
# TEST 3 — COMPLETE ATTEMPT
# ============================================================

def test_complete_attempt():

    history = AssessmentHistory()

    attempt = history.start_attempt(
        user_id="student_001",
        skill="SQL",
        form="A",
    )

    completed = history.complete_attempt(
        attempt["attempt_id"],
        resulting_level="Beginner",
    )

    assert completed["status"] == COMPLETED
    assert completed["completion_time"] is not None
    assert completed["resulting_level"] == "Beginner"


# ============================================================
# TEST 4 — ABANDON ATTEMPT
# ============================================================

def test_abandon_attempt():

    history = AssessmentHistory()

    attempt = history.start_attempt(
        user_id="student_001",
        skill="SQL",
        form="A",
    )

    abandoned = history.abandon_attempt(
        attempt["attempt_id"]
    )

    assert abandoned["status"] == ABANDONED
    assert abandoned["completion_time"] is not None


# ============================================================
# TEST 5 — USER HISTORY
# ============================================================

def test_user_history():

    history = AssessmentHistory()

    history.start_attempt(
        user_id="student_001",
        skill="SQL",
        form="A",
    )

    history.start_attempt(
        user_id="student_001",
        skill="SQL",
        form="B",
    )

    history.start_attempt(
        user_id="student_002",
        skill="SQL",
        form="A",
    )

    student_history = history.get_history(
        "student_001"
    )

    assert len(student_history) == 2

    for attempt in student_history:
        assert attempt["user_id"] == "student_001"


# ============================================================
# TEST 6 — CANNOT ANSWER AFTER COMPLETION
# ============================================================

def test_cannot_answer_after_completion():

    history = AssessmentHistory()

    attempt = history.start_attempt(
        user_id="student_001",
        skill="SQL",
        form="A",
    )

    history.complete_attempt(
        attempt["attempt_id"],
        resulting_level="Beginner",
    )

    try:

        history.record_answer(
            attempt_id=attempt["attempt_id"],
            question_id="SQL-A-001",
            submitted_answer="SELECT * FROM employees;",
            correct=True,
            error_message=None,
            runtime=0.01,
            topic="Filtering",
            difficulty="Beginner",
        )

        assert False

    except ValueError:
        assert True