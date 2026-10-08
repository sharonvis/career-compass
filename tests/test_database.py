"""Database contracts tested exclusively against fresh in-memory SQLite engines."""

import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, configure_mappers
from sqlalchemy.pool import StaticPool

from database.db import Base, configure_sqlite_foreign_keys
from database import models as m  # Register every model before create_all().


@pytest.fixture
def test_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    configure_sqlite_foreign_keys(engine)
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def session(test_engine):
    with Session(test_engine) as session:
        yield session


@pytest.fixture
def parents(session):
    user = m.User(name="Student", email="student@example.com", degree="BSc",
                  branch="CS", year_of_study=1)
    skill = m.Skill(name="Python")
    prerequisite = m.Skill(name="Programming basics")
    career = m.Career(name="Developer")
    opportunity = m.Opportunity(title="Intern", company="Example",
                                opportunity_type="internship", source="manual")
    session.add_all([user, skill, prerequisite, career, opportunity])
    session.flush()
    attempt = m.AssessmentAttempt(user_id=user.id, skill_id=skill.id, form_name="basic")
    session.add(attempt)
    session.commit()
    return dict(user=user, skill=skill, prerequisite=prerequisite, career=career,
                opportunity=opportunity, attempt=attempt)


def make_row(model, parents, **overrides):
    """Supply valid required values so rejection tests isolate one constraint."""
    p = parents
    values = {
        m.User: dict(name="Other", email="other@example.com", degree="BSc", branch="CS", year_of_study=1),
        m.Skill: dict(name="Other skill"),
        m.Career: dict(name="Other career"),
        m.CareerSkillRequirement: dict(career_id=p["career"].id, skill_id=p["skill"].id, required_level=1, importance=1),
        m.UserSkillClaim: dict(user_id=p["user"].id, skill_id=p["skill"].id, claimed_level=1),
        m.AssessmentAttempt: dict(user_id=p["user"].id, skill_id=p["skill"].id, form_name="basic"),
        m.AttemptAnswer: dict(attempt_id=p["attempt"].id, question_reference="q1"),
        m.SkillPrerequisite: dict(skill_id=p["skill"].id, prerequisite_skill_id=p["prerequisite"].id, minimum_level=1),
        m.RoadmapCompletion: dict(user_id=p["user"].id, roadmap_item_key="python-basics"),
        m.Opportunity: dict(title="Intern", company="Example", opportunity_type="internship", source="manual"),
        m.OpportunitySearchCache: dict(cache_key="a" * 64, results={"jobs_results": []},
                                       expires_at=datetime.now(timezone.utc)),
        m.OpportunitySkill: dict(opportunity_id=p["opportunity"].id, skill_id=p["skill"].id, required_level=1),
        m.Application: dict(user_id=p["user"].id, opportunity_id=p["opportunity"].id),
        m.Evidence: dict(user_id=p["user"].id, skill_id=p["skill"].id, title="Project"),
        m.ProgressEvent: dict(user_id=p["user"].id, event_type="assessment"),
    }[model]
    values.update(overrides)
    return model(**values)


def reject(session, row, match):
    session.add(row)
    with pytest.raises(IntegrityError, match=match):
        session.flush()
    session.rollback()


def test_exact_schema(test_engine):
    assert set(inspect(test_engine).get_table_names()) == {
        "users", "skills", "careers", "career_skill_requirements", "user_skill_claims",
        "assessment_attempts", "attempt_answers", "skill_prerequisites", "roadmap_completions",
        "opportunities", "opportunity_search_cache", "opportunity_skills", "applications",
        "evidence", "progress_events",
    }


def test_foreign_keys(session, parents):
    assert session.scalar(text("PRAGMA foreign_keys")) == 1
    reject(session, make_row(m.UserSkillClaim, parents, user_id=999999), "FOREIGN KEY constraint failed")


@pytest.mark.parametrize("model,columns", [
    (m.User, ("email",)), (m.Skill, ("name",)), (m.Career, ("name",)),
    (m.CareerSkillRequirement, ("career_id", "skill_id")),
    (m.UserSkillClaim, ("user_id", "skill_id")),
    (m.SkillPrerequisite, ("skill_id", "prerequisite_skill_id")),
    (m.RoadmapCompletion, ("user_id", "roadmap_item_key")),
    (m.OpportunitySkill, ("opportunity_id", "skill_id")),
    (m.Application, ("user_id", "opportunity_id")),
    (m.AttemptAnswer, ("attempt_id", "question_reference")),
])
def test_unique_constraints(session, parents, model, columns):
    first = make_row(model, parents)
    session.add(first)
    session.commit()
    duplicate = make_row(model, parents, **{column: getattr(first, column) for column in columns})
    column_names = ", ".join(f"{model.__tablename__}.{column}" for column in columns)
    reject(session, duplicate, "UNIQUE constraint failed: " + column_names.replace(".", r"\."))


LEVEL_FIELDS = [
    (m.CareerSkillRequirement, "required_level", "ck_career_requirement_level"),
    (m.UserSkillClaim, "claimed_level", "ck_user_claim_level"),
    (m.AssessmentAttempt, "resulting_level", "ck_attempt_resulting_level"),
    (m.SkillPrerequisite, "minimum_level", "ck_prerequisite_level"),
    (m.OpportunitySkill, "required_level", "ck_opportunity_skill_level"),
]


@pytest.mark.parametrize("model,field,constraint", LEVEL_FIELDS)
@pytest.mark.parametrize("level", [0, 3, -1, 4])
def test_level_ranges(session, parents, model, field, constraint, level):
    row = make_row(model, parents, **{field: level})
    if level in (0, 3):
        session.add(row)
        session.commit()
        session.refresh(row)
        assert getattr(row, field) == level
    else:
        reject(session, row, constraint)


@pytest.mark.parametrize("model,field,constraint", [item for item in LEVEL_FIELDS if item[0] is not m.AssessmentAttempt])
def test_required_levels_cannot_be_null(session, parents, model, field, constraint):
    reject(session, make_row(model, parents, **{field: None}), "NOT NULL constraint failed")


@pytest.mark.parametrize("importance", [1, 5, 0])
def test_importance(session, parents, importance):
    row = make_row(m.CareerSkillRequirement, parents, importance=importance)
    if importance == 0:
        reject(session, row, "ck_career_requirement_importance")
    else:
        session.add(row)
        session.flush()
        assert row.importance == importance


@pytest.mark.parametrize("self_prerequisite", [False, True])
def test_prerequisite_rule(session, parents, self_prerequisite):
    row = make_row(m.SkillPrerequisite, parents)
    if self_prerequisite:
        row.prerequisite_skill_id = parents["skill"].id
        reject(session, row, "ck_prerequisite_different_skills")
    else:
        session.add(row)
        session.commit()
        session.refresh(row)
        assert row.skill is parents["skill"]
        assert row.prerequisite_skill is parents["prerequisite"]


@pytest.mark.parametrize("status", ["in_progress", "completed", "abandoned", "invalid"])
def test_assessment_status(session, parents, status):
    values = dict(status=status)
    if status == "completed":
        values.update(resulting_level=2, completed_at=datetime.now(timezone.utc))
    row = make_row(m.AssessmentAttempt, parents, **values)
    if status == "invalid":
        reject(session, row, "ck_attempt_status")
    else:
        session.add(row)
        session.commit()
        session.refresh(row)
        assert row.status == status
        if status != "completed":
            assert row.resulting_level is None and row.completed_at is None


@pytest.mark.parametrize("level,completed_at", [
    (None, datetime(2020, 1, 1, tzinfo=timezone.utc)), (2, None), (None, None),
])
def test_completed_attempt_requires_result_and_time(session, parents, level, completed_at):
    reject(session, make_row(m.AssessmentAttempt, parents, status="completed",
                            resulting_level=level, completed_at=completed_at),
           "ck_attempt_completed_consistency")


@pytest.mark.parametrize("status", ["saved", "applied", "interview", "offer", "rejected", "withdrawn", "invalid"])
def test_application_status(session, parents, status):
    row = make_row(m.Application, parents, status=status)
    if status == "invalid":
        reject(session, row, "ck_application_status")
    else:
        session.add(row)
        session.commit()
        session.refresh(row)
        assert row.status == status


@pytest.mark.parametrize("parent_key,collection,model,back_reference", [
    ("career", "skill_requirements", m.CareerSkillRequirement, "career"),
    ("user", "skill_claims", m.UserSkillClaim, "user"),
    ("user", "assessment_attempts", m.AssessmentAttempt, "user"),
    ("attempt", "answers", m.AttemptAnswer, "attempt"),
    ("opportunity", "skills", m.OpportunitySkill, "opportunity"),
    ("user", "applications", m.Application, "user"),
])
def test_relationship_round_trip(session, parents, parent_key, collection, model, back_reference):
    parent = parents[parent_key]
    row = make_row(model, parents)
    getattr(parent, collection).append(row)
    session.commit()
    parent_id, row_id = parent.id, row.id
    session.expunge_all()
    loaded_parent = session.get(type(parent), parent_id)
    loaded_child = session.get(model, row_id)
    assert loaded_child in getattr(loaded_parent, collection)
    assert getattr(loaded_child, back_reference) is loaded_parent


@pytest.mark.parametrize("parent_key,child_models", [
    ("attempt", [m.AttemptAnswer]),
    ("user", [m.UserSkillClaim, m.AssessmentAttempt, m.AttemptAnswer, m.Application,
              m.Evidence, m.RoadmapCompletion, m.ProgressEvent]),
    ("opportunity", [m.OpportunitySkill]),
    ("career", [m.CareerSkillRequirement]),
])
@pytest.mark.parametrize("load_children", [False, True])
def test_cascade_delete(session, parents, parent_key, child_models, load_children):
    for model in child_models:
        if model is not m.AssessmentAttempt:  # Already created by parents fixture.
            session.add(make_row(model, parents))
    session.commit()
    parent_type, parent_id = type(parents[parent_key]), parents[parent_key].id
    child_ids = {model: list(session.scalars(select(model.id))) for model in child_models}
    assert all(child_ids.values())
    session.expunge_all()
    parent = session.get(parent_type, parent_id)
    if load_children:
        for relation in inspect(parent_type).relationships:
            if relation.uselist:
                list(getattr(parent, relation.key))
        if parent_key == "user":
            for attempt in parent.assessment_attempts:
                list(attempt.answers)
    session.delete(parent)
    session.commit()
    session.expunge_all()
    for model, ids in child_ids.items():
        assert all(session.get(model, row_id) is None for row_id in ids)


@pytest.mark.parametrize("load_children", [False, True])
def test_application_history_blocks_opportunity_deletion(session, parents, load_children):
    application = make_row(m.Application, parents)
    opportunity_skill = make_row(m.OpportunitySkill, parents)
    session.add_all([application, opportunity_skill])
    session.commit()
    opportunity_id = parents["opportunity"].id
    application_id, opportunity_skill_id = application.id, opportunity_skill.id
    session.expunge_all()
    opportunity = session.get(m.Opportunity, opportunity_id)
    if load_children:
        list(opportunity.applications)
        list(opportunity.skills)
    session.delete(opportunity)
    with pytest.raises(IntegrityError, match="FOREIGN KEY constraint failed"):
        session.flush()
    session.rollback()
    assert session.get(m.Opportunity, opportunity_id) is not None
    assert session.get(m.Application, application_id) is not None
    assert session.get(m.OpportunitySkill, opportunity_skill_id) is not None


def test_deleting_target_career_sets_null(session, parents):
    user = parents["user"]
    user.target_career = parents["career"]
    session.commit()
    career_id = parents["career"].id
    user_id = user.id
    session.expunge_all()
    user = session.get(m.User, user_id)
    session.delete(session.get(m.Career, career_id))
    session.commit()
    session.refresh(user)
    assert user.target_career_id is None
    assert user.target_career is None


@pytest.mark.parametrize("model,field,expected", [
    (m.User, "created_at", "timestamp"), (m.UserSkillClaim, "updated_at", "timestamp"),
    (m.OpportunitySearchCache, "created_at", "timestamp"),
    (m.OpportunitySearchCache, "updated_at", "timestamp"),
    (m.Opportunity, "is_seeded", False), (m.OpportunitySkill, "is_required", True),
    (m.RoadmapCompletion, "completed", False), (m.Application, "status", "saved"),
    (m.AssessmentAttempt, "status", "in_progress"),
])
def test_defaults_after_flush(session, parents, model, field, expected):
    row = make_row(model, parents)
    session.add(row)
    session.flush()
    if expected == "timestamp":
        assert isinstance(getattr(row, field), datetime)
        assert getattr(row, field).tzinfo is timezone.utc
    else:
        assert getattr(row, field) == expected


TIMESTAMP_FIELDS = [
    (m.User, "created_at"), (m.UserSkillClaim, "updated_at"),
    (m.OpportunitySearchCache, "created_at"), (m.OpportunitySearchCache, "updated_at"),
    (m.OpportunitySearchCache, "expires_at"),
    (m.AssessmentAttempt, "started_at"), (m.AssessmentAttempt, "completed_at"),
    (m.RoadmapCompletion, "completed_at"), (m.Application, "created_at"),
    (m.Application, "updated_at"), (m.ProgressEvent, "created_at"),
]


@pytest.mark.parametrize("model,field", TIMESTAMP_FIELDS)
def test_utc_timestamp_reload(session, parents, model, field):
    original = datetime(2020, 1, 1, 12, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    row = make_row(model, parents, **{field: original})
    session.add(row)
    session.commit()
    identity = session.identity_key(instance=row)[1]
    session.expunge_all()
    primary_key = identity[0] if len(identity) == 1 else identity
    timestamp = getattr(session.get(model, primary_key), field)
    assert timestamp is not None
    assert timestamp.tzinfo is timezone.utc
    assert timestamp.utcoffset() == timedelta(0)
    assert timestamp == original.astimezone(timezone.utc)


@pytest.mark.parametrize("model,field,new_value", [
    (m.UserSkillClaim, "claimed_level", 3), (m.Application, "notes", "Updated notes"),
])
def test_updated_at_advances(session, parents, model, field, new_value):
    old = datetime(2000, 1, 1, tzinfo=timezone.utc)
    row = make_row(model, parents, updated_at=old)
    session.add(row)
    session.commit()
    session.refresh(row)
    assert row.updated_at == old
    setattr(row, field, new_value)
    session.commit()
    row_id = row.id
    session.expunge_all()
    loaded = session.get(model, row_id)
    assert getattr(loaded, field) == new_value
    assert loaded.updated_at.tzinfo is timezone.utc
    assert loaded.updated_at > old


@pytest.mark.parametrize("model,fields", [
    (m.AssessmentAttempt, ["resulting_level", "completed_at"]),
    (m.Opportunity, ["deadline", "source_url"]), (m.Evidence, ["evidence_date"]),
    (m.AttemptAnswer, ["submitted_answer", "is_correct", "error_message", "runtime_ms"]),
])
def test_nullable_fields(session, parents, model, fields):
    row = make_row(model, parents, **dict.fromkeys(fields))
    session.add(row)
    session.commit()
    session.refresh(row)
    assert all(getattr(row, field) is None for field in fields)


def test_no_derived_values_stored():
    forbidden = {"readiness", "skill_gap", "opportunity_match_band", "next_action", "demonstrated_level"}
    for mapper in Base.registry.mappers:
        assert forbidden.isdisjoint(mapper.class_.__table__.columns.keys())


def test_mapper_configuration():
    configure_mappers()
    relationships = inspect(m.SkillPrerequisite).relationships
    assert relationships["skill"].local_columns == {m.SkillPrerequisite.__table__.c.skill_id}
    assert relationships["prerequisite_skill"].local_columns == {m.SkillPrerequisite.__table__.c.prerequisite_skill_id}


def test_import_does_not_connect_or_create_tables(test_engine):
    """Execute db.py fresh, redirecting engine creation to isolated memory."""
    Base.metadata.drop_all(test_engine)
    source = Path(__file__).resolve().parents[1] / "database" / "db.py"
    spec = importlib.util.spec_from_file_location("isolated_database_setup", source)
    module = importlib.util.module_from_spec(spec)
    with patch("sqlalchemy.create_engine", return_value=test_engine), \
         patch.object(test_engine, "connect", side_effect=AssertionError("Import opened a connection")):
        spec.loader.exec_module(module)
    assert inspect(test_engine).get_table_names() == []
