"""
Database-backed assessment service for Career Compass.

Person 3 owns assessment creation, grading, completion,
attempt answers, and assessment progress events.
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from database.models import AssessmentAttempt, AttemptAnswer, Skill, User
from services.progress_service import record_progress_event
from services.sql_assessment import calculate_sql_level


LEVEL_TO_INT = {
    "Not Demonstrated": 0,
    "Beginner": 1,
    "Intermediate": 2,
    "Advanced": 3,
}


def _utc_now():
    """Return the current UTC time."""
    return datetime.now(timezone.utc)


def _verify_user(session: Session, user_id: int):
    """Make sure the user exists."""
    if session.get(User, user_id) is None:
        raise ValueError(f"User {user_id} was not found")


def _get_skill(session: Session, skill_name: str) -> Skill:
    """Find a skill by its catalog name."""
    skill = session.query(Skill).filter(Skill.name == skill_name).first()

    if skill is None:
        raise ValueError(f"Skill '{skill_name}' was not found")

    return skill
def start_assessment(session: Session, user_id: int, skill_name: str, form_name: str) -> dict:
    """
    Create a new in-progress assessment attempt.

    The caller owns the transaction and is responsible for commit/rollback.
    """

    _verify_user(session, user_id)

    if form_name not in ("A", "B"):
        raise ValueError("form_name must be 'A' or 'B'")

    skill = _get_skill(session, skill_name)

    attempt = AssessmentAttempt(
        user_id=user_id,
        skill_id=skill.id,
        form_name=form_name,
        status="in_progress",
        resulting_level=None,
        started_at=_utc_now(),
        completed_at=None,
    )

    session.add(attempt)
    session.flush()

    return {
        "attempt_id": attempt.id,
        "user_id": attempt.user_id,
        "skill_id": attempt.skill_id,
        "skill_name": skill.name,
        "form_name": attempt.form_name,
        "status": attempt.status,
        "started_at": attempt.started_at,
    }
def record_answer(
    session: Session,
    attempt_id: int,
    question_id: str,
    submitted_answer: str | None,
    correct: bool | None,
    error_message: str | None = None,
    runtime_ms: int | None = None,
) -> dict:
    """
    Record one answer for an in-progress assessment attempt.

    The caller owns the transaction.
    """

    attempt = session.get(AssessmentAttempt, attempt_id)

    if attempt is None:
        raise ValueError(f"Assessment attempt {attempt_id} was not found")

    if attempt.status != "in_progress":
        raise ValueError("Answers can only be recorded for an in-progress attempt")

    existing = session.query(AttemptAnswer).filter(
        AttemptAnswer.attempt_id == attempt_id,
        AttemptAnswer.question_reference == question_id,
    ).first()

    if existing is not None:
        raise ValueError(
            f"Question '{question_id}' has already been answered"
        )

    answer = AttemptAnswer(
        attempt_id=attempt_id,
        question_reference=question_id,
        submitted_answer=submitted_answer,
        is_correct=correct,
        error_message=error_message,
        runtime_ms=runtime_ms,
    )

    session.add(answer)
    session.flush()

    return {
        "answer_id": answer.id,
        "attempt_id": answer.attempt_id,
        "question_reference": answer.question_reference,
        "submitted_answer": answer.submitted_answer,
        "is_correct": answer.is_correct,
        "error_message": answer.error_message,
        "runtime_ms": answer.runtime_ms,
    }
def complete_assessment(
    session: Session,
    attempt_id: int,
    question_results: list[dict],
) -> dict:
    """
    Grade and complete an assessment attempt.

    The assessment result and the assessment_completed
    progress event are created in the same transaction.
    The caller owns the final commit/rollback.
    """

    attempt = session.get(AssessmentAttempt, attempt_id)

    if attempt is None:
        raise ValueError(f"Assessment attempt {attempt_id} was not found")

    if attempt.status != "in_progress":
        raise ValueError("Only an in-progress attempt can be completed")

    if not question_results:
        raise ValueError("question_results cannot be empty")

    # Calculate the estimated level using the existing
    # Person 3 SQL assessment scoring logic.
    estimated_level = calculate_sql_level(question_results)

    resulting_level = LEVEL_TO_INT[estimated_level]

    # Mark the assessment as completed.
    attempt.status = "completed"
    attempt.resulting_level = resulting_level
    attempt.completed_at = _utc_now()

    session.flush()

    # Record the Recent Activity event in the SAME transaction.
    record_progress_event(
        session=session,
        user_id=attempt.user_id,
        event_type="assessment_completed",
        subject=attempt.skill.name,
    )

    session.flush()

    return {
        "attempt_id": attempt.id,
        "user_id": attempt.user_id,
        "skill_id": attempt.skill_id,
        "skill_name": attempt.skill.name,
        "form_name": attempt.form_name,
        "status": attempt.status,
        "resulting_level": resulting_level,
        "estimated_level": estimated_level,
        "completed_at": attempt.completed_at,
    }
    def get_attempt(session: Session, attempt_id: int) -> dict:
        """Return one assessment attempt."""
    attempt = session.get(AssessmentAttempt, attempt_id)

    if attempt is None:
        raise ValueError(f"Assessment attempt {attempt_id} was not found")

    return {
        "attempt_id": attempt.id,
        "user_id": attempt.user_id,
        "skill_id": attempt.skill_id,
        "skill_name": attempt.skill.name,
        "form_name": attempt.form_name,
        "status": attempt.status,
        "resulting_level": attempt.resulting_level,
        "started_at": attempt.started_at,
        "completed_at": attempt.completed_at,
    }

def get_attempt(session: Session, attempt_id: int) -> dict:
    """Return one assessment attempt."""
    attempt = session.get(AssessmentAttempt, attempt_id)

    if attempt is None:
        raise ValueError(f"Assessment attempt {attempt_id} was not found")

    return {
        "attempt_id": attempt.id,
        "user_id": attempt.user_id,
        "skill_id": attempt.skill_id,
        "skill_name": attempt.skill.name,
        "form_name": attempt.form_name,
        "status": attempt.status,
        "resulting_level": attempt.resulting_level,
        "started_at": attempt.started_at,
        "completed_at": attempt.completed_at,
    }
def get_attempt_answers(session: Session, attempt_id: int) -> list[dict]:
    """Return all recorded answers for an assessment attempt."""

    attempt = session.get(AssessmentAttempt, attempt_id)

    if attempt is None:
        raise ValueError(f"Assessment attempt {attempt_id} was not found")

    answers = (
        session.query(AttemptAnswer)
        .filter(AttemptAnswer.attempt_id == attempt_id)
        .order_by(AttemptAnswer.id)
        .all()
    )

    return [
        {
            "answer_id": answer.id,
            "question_reference": answer.question_reference,
            "submitted_answer": answer.submitted_answer,
            "is_correct": answer.is_correct,
            "error_message": answer.error_message,
            "runtime_ms": answer.runtime_ms,
        }
        for answer in answers
    ]
def get_user_assessment_history(
    session: Session,
    user_id: int,
    skill_name: str | None = None,
) -> list[dict]:
    """Return completed assessment attempts, newest first."""

    _verify_user(session, user_id)

    query = (
        session.query(AssessmentAttempt)
        .filter(
            AssessmentAttempt.user_id == user_id,
            AssessmentAttempt.status == "completed",
        )
        .order_by(
            AssessmentAttempt.completed_at.desc(),
            AssessmentAttempt.id.desc(),
        )
    )

    if skill_name is not None:
        query = query.join(AssessmentAttempt.skill).filter(
            Skill.name == skill_name
        )

    attempts = query.all()

    return [
        {
            "attempt_id": attempt.id,
            "skill_id": attempt.skill_id,
            "skill_name": attempt.skill.name,
            "form_name": attempt.form_name,
            "status": attempt.status,
            "resulting_level": attempt.resulting_level,
            "completed_at": attempt.completed_at,
        }
        for attempt in attempts
    ]