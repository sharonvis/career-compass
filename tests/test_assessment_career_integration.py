import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from database import models as m
from database.db import Base, configure_sqlite_foreign_keys
from database.seed import seed_database
from data.sql_questions import SQL_QUESTIONS
from services.assessment_service import (
    complete_assessment,
    record_answer,
    start_assessment,
)
from services.career_service import get_user_career_summary


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    configure_sqlite_foreign_keys(engine)
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            seed_database(session)
            session.commit()
            yield session
    finally:
        engine.dispose()


def create_user_and_career(session):
    user = m.User(
        name="Assessment Integration Student",
        email="assessment-career-integration@example.com",
        degree="BSc",
        branch="CS",
        year_of_study=1,
    )
    session.add(user)
    session.commit()
    career = session.scalar(select(m.Career).where(m.Career.name == "AI/ML Engineer"))
    sql_skill = session.scalar(select(m.Skill).where(m.Skill.name == "SQL"))
    return user, career, sql_skill


def answer_sql_form(session, attempt_id, form_name, beginner_correct, intermediate_correct):
    questions = [question for question in SQL_QUESTIONS if question["form"] == form_name]
    intermediate_seen = 0

    for question in questions:
        if question["difficulty"] == "Beginner":
            use_correct_answer = beginner_correct
        else:
            use_correct_answer = intermediate_seen < intermediate_correct
            intermediate_seen += 1

        submitted_answer = (
            question["expected_answer"]
            if use_correct_answer
            else "SELECT 1 WHERE 1 = 0;"
        )
        record_answer(
            session=session,
            attempt_id=attempt_id,
            question_id=question["question_id"],
            submitted_answer=submitted_answer,
        )


def sql_state(summary):
    return next(skill for skill in summary["skills"] if skill["name"] == "SQL")


def test_assessment_completion_is_consumed_by_career_service(session):
    user, career, _ = create_user_and_career(session)

    form_a = start_assessment(session, user.id, "SQL", "A")
    answer_sql_form(session, form_a["attempt_id"], "A", beginner_correct=True, intermediate_correct=0)
    completed_a = complete_assessment(session, form_a["attempt_id"])
    assert completed_a["resulting_level"] == 1
    session.commit()

    summary_a = get_user_career_summary(session, user.id, career.id)
    sql_a = sql_state(summary_a)
    assert sql_a["demonstrated_level"] == 1
    assert sql_a["required_level"] == 2
    assert sql_a["gap"] == 1
    assert summary_a["next_action"] == {"action_type": "improve", "skill_name": "SQL"}

    form_b = start_assessment(session, user.id, "SQL", "B")
    answer_sql_form(session, form_b["attempt_id"], "B", beginner_correct=True, intermediate_correct=4)
    completed_b = complete_assessment(session, form_b["attempt_id"])
    assert completed_b["resulting_level"] == 2
    session.commit()

    summary_b = get_user_career_summary(session, user.id, career.id)
    sql_b = sql_state(summary_b)
    assert sql_b["demonstrated_level"] == 2
    assert sql_b["required_level"] == 2
    assert sql_b["gap"] == 0
    assert sql_b["latest_attempt_id"] == form_b["attempt_id"]
    assert sql_b["latest_attempt_id"] != form_a["attempt_id"]
    assert summary_b["next_action"] != {"action_type": "improve", "skill_name": "SQL"}

    incomplete = start_assessment(session, user.id, "SQL", "A")
    incomplete_row = session.get(m.AssessmentAttempt, incomplete["attempt_id"])
    summary_with_in_progress = get_user_career_summary(session, user.id, career.id)
    assert sql_state(summary_with_in_progress)["demonstrated_level"] == 2
    assert sql_state(summary_with_in_progress)["latest_attempt_id"] == form_b["attempt_id"]

    incomplete_row.status = "abandoned"
    session.flush()
    summary_with_abandoned = get_user_career_summary(session, user.id, career.id)
    assert sql_state(summary_with_abandoned)["demonstrated_level"] == 2
    assert sql_state(summary_with_abandoned)["latest_attempt_id"] == form_b["attempt_id"]
