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
# ============================================================
# TEST 7 — FIRST ATTEMPT USES FORM A
# ============================================================

def test_first_attempt_form_a():

    history = AssessmentHistory()

    next_form = history.get_next_form(
        user_id="student_001",
        skill="SQL",
    )

    assert next_form == "A"


# ============================================================
# TEST 8 — SECOND ATTEMPT USES FORM B
# ============================================================

def test_second_attempt_form_b():

    history = AssessmentHistory()

    history.start_attempt(
        user_id="student_001",
        skill="SQL",
        form="A",
    )

    next_form = history.get_next_form(
        user_id="student_001",
        skill="SQL",
    )

    assert next_form == "B"


# ============================================================
# TEST 9 — THIRD ATTEMPT USES FORM A
# ============================================================

def test_third_attempt_form_a():

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

    next_form = history.get_next_form(
        user_id="student_001",
        skill="SQL",
    )

    assert next_form == "A"


# ============================================================
# TEST 10 — DIFFERENT SKILLS HAVE SEPARATE FORM HISTORY
# ============================================================

def test_form_history_is_skill_specific():

    history = AssessmentHistory()

    history.start_attempt(
        user_id="student_001",
        skill="SQL",
        form="A",
    )

    next_sql_form = history.get_next_form(
        user_id="student_001",
        skill="SQL",
    )

    next_statistics_form = history.get_next_form(
        user_id="student_001",
        skill="Statistics",
    )

    assert next_sql_form == "B"
    assert next_statistics_form == "A"