"""Application history and tracking tested with isolated seeded SQLite."""

import ast
from datetime import date, datetime, timedelta, timezone
from itertools import product
from pathlib import Path
from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from database.db import Base, configure_sqlite_foreign_keys
from database import models as m
from database.seed import seed_database
from services import application_service as service
from services.career_service import UserNotFoundError, get_user_career_summary
from services.opportunity_service import OpportunityNotFoundError


TODAY = date(2030, 1, 1)
OLD = datetime(2000, 1, 1, tzinfo=timezone.utc)


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:", poolclass=StaticPool,
                           connect_args={"check_same_thread": False})
    configure_sqlite_foreign_keys(engine)
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            seed_database(session)
            session.commit()
            yield session
    finally:
        engine.dispose()


@pytest.fixture
def catalog(session):
    career_id = session.scalar(select(m.Career.id).where(m.Career.name == "AI/ML Engineer"))
    user = m.User(name="Student", email="student@example.com", degree="BSc", branch="CS",
                  year_of_study=1, target_career_id=career_id)
    other = m.User(name="Other", email="other@example.com", degree="BSc", branch="CS", year_of_study=1)
    session.add_all([user, other])
    session.commit()
    return dict(user_id=user.id, other_id=other.id, career_id=career_id,
                opportunities={o.title: o.id for o in session.scalars(select(m.Opportunity))})


def save(session, catalog, title="Data Engineering Intern", **kwargs):
    return service.save_opportunity(session, catalog["user_id"], catalog["opportunities"][title], today=TODAY, **kwargs)


def snapshot(session):
    return {table.name: session.execute(select(table)).all() for table in Base.metadata.sorted_tables}


def test_save_plain_result_defaults_and_idempotent_status_preservation(session, catalog):
    result = save(session, catalog, notes="  Initial notes  ")
    assert set(result) == {"application_id", "user_id", "opportunity_id", "status", "notes", "created_at", "updated_at", "opportunity"}
    assert set(result["opportunity"]) == {"title", "company", "location", "opportunity_type", "deadline",
                                         "source", "source_url", "is_seeded", "is_expired"}
    assert result["status"] == "saved" and result["notes"] == "Initial notes"
    assert result["created_at"].tzinfo is timezone.utc and result["updated_at"].tzinfo is timezone.utc
    assert result["opportunity"]["source"] == "seed" and result["opportunity"]["source_url"] is None
    assert save(session, catalog) == result
    service.update_application_status(session, catalog["user_id"], result["application_id"], "interview")
    repeated = save(session, catalog)
    assert repeated["status"] == "interview" and repeated["notes"] == "Initial notes"
    repeated = save(session, catalog, notes="  Replacement  ")
    assert repeated["notes"] == "Replacement" and repeated["status"] == "interview"
    assert repeated["application_id"] == result["application_id"]
    assert session.scalar(select(func.count()).select_from(m.Application)) == 1


@pytest.mark.parametrize("notes,expected", [(None, None), ("", None), ("  \n ", None), ("  Text  ", "Text"), ("x" * 2000, "x" * 2000)])
def test_note_normalization_on_save_and_update(session, catalog, notes, expected):
    result = save(session, catalog, notes=notes)
    assert result["notes"] == expected
    result = service.update_application_notes(session, catalog["user_id"], result["application_id"], notes)
    assert result["notes"] == expected


@pytest.mark.parametrize("operation", ["save", "repeat_save", "update"])
def test_long_notes_rejected_without_mutation(session, catalog, operation):
    application_id = None
    if operation != "save":
        application_id = save(session, catalog, notes="Keep")["application_id"]
        session.commit()
    before = snapshot(session)
    with pytest.raises(ValueError, match="2000"):
        if operation == "update":
            service.update_application_notes(session, catalog["user_id"], application_id, "x" * 2001)
        else:
            save(session, catalog, notes="x" * 2001)
    assert snapshot(session) == before


@pytest.mark.parametrize("missing", ["user", "opportunity"])
def test_save_unknown_entities(session, catalog, missing):
    with pytest.raises(UserNotFoundError if missing == "user" else OpportunityNotFoundError):
        service.save_opportunity(session, 99999 if missing == "user" else catalog["user_id"],
                                  99999 if missing == "opportunity" else catalog["opportunities"]["Data Engineering Intern"])


@pytest.mark.parametrize("operation", ["get", "status", "notes", "remove"])
def test_ownership_failures_are_identical_to_missing_id(session, catalog, operation):
    result = save(session, catalog)
    session.commit()
    def call(user_id, application_id):
        if operation == "get":
            return service.get_application(session, user_id, application_id)
        if operation == "status":
            return service.update_application_status(session, user_id, application_id, "applied")
        if operation == "notes":
            return service.update_application_notes(session, user_id, application_id, "Other")
        return service.remove_saved_application(session, user_id, application_id)
    before = snapshot(session)
    messages = []
    for user_id, application_id in [(catalog["other_id"], result["application_id"]), (catalog["user_id"], 99999)]:
        with pytest.raises(service.ApplicationNotFoundError) as error:
            call(user_id, application_id)
        messages.append(str(error.value))
    assert messages == ["Application was not found"] * 2
    assert service.get_application(session, catalog["user_id"], result["application_id"], today=TODAY) == result
    assert snapshot(session) == before


def test_list_order_filter_and_other_user_exclusion(session, catalog):
    ids = [save(session, catalog, title)["application_id"] for title in list(catalog["opportunities"])[:3]]
    for index, application_id in enumerate(ids):
        row = session.get(m.Application, application_id)
        row.updated_at = OLD + timedelta(days=1 if index else 2)
        row.status = "applied" if index else "saved"
    service.save_opportunity(session, catalog["other_id"], list(catalog["opportunities"].values())[0])
    session.commit()
    results = service.list_user_applications(session, catalog["user_id"], today=TODAY)
    assert [row["application_id"] for row in results] == [ids[0], ids[2], ids[1]]
    assert [row["application_id"] for row in service.list_user_applications(session, catalog["user_id"], status="applied")] == [ids[2], ids[1]]
    assert service.list_user_applications(session, catalog["user_id"], status="offer") == []
    with pytest.raises(service.InvalidApplicationStatusError):
        service.list_user_applications(session, catalog["user_id"], status="invalid")


@pytest.mark.parametrize("before,after", list(product(service.APPLICATION_STATUSES, repeat=2)))
def test_all_status_transitions_round_trip(session, catalog, before, after):
    result = save(session, catalog)
    application_id = result["application_id"]
    row = session.get(m.Application, application_id)
    row.status, row.updated_at = before, OLD
    session.commit()
    result = service.update_application_status(session, catalog["user_id"], application_id, after)
    session.commit()
    session.expire_all()
    reloaded = service.get_application(session, catalog["user_id"], application_id)
    assert reloaded["status"] == result["status"] == after
    assert reloaded["updated_at"] == OLD if before == after else reloaded["updated_at"] > OLD
    assert reloaded["application_id"] == application_id


def test_status_constant_and_db_constraint_agree(session, catalog):
    assert service.APPLICATION_STATUSES == ("saved", "applied", "interview", "offer", "rejected", "withdrawn")
    for opportunity_id, status in zip(catalog["opportunities"].values(), service.APPLICATION_STATUSES):
        row = m.Application(user_id=catalog["user_id"], opportunity_id=opportunity_id, status=status)
        session.add(row)
        session.flush()
        session.refresh(row)
        assert row.status == status
    session.commit()
    result = service.list_user_applications(session, catalog["user_id"])[0]
    with pytest.raises(service.InvalidApplicationStatusError):
        service.update_application_status(session, catalog["user_id"], result["application_id"], "invalid")
    session.get(m.Application, result["application_id"]).status = "invalid"
    with pytest.raises(IntegrityError, match="ck_application_status"):
        session.flush()
    session.rollback()


def test_notes_changes_clear_and_noops(session, catalog, monkeypatch):
    application_id = save(session, catalog, notes="Text")["application_id"]
    session.get(m.Application, application_id).updated_at = OLD
    session.commit()
    with monkeypatch.context() as context:
        context.setattr(session, "flush", Mock(side_effect=AssertionError("No-op flushed")))
        result = service.update_application_notes(session, catalog["user_id"], application_id, "  Text  ")
        assert result["updated_at"] == OLD
        result = service.update_application_status(session, catalog["user_id"], application_id, "saved")
        assert result["updated_at"] == OLD
    for notes, expected in [("New", "New"), (None, None), ("Again", "Again"), (" \n ", None)]:
        result = service.update_application_notes(session, catalog["user_id"], application_id, notes)
        assert result["notes"] == expected
    assert result["updated_at"] > OLD


@pytest.mark.parametrize("status", service.APPLICATION_STATUSES)
def test_removal_only_saved(session, catalog, status):
    application_id = save(session, catalog)["application_id"]
    service.update_application_status(session, catalog["user_id"], application_id, status)
    session.commit()
    if status == "saved":
        assert service.remove_saved_application(session, catalog["user_id"], application_id) is None
        assert session.get(m.Application, application_id) is None
        session.rollback()
        assert session.get(m.Application, application_id) is not None
    else:
        with pytest.raises(service.ApplicationNotRemovableError, match="Only saved"):
            service.remove_saved_application(session, catalog["user_id"], application_id)
        assert session.get(m.Application, application_id).status == status


def test_status_counts_all_keys_and_empty_lists(session, catalog):
    zero = dict.fromkeys(service.APPLICATION_STATUSES, 0)
    assert service.get_application_status_counts(session, catalog["user_id"]) == zero
    assert list(service.get_application_status_counts(session, catalog["user_id"])) == list(service.APPLICATION_STATUSES)
    assert service.list_user_applications(session, catalog["user_id"]) == []
    for index, title in enumerate(list(catalog["opportunities"])[:7]):
        application_id = save(session, catalog, title)["application_id"]
        service.update_application_status(session, catalog["user_id"], application_id, service.APPLICATION_STATUSES[index % 6])
    service.save_opportunity(session, catalog["other_id"], catalog["opportunities"]["Data Engineering Intern"])
    assert service.get_application_status_counts(session, catalog["user_id"]) == dict(saved=2, applied=1, interview=1, offer=1, rejected=1, withdrawn=1)


@pytest.mark.parametrize("function", [service.list_user_applications, service.get_application_status_counts])
def test_unknown_user_for_listing_and_counts(session, function):
    with pytest.raises(UserNotFoundError):
        function(session, 99999)


@pytest.mark.parametrize("source", ["seed", "live"])
@pytest.mark.parametrize("deadline,expired", [(TODAY - timedelta(days=1), True), (TODAY, False), (None, False)])
def test_expiry_never_blocks_tracking_for_seeded_or_live(session, catalog, source, deadline, expired):
    row = m.Opportunity(title="Demo", company="Example", opportunity_type="internship", source=source,
                        source_url=None if source == "seed" else "https://example.com/job", is_seeded=source == "seed", deadline=deadline)
    session.add(row)
    session.commit()
    result = service.save_opportunity(session, catalog["user_id"], row.id, today=TODAY)
    assert result["opportunity"]["is_expired"] is expired
    assert result["opportunity"]["is_seeded"] is (source == "seed")
    application_id = result["application_id"]
    result = service.update_application_status(session, catalog["user_id"], application_id, "offer", today=TODAY)
    assert result["opportunity"]["is_expired"] is expired
    assert service.get_application(session, catalog["user_id"], application_id, today=TODAY)["opportunity"]["is_expired"] is expired
    assert service.list_user_applications(session, catalog["user_id"], today=TODAY)[0]["opportunity"]["is_expired"] is expired


def test_default_today_expiry(session, catalog):
    opportunity_id = catalog["opportunities"]["Data Engineering Intern"]
    session.get(m.Opportunity, opportunity_id).deadline = date.today() - timedelta(days=1)
    session.commit()
    assert service.save_opportunity(session, catalog["user_id"], opportunity_id)["opportunity"]["is_expired"] is True


def test_golden_flow_only_changes_applications_and_caller_can_rollback(session, catalog, monkeypatch):
    skills = {s.name: s.id for s in session.scalars(select(m.Skill))}
    for name, level in {"Python": 2, "SQL": 3, "Statistics": 1, "Machine Learning Fundamentals": 1,
                        "Pandas/Data Handling": 2, "Git": 1}.items():
        session.add(m.UserSkillClaim(user_id=catalog["user_id"], skill_id=skills[name], claimed_level=level))
    session.add(m.AssessmentAttempt(user_id=catalog["user_id"], skill_id=skills["Python"], form_name="fixture",
                                    status="completed", resulting_level=2, completed_at=OLD))
    session.commit()
    before = snapshot(session)
    career_before = get_user_career_summary(session, catalog["user_id"], catalog["career_id"])
    touched = []
    from sqlalchemy import event
    def before_flush(session, context, instances):
        touched.extend(list(session.new) + list(session.dirty) + list(session.deleted))
    event.listen(session, "before_flush", before_flush)
    with monkeypatch.context() as context:
        context.setattr(session, "commit", Mock(side_effect=AssertionError("Service committed")))
        application_id = save(session, catalog)["application_id"]
        for status in ["applied", "interview", "offer"]:
            result = service.update_application_status(session, catalog["user_id"], application_id, status)
            assert result["application_id"] == application_id and result["status"] == status
            assert session.scalar(select(func.count()).select_from(m.Application)) == 1
        service.update_application_notes(session, catalog["user_id"], application_id, "Offer received")
        save(session, catalog, notes="Confirmed offer")
        assert service.get_application_status_counts(session, catalog["user_id"])["offer"] == 1
    assert touched and all(isinstance(row, m.Application) for row in touched)
    assert get_user_career_summary(session, catalog["user_id"], catalog["career_id"]) == career_before
    after = snapshot(session)
    assert {k: v for k, v in before.items() if k != "applications"} == {k: v for k, v in after.items() if k != "applications"}
    session.rollback()
    assert snapshot(session) == before


def test_removal_never_commits_or_changes_other_rows(session, catalog, monkeypatch):
    application_id = save(session, catalog)["application_id"]
    session.commit()
    before = snapshot(session)
    with monkeypatch.context() as context:
        context.setattr(session, "commit", Mock(side_effect=AssertionError("Service committed")))
        service.remove_saved_application(session, catalog["user_id"], application_id)
    after = snapshot(session)
    assert {k: v for k, v in before.items() if k != "applications"} == {k: v for k, v in after.items() if k != "applications"}
    session.rollback()
    assert snapshot(session) == before


def test_reads_do_not_flush_pending_changes(session, catalog, monkeypatch):
    application_id = save(session, catalog)["application_id"]
    session.commit()
    session.get(m.User, catalog["user_id"]).name = "Pending"
    with monkeypatch.context() as context:
        for method in ["commit", "flush", "add"]:
            context.setattr(session, method, Mock(side_effect=AssertionError(method)))
        service.get_application(session, catalog["user_id"], application_id)
        service.list_user_applications(session, catalog["user_id"])
        service.get_application_status_counts(session, catalog["user_id"])
    session.rollback()


def test_no_ui_network_or_scoring_dependencies():
    tree = ast.parse(Path(service.__file__).read_text(encoding="utf-8"))
    forbidden = {"streamlit", "serpapi", "requests", "httpx", "urllib", "socket", "aiohttp"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(alias.name.split(".")[0] not in forbidden for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert (node.module or "").split(".")[0] not in forbidden
            assert not any(name.name.startswith(("calculate_", "classify_", "get_user_career_summary")) for name in node.names)
