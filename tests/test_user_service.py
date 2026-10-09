"""Onboarding and transaction boundaries using isolated SQLite."""

import ast
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine, select, func, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from database import db, models as m
from database.seed import seed_database
from services import user_service as service, errors
from services.career_service import UserNotFoundError, CareerNotFoundError, get_user_career_summary


@pytest.fixture
def test_engine():
    engine = create_engine("sqlite:///:memory:", poolclass=StaticPool,
                           connect_args={"check_same_thread": False})
    db.configure_sqlite_foreign_keys(engine)
    db.Base.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            seed_database(session)
            session.commit()
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def session(test_engine):
    with Session(test_engine) as session:
        yield session


def create(session, **overrides):
    values = dict(name="  Student  ", email=" Student@Example.COM ", degree="BSc", branch="CS", year_of_study=1)
    values.update(overrides)
    return service.create_user(session, **values)


def ids(session):
    return dict(careers={c.name: c.id for c in session.scalars(select(m.Career))},
                skills={s.name: s.id for s in session.scalars(select(m.Skill))},
                opportunity=session.scalar(select(m.Opportunity.id).where(m.Opportunity.title == "Data Engineering Intern")))


def snapshot(session):
    return {table.name: session.execute(select(table)).all() for table in db.Base.metadata.sorted_tables}


def test_create_normalized_profile_and_email_lookup(session):
    profile = create(session)
    assert profile == dict(user_id=1, name="Student", email="student@example.com", degree="BSc", branch="CS",
                           year_of_study=1, target_career_id=None, target_career_name=None)
    assert session.get(m.User, profile["user_id"]).created_at.tzinfo is timezone.utc
    assert service.get_user_profile(session, profile["user_id"]) == profile
    assert service.get_user_by_email(session, "  STUDENT@EXAMPLE.COM  ") == profile
    assert service.get_user_by_email(session, "missing@example.com") is None
    assert service.get_user_by_email(session, "  ") is None


def test_duplicate_normalized_email_rejected(session):
    create(session)
    with pytest.raises(ValueError, match="student@example.com already exists"):
        create(session, email="STUDENT@example.com")
    assert session.scalar(select(func.count()).select_from(m.User)) == 1


@pytest.mark.parametrize("field,value", [("name", ""), ("name", " \n "), ("email", ""), ("email", " \n ")])
def test_blank_name_or_email_rejected_before_writes(session, field, value):
    with pytest.raises(ValueError, match=f"{field} must not be blank"):
        create(session, **{field: value})
    assert not session.new
    assert session.scalar(select(func.count()).select_from(m.User)) == 0


def test_list_careers_and_target_selection_profile_switch_and_noop(session):
    catalog = service.list_careers(session)
    assert [c["name"] for c in catalog] == ["AI/ML Engineer", "Software Engineer", "Data Analyst"]
    assert [c["career_id"] for c in catalog] == sorted(c["career_id"] for c in catalog)
    assert all(set(c) == {"career_id", "name", "description"} for c in catalog)
    user_id = create(session)["user_id"]
    first = service.set_target_career(session, user_id, catalog[0]["career_id"])
    assert first == dict(user_id=user_id, previous_career_id=None, target_career_id=catalog[0]["career_id"],
                         career_name="AI/ML Engineer", changed=True)
    assert service.get_user_profile(session, user_id)["target_career_name"] == "AI/ML Engineer"
    # Load the relationship before changing its FK to exercise stale-relationship handling.
    assert session.get(m.User, user_id).target_career.name == "AI/ML Engineer"
    second = service.set_target_career(session, user_id, catalog[2]["career_id"])
    assert second["previous_career_id"] == first["target_career_id"] and second["changed"] is True
    assert service.get_user_profile(session, user_id)["target_career_name"] == "Data Analyst"
    statements = []
    event.listen(session.bind, "before_cursor_execute", lambda *args: statements.append(args[2]))
    repeated = service.set_target_career(session, user_id, catalog[2]["career_id"])
    assert repeated["changed"] is False
    assert not any(statement.lstrip().upper().startswith("UPDATE") for statement in statements)


@pytest.mark.parametrize("operation", ["profile", "target", "claim"])
def test_unknown_user(session, operation):
    catalog = ids(session)
    with pytest.raises(UserNotFoundError):
        if operation == "profile":
            service.get_user_profile(session, 99999)
        elif operation == "target":
            service.set_target_career(session, 99999, catalog["careers"]["AI/ML Engineer"])
        else:
            service.set_skill_claim(session, 99999, catalog["skills"]["SQL"], 1)


@pytest.mark.parametrize("career_id", [None, 99999])
def test_unknown_or_null_career_rejected(session, career_id):
    user_id = create(session)["user_id"]
    with pytest.raises(CareerNotFoundError):
        service.set_target_career(session, user_id, career_id)
    assert service.get_user_profile(session, user_id)["target_career_id"] is None


def test_target_switch_preserves_every_runtime_table(session):
    user_id = create(session)["user_id"]
    catalog = ids(session)
    sql_id = catalog["skills"]["SQL"]
    service.set_target_career(session, user_id, catalog["careers"]["AI/ML Engineer"])
    session.add_all([
        m.UserSkillClaim(user_id=user_id, skill_id=sql_id, claimed_level=3),
        m.AssessmentAttempt(user_id=user_id, skill_id=sql_id, form_name="fixture", status="completed",
                            resulting_level=1, completed_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
                            answers=[m.AttemptAnswer(question_reference="q1")]),
        m.RoadmapCompletion(user_id=user_id, roadmap_item_key="learn:1", completed=True),
        m.Application(user_id=user_id, opportunity_id=catalog["opportunity"], status="offer"),
        m.Evidence(user_id=user_id, skill_id=sql_id, title="Project"),
        m.ProgressEvent(user_id=user_id, event_type="fixture"),
    ])
    session.commit()
    before = snapshot(session)
    service.set_target_career(session, user_id, catalog["careers"]["Data Analyst"])
    session.flush()
    after = snapshot(session)
    assert {k: v for k, v in before.items() if k != "users"} == {k: v for k, v in after.items() if k != "users"}
    assert before["users"][0]._mapping["target_career_id"] != after["users"][0]._mapping["target_career_id"]
    assert {k: v for k, v in before["users"][0]._mapping.items() if k != "target_career_id"} == {
        k: v for k, v in after["users"][0]._mapping.items() if k != "target_career_id"}


def test_empty_career_can_be_selected_then_summary_rejects_and_user_recovers(session):
    user_id = create(session)["user_id"]
    good = ids(session)["careers"]["AI/ML Engineer"]
    empty = m.Career(name="Empty")
    session.add(empty)
    session.flush()
    assert service.set_target_career(session, user_id, empty.id)["changed"] is True
    with pytest.raises(ValueError, match="no valid skill requirements"):
        get_user_career_summary(session, user_id, empty.id)
    service.set_target_career(session, user_id, good)
    assert service.get_user_profile(session, user_id)["target_career_id"] == good


@pytest.mark.parametrize("level", [0, 3])
def test_claim_create_update_upserts_and_never_changes_evidence(session, level):
    user_id = create(session)["user_id"]
    sql_id = ids(session)["skills"]["SQL"]
    attempt = m.AssessmentAttempt(user_id=user_id, skill_id=sql_id, form_name="fixture", status="completed",
                                  resulting_level=1, completed_at=datetime(2025, 1, 1, tzinfo=timezone.utc))
    session.add(attempt)
    session.commit()
    result = service.set_skill_claim(session, user_id, sql_id, level)
    assert result == dict(user_id=user_id, skill_id=sql_id, skill_name="SQL", claimed_level=level)
    row = session.scalar(select(m.UserSkillClaim))
    first_id = row.id
    service.set_skill_claim(session, user_id, sql_id, 2)
    service.set_skill_claim(session, user_id, sql_id, 2)
    assert session.scalar(select(func.count()).select_from(m.UserSkillClaim)) == 1
    assert row.id == first_id and row.claimed_level == 2
    session.refresh(attempt)
    assert attempt.resulting_level == 1


@pytest.mark.parametrize("level", [-1, 4, True, 1.5, "2", None])
def test_invalid_claim_levels_rejected(session, level):
    user_id = create(session)["user_id"]
    sql_id = ids(session)["skills"]["SQL"]
    with pytest.raises(ValueError, match="integer from 0 to 3"):
        service.set_skill_claim(session, user_id, sql_id, level)
    assert session.scalar(select(func.count()).select_from(m.UserSkillClaim)) == 0


def test_unknown_skill(session):
    user_id = create(session)["user_id"]
    with pytest.raises(errors.SkillNotFoundError, match="Skill 99999 was not found"):
        service.set_skill_claim(session, user_id, 99999, 1)


def test_services_do_not_commit_and_reads_do_not_flush(session, monkeypatch):
    with monkeypatch.context() as context:
        context.setattr(session, "commit", Mock(side_effect=AssertionError("Service committed")))
        user_id = create(session)["user_id"]
        catalog = ids(session)
        service.set_target_career(session, user_id, catalog["careers"]["AI/ML Engineer"])
        service.set_skill_claim(session, user_id, catalog["skills"]["SQL"], 2)
    session.get(m.User, user_id).name = "Pending"
    with monkeypatch.context() as context:
        for method in ["add", "flush", "commit"]:
            context.setattr(session, method, Mock(side_effect=AssertionError(method)))
        assert service.get_user_profile(session, user_id)["name"] == "Pending"
        assert service.get_user_by_email(session, "Student@example.com")["user_id"] == user_id
        assert len(service.list_careers(session)) == 3
    session.rollback()
    assert session.scalar(select(func.count()).select_from(m.User)) == 0


def test_session_scope_commits_and_closes(test_engine, monkeypatch):
    session = Session(test_engine)
    close = Mock(wraps=session.close)
    monkeypatch.setattr(session, "close", close)
    monkeypatch.setattr(db, "SessionLocal", lambda: session)
    with db.session_scope() as scoped:
        assert scoped is session
        user_id = create(scoped)["user_id"]
    close.assert_called_once()
    assert not session.in_transaction()
    with Session(test_engine) as verify:
        assert verify.get(m.User, user_id) is not None


@pytest.mark.parametrize("failure", ["block", "commit", "interrupt"])
def test_session_scope_rolls_back_reraises_and_closes(test_engine, monkeypatch, failure):
    session = Session(test_engine)
    close = Mock(wraps=session.close)
    rollback = Mock(wraps=session.rollback)
    monkeypatch.setattr(session, "close", close)
    monkeypatch.setattr(session, "rollback", rollback)
    monkeypatch.setattr(db, "SessionLocal", lambda: session)
    error = KeyboardInterrupt("abort") if failure == "interrupt" else RuntimeError("abort")
    if failure == "commit":
        monkeypatch.setattr(session, "commit", Mock(side_effect=error))
    with pytest.raises(type(error), match="abort") as caught:
        with db.session_scope() as scoped:
            create(scoped)
            if failure != "commit":
                raise error
    assert caught.value is error
    rollback.assert_called_once()
    close.assert_called_once()
    with Session(test_engine) as verify:
        assert verify.scalar(select(func.count()).select_from(m.User)) == 0


def test_error_reexports_are_existing_classes():
    from services import career_service, opportunity_service, application_service
    for module, names in [(career_service, ["UserNotFoundError", "CareerNotFoundError"]),
                          (opportunity_service, ["OpportunityNotFoundError"]),
                          (application_service, ["ApplicationNotFoundError", "InvalidApplicationStatusError", "ApplicationNotRemovableError"])]:
        for name in names:
            assert getattr(errors, name) is getattr(module, name)


def test_no_ui_network_or_scoring_implementation():
    tree = ast.parse(Path(service.__file__).read_text(encoding="utf-8"))
    forbidden = {"streamlit", "serpapi", "requests", "httpx", "urllib", "socket"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(alias.name.split(".")[0] not in forbidden for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert (node.module or "").split(".")[0] not in forbidden
            assert node.module not in {"services.scoring_service", "services.roadmap_service", "services.opportunity_service"}


@pytest.mark.parametrize("name,count", [("AI/ML Engineer", 6), ("Software Engineer", 5), ("Data Analyst", 6)])
def test_career_skill_catalog(session, name, count, monkeypatch):
    career_id = ids(session)["careers"][name]
    with monkeypatch.context() as context:
        for method in ("flush", "commit", "add"):
            context.setattr(session, method, Mock(side_effect=AssertionError(method)))
        rows = service.list_career_skills(session, career_id)
        assert rows == service.list_career_skills(session, career_id)
    assert len(rows) == count
    assert [r["skill_id"] for r in rows] == sorted(r["skill_id"] for r in rows)
    assert all(set(r) == {"skill_id", "name", "required_level", "importance"} for r in rows)
    assert all(ids(session)["skills"][r["name"]] == r["skill_id"] for r in rows)


def test_career_skill_catalog_unknown_and_inactive(session):
    with pytest.raises(CareerNotFoundError):
        service.list_career_skills(session, 99999)
    career_id = ids(session)["careers"]["Data Analyst"]
    requirement = session.scalar(select(m.CareerSkillRequirement).where(m.CareerSkillRequirement.career_id == career_id))
    requirement.required_level = 0
    session.flush()
    assert requirement.skill_id not in {r["skill_id"] for r in service.list_career_skills(session, career_id)}
