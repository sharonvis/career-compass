"""Golden backend flow across real SQLite file transactions and fresh sessions."""

from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from database.db import Base, configure_sqlite_foreign_keys
from database import models as m
from database.seed import seed_database
from services.user_service import create_user, list_careers, set_target_career, set_skill_claim, get_user_profile
from services.career_service import get_user_career_summary, get_latest_demonstrated_level
from services.roadmap_service import get_user_roadmap, mark_roadmap_item_completed
from services.opportunity_service import get_opportunity_match, get_ranked_opportunities
from services.application_service import save_opportunity, update_application_status, update_application_notes, get_application


STAMP = datetime(2025, 1, 1, tzinfo=timezone.utc)
TODAY = date(2025, 1, 1)


@pytest.fixture
def session_factory(tmp_path):
    path = tmp_path / "integration.db"
    engine = create_engine(f"sqlite:///{path}")
    configure_sqlite_foreign_keys(engine)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory.begin() as session:
        seed_database(session)
    assert path.is_file()
    try:
        yield factory
    finally:
        engine.dispose()


def write_attempt(factory, user_id, skill_id, level, day, form_name):
    """Person 3 fixture: one attempt and its answers commit in one transaction."""
    with factory.begin() as session:
        completed_at = STAMP + timedelta(days=day)
        row = m.AssessmentAttempt(user_id=user_id, skill_id=skill_id, form_name=form_name,
                                  status="completed", resulting_level=level,
                                  started_at=completed_at - timedelta(minutes=10), completed_at=completed_at,
                                  answers=[m.AttemptAnswer(question_reference=f"{form_name}:q1",
                                                           submitted_answer="fixture", is_correct=True)])
        session.add(row)
        session.flush()
        return row.id


def persisted_state(session):
    return {
        "claims": session.execute(select(m.UserSkillClaim.__table__).order_by(m.UserSkillClaim.id)).all(),
        "attempts": session.execute(select(m.AssessmentAttempt.__table__).order_by(m.AssessmentAttempt.id)).all(),
        "answers": session.execute(select(m.AttemptAnswer.__table__).order_by(m.AttemptAnswer.id)).all(),
        "completions": session.execute(select(m.RoadmapCompletion.__table__).order_by(m.RoadmapCompletion.id)).all(),
        "opportunities": session.execute(select(m.Opportunity.__table__).order_by(m.Opportunity.id)).all(),
    }


def current(items):
    current_items = [item for item in items if item["status"] == "current"]
    assert len(current_items) == 1
    return current_items[0]


def test_full_golden_backend_flow_across_sessions(session_factory):
    factory = session_factory
    # Onboarding: every write action gets a new session and commit boundary.
    with factory.begin() as session:
        profile = create_user(session, "Student", " STUDENT@example.com ", "BSc", "CS", 1)
        user_id = profile["user_id"]
        assert profile["target_career_id"] is None
    with factory() as session:
        careers = {c["name"]: c["career_id"] for c in list_careers(session)}
        skills = {s.name: s.id for s in session.scalars(select(m.Skill))}
        opportunity_id = session.scalar(select(m.Opportunity.id).where(m.Opportunity.title == "Data Engineering Intern"))
    ai_id, analyst_id = careers["AI/ML Engineer"], careers["Data Analyst"]
    with factory.begin() as session:
        set_target_career(session, user_id, ai_id)
    claims = {"Python": 2, "SQL": 3, "Statistics": 1, "Machine Learning Fundamentals": 1,
              "Pandas/Data Handling": 2, "Git": 1}
    for name, level in claims.items():
        with factory.begin() as session:
            set_skill_claim(session, user_id, skills[name], level)
    write_attempt(factory, user_id, skills["Python"], 2, 0, "Python demo")
    with factory() as session:
        initial = get_user_career_summary(session, user_id, ai_id)
        assert initial["claimed_readiness"] == 0.8125
        assert initial["effective_readiness"] == pytest.approx(12.25 / 24)
        assert initial["assessment_coverage"] == pytest.approx(5 / 24)
        assert initial["confirmed_gaps"] == []
        assert initial["next_action"] == dict(action_type="assess", skill_name="SQL")
        assert next(s for s in initial["skills"] if s["name"] == "Python")["assessable"] is False
    with factory() as session:
        assert current(get_user_roadmap(session, user_id, ai_id))["title"] == "Assess SQL"
    with factory() as session:
        assert get_opportunity_match(session, user_id, ai_id, opportunity_id, today=TODAY)["match_band"] == "good"

    # Person 3 Form A and subsequent reads.
    form_a_id = write_attempt(factory, user_id, skills["SQL"], 1, 1, "SQL Form A")
    with factory() as session:
        form_a = get_user_career_summary(session, user_id, ai_id)
        assert form_a["claimed_readiness"] == 0.8125
        assert form_a["effective_readiness"] == pytest.approx(12.25 / 24)
        assert form_a["assessment_coverage"] == pytest.approx(9 / 24)
        assert form_a["confirmed_gaps"] == [dict(skill_name="SQL", required_level=2, demonstrated_level=1, gap=1, importance=4)]
        assert form_a["next_action"] == dict(action_type="improve", skill_name="SQL")
        step = current(get_user_roadmap(session, user_id, ai_id))
        improve_key = step["item_key"]
        assert improve_key == f"improve:{skills['SQL']}:{form_a_id}" and step["title"] == "Improve SQL"
        assert get_opportunity_match(session, user_id, ai_id, opportunity_id, today=TODAY)["match_band"] == "stretch"
    with factory.begin() as session:
        mark_roadmap_item_completed(session, user_id, improve_key)
    with factory() as session:
        assert current(get_user_roadmap(session, user_id, ai_id))["title"] == "Reassess SQL"
        assert get_latest_demonstrated_level(session, user_id, skills["SQL"]) == 1
        assert get_user_career_summary(session, user_id, ai_id) == form_a

    # Form B changes demonstrated evidence, not the user's claim.
    form_b_id = write_attempt(factory, user_id, skills["SQL"], 2, 2, "SQL Form B")
    with factory() as session:
        post_form_b = get_user_career_summary(session, user_id, ai_id)
        assert post_form_b["effective_readiness"] == pytest.approx(14.25 / 24)
        assert post_form_b["claimed_readiness"] == 0.8125
        assert post_form_b["assessment_coverage"] == pytest.approx(9 / 24)
        assert post_form_b["confirmed_gaps"] == []
        sql = next(s for s in post_form_b["skills"] if s["name"] == "SQL")
        assert sql["gap"] == 0 and sql["latest_attempt_id"] == form_b_id
        assert post_form_b["next_action"] == dict(action_type="assess", skill_name="Statistics")
        assert current(get_user_roadmap(session, user_id, ai_id))["title"] == "Assess Statistics"
        assert get_opportunity_match(session, user_id, ai_id, opportunity_id, today=TODAY)["match_band"] == "strong"
        stable_state = persisted_state(session)
        stable_profile = get_user_profile(session, user_id)

    # Save and track one opportunity with independent application transactions.
    with factory.begin() as session:
        application = save_opportunity(session, user_id, opportunity_id, today=TODAY)
        application_id = application["application_id"]
    for status in ["applied", "interview", "offer"]:
        with factory.begin() as session:
            tracked = update_application_status(session, user_id, application_id, status, today=TODAY)
            assert tracked["application_id"] == application_id and tracked["status"] == status
        with factory() as session:
            assert session.scalar(select(func.count()).select_from(m.Application)) == 1
            assert persisted_state(session) == stable_state
            assert get_user_profile(session, user_id) == stable_profile
            assert get_user_career_summary(session, user_id, ai_id) == post_form_b
    with factory.begin() as session:
        update_application_notes(session, user_id, application_id, "Offer received", today=TODAY)
    with factory() as session:
        saved_application = get_application(session, user_id, application_id, today=TODAY)
        assert saved_application["notes"] == "Offer received" and saved_application["status"] == "offer"
        assert persisted_state(session) == stable_state
    # An uncommitted UI edit can be undone across a session boundary.
    with factory() as session:
        update_application_notes(session, user_id, application_id, "Undo this", today=TODAY)
        session.rollback()
    with factory() as session:
        assert get_application(session, user_id, application_id, today=TODAY) == saved_application

    # Career switching changes only the target selection.
    with factory.begin() as session:
        set_target_career(session, user_id, analyst_id)
    with factory() as session:
        assert get_user_profile(session, user_id)["target_career_id"] == analyst_id
        assert persisted_state(session) == stable_state
        assert get_application(session, user_id, application_id, today=TODAY) == saved_application
        analyst = get_user_career_summary(session, user_id, analyst_id)
        assert analyst["effective_readiness"] == pytest.approx(10.5 / 23)
        assert analyst["claimed_readiness"] == pytest.approx(13 / 23)
        assert analyst["assessment_coverage"] == pytest.approx(8 / 23)
        assert analyst["confirmed_gaps"] == []
        assert analyst["next_action"] == dict(action_type="assess", skill_name="Statistics")
        visible = get_ranked_opportunities(session, user_id, analyst_id, today=TODAY)
        assert {o["title"] for o in visible} == {
            "Junior Data Scientist Trainee", "Data Engineering Intern", "Data Analyst Intern",
            "Business Analytics Intern", "Junior Data Analyst",
        }
        assert next(o for o in visible if o["opportunity_id"] == opportunity_id)["match_band"] == "strong"
    with factory.begin() as session:
        set_target_career(session, user_id, ai_id)
    with factory() as session:
        assert get_user_career_summary(session, user_id, ai_id) == post_form_b
        assert persisted_state(session) == stable_state
        for model, expected in [(m.UserSkillClaim, 6), (m.AssessmentAttempt, 3), (m.AttemptAnswer, 3), (m.Application, 1)]:
            assert session.scalar(select(func.count()).select_from(model)) == expected

    # Person 4 cannot delete an opportunity that has application history.
    with factory() as session:
        session.delete(session.get(m.Opportunity, opportunity_id))
        with pytest.raises(IntegrityError, match="FOREIGN KEY constraint failed"):
            session.flush()
        session.rollback()
    with factory() as session:
        assert session.get(m.Opportunity, opportunity_id) is not None
        assert get_application(session, user_id, application_id, today=TODAY) == saved_application

    # Existence-only career selection permits incomplete catalog entries.
    with factory.begin() as session:
        empty = m.Career(name="Empty requirements")
        session.add(empty)
        session.flush()
        empty_id = empty.id
    with factory.begin() as session:
        assert set_target_career(session, user_id, empty_id)["changed"] is True
    with factory() as session:
        assert get_user_profile(session, user_id)["target_career_id"] == empty_id
        with pytest.raises(ValueError, match="no valid skill requirements"):
            get_user_career_summary(session, user_id, empty_id)
    with factory.begin() as session:
        set_target_career(session, user_id, ai_id)
    with factory() as session:
        assert get_user_career_summary(session, user_id, ai_id) == post_form_b
        assert persisted_state(session) == stable_state


def test_person3_contract_retakes_are_new_rows_latest_not_highest(session_factory):
    factory = session_factory
    with factory.begin() as session:
        user_id = create_user(session, "Student", "student@example.com", "BSc", "CS", 1)["user_id"]
        sql_id = session.scalar(select(m.Skill.id).where(m.Skill.name == "SQL"))
    earlier_id = write_attempt(factory, user_id, sql_id, 2, 0, "SQL Earlier")
    with factory() as session:
        earlier = session.execute(select(m.AssessmentAttempt.__table__).where(m.AssessmentAttempt.id == earlier_id)).one()
    later_id = write_attempt(factory, user_id, sql_id, 1, 1, "SQL Retake")
    with factory() as session:
        assert earlier_id != later_id
        assert get_latest_demonstrated_level(session, user_id, sql_id) == 1
        assert session.execute(select(m.AssessmentAttempt.__table__).where(m.AssessmentAttempt.id == earlier_id)).one() == earlier
        assert session.scalar(select(func.count()).select_from(m.AssessmentAttempt)) == 2
        assert session.scalar(select(func.count()).select_from(m.AttemptAnswer)) == 2
        assert session.scalar(select(func.count()).select_from(m.Application)) == 0
        assert session.scalar(select(func.count()).select_from(m.RoadmapCompletion)) == 0
