"""Recent Activity stays explicit, atomic with actions, and scoring-neutral."""

import ast
from datetime import datetime, date, timezone, timedelta
from pathlib import Path
from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine, select, func, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from database import models as m
from database.db import Base, configure_sqlite_foreign_keys
from database.seed import seed_database
from services import progress_service as service
from services.errors import UserNotFoundError
from services.user_service import create_user, set_target_career, set_skill_claim
from services.career_service import get_user_career_summary
from services.roadmap_service import get_user_roadmap, mark_roadmap_item_completed
from services.opportunity_service import get_ranked_opportunities, get_opportunity_match
from services.application_service import save_opportunity, update_application_status, get_application_status_counts
from services.evidence_service import add_evidence


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:", poolclass=StaticPool, connect_args={"check_same_thread": False})
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
    user_id = create_user(session, "Student", "student@example.com", "BSc", "CS", 1)["user_id"]
    other_id = create_user(session, "Other", "other@example.com", "BSc", "CS", 1)["user_id"]
    session.commit()
    return dict(user_id=user_id, other_id=other_id,
                skills={s.name: s.id for s in session.scalars(select(m.Skill))},
                career_id=session.scalar(select(m.Career.id).where(m.Career.name == "AI/ML Engineer")),
                opportunity_id=session.scalar(select(m.Opportunity.id).where(m.Opportunity.title == "Data Engineering Intern")))


def record(session, catalog, **kwargs):
    values = dict(event_type="opportunity_saved", subject="Data Engineering Intern")
    values.update(kwargs)
    return service.record_progress_event(session, catalog["user_id"], **values)


CASES = [
    ("target_career_changed", "AI/ML Engineer", None, "Target career changed to AI/ML Engineer."),
    ("assessment_completed", "SQL", None, "Completed SQL assessment."),
    ("roadmap_item_completed", "Improve SQL", None, "Completed roadmap step: Improve SQL."),
    ("opportunity_saved", "Data Engineering Intern", None, "Saved Data Engineering Intern."),
    ("application_status_changed", "Data Engineering Intern", "Applied", "Application for Data Engineering Intern moved to Applied."),
    ("evidence_added", "SQL certificate", None, "Added evidence: SQL certificate."),
]


@pytest.mark.parametrize("event_type,subject,detail,expected", CASES)
def test_all_templates_and_exact_return_fields_utc(session, catalog, event_type, subject, detail, expected):
    result = record(session, catalog, event_type=event_type, subject=subject, detail=detail)
    assert set(result) == {"event_id", "user_id", "event_type", "description", "created_at"}
    assert result["description"] == expected and result["event_type"] == event_type
    assert result["created_at"].tzinfo is timezone.utc
    session.commit()
    session.expire_all()
    assert service.list_recent_progress_events(session, catalog["user_id"]) == [result]


def test_exact_event_types():
    assert service.PROGRESS_EVENT_TYPES == (
        "target_career_changed", "assessment_completed", "roadmap_item_completed", "opportunity_saved",
        "application_status_changed", "evidence_added")


@pytest.mark.parametrize("values", [
    dict(event_type="invalid"), dict(event_type="profile_created"), dict(event_type=None),
    dict(subject=None), dict(subject=" \n "), dict(subject=12), dict(subject="x" * 101),
    dict(event_type="application_status_changed", detail=None),
    dict(event_type="application_status_changed", detail=" \t "),
    dict(event_type="application_status_changed", detail="x" * 41),
    dict(event_type="application_status_changed", detail=12),
    dict(detail="Unexpected"),
])
def test_validation_before_user_query(session, catalog, monkeypatch, values):
    with monkeypatch.context() as context:
        context.setattr(session, "get", Mock(side_effect=AssertionError("Validation queried user")))
        with pytest.raises(ValueError):
            record(session, catalog, **values)
    assert not session.new and not session.dirty


def test_normalization_and_boundaries(session, catalog):
    assert record(session, catalog, detail=" \n ")["description"] == "Saved Data Engineering Intern."
    result = record(session, catalog, event_type="application_status_changed", subject="  Data\nEngineering  Intern ", detail="  In\t Review  ")
    assert result["description"] == "Application for Data Engineering Intern moved to In Review."
    result = record(session, catalog, event_type="application_status_changed", subject="x" * 100, detail="y" * 40)
    assert result["description"] == f"Application for {'x' * 100} moved to {'y' * 40}."


def test_unknown_user(session):
    with pytest.raises(UserNotFoundError):
        service.record_progress_event(session, 99999, "assessment_completed", "SQL")
    with pytest.raises(UserNotFoundError):
        service.list_recent_progress_events(session, 99999, limit=0)


def test_listing_user_scoping_newest_id_tie_and_limits(session, catalog):
    assert service.list_recent_progress_events(session, catalog["user_id"]) == []
    ids = [record(session, catalog)["event_id"] for _ in range(12)]
    stamp = datetime(2025, 1, 1, tzinfo=timezone.utc)
    for index, event_id in enumerate(ids):
        session.get(m.ProgressEvent, event_id).created_at = stamp + timedelta(days=1 if index == 0 else 0)
    service.record_progress_event(session, catalog["other_id"], "assessment_completed", "SQL")
    session.commit()
    expected = [ids[0]] + list(reversed(ids[1:]))
    assert [row["event_id"] for row in service.list_recent_progress_events(session, catalog["user_id"])] == expected[:10]
    assert [row["event_id"] for row in service.list_recent_progress_events(session, catalog["user_id"], 3)] == expected[:3]
    assert [row["event_id"] for row in service.list_recent_progress_events(session, catalog["user_id"], 50)] == expected
    assert service.list_recent_progress_events(session, catalog["user_id"], 0) == []


@pytest.mark.parametrize("limit", [-1, True, False, None, "5", 1.5, 51])
def test_invalid_limits(session, catalog, limit):
    with pytest.raises(ValueError, match="integer from 0 to 50"):
        service.list_recent_progress_events(session, catalog["user_id"], limit)


def test_events_only_touch_progress_never_commit_and_rollback(session, catalog, monkeypatch):
    touched = []
    def before_flush(session, context, instances):
        touched.extend(list(session.new) + list(session.dirty) + list(session.deleted))
    event.listen(session, "before_flush", before_flush)
    with monkeypatch.context() as context:
        context.setattr(session, "commit", Mock(side_effect=AssertionError("Service committed")))
        record(session, catalog)
    assert touched and all(isinstance(row, m.ProgressEvent) for row in touched)
    session.rollback()
    assert service.list_recent_progress_events(session, catalog["user_id"]) == []


def test_action_and_event_rollback_together_on_validation_failure(session, catalog):
    try:
        save_opportunity(session, catalog["user_id"], catalog["opportunity_id"])
        record(session, catalog)
        record(session, catalog, subject=" ")
    except ValueError:
        session.rollback()
    else:
        pytest.fail("Invalid event was accepted")
    assert session.scalar(select(func.count()).select_from(m.Application)) == 0
    assert session.scalar(select(func.count()).select_from(m.ProgressEvent)) == 0


def snapshots(session, catalog):
    user_id, career_id = catalog["user_id"], catalog["career_id"]
    return dict(summary=get_user_career_summary(session, user_id, career_id),
                roadmap=get_user_roadmap(session, user_id, career_id),
                rankings=get_ranked_opportunities(session, user_id, career_id, today=date(2025, 1, 1)),
                match=get_opportunity_match(session, user_id, career_id, catalog["opportunity_id"], today=date(2025, 1, 1)),
                counts=get_application_status_counts(session, user_id))


def test_existing_services_have_no_events_and_progress_is_neutral(session, catalog):
    user_id = catalog["user_id"]
    set_target_career(session, user_id, catalog["career_id"])
    for name, level in {"Python": 2, "SQL": 3, "Statistics": 1, "Machine Learning Fundamentals": 1,
                        "Pandas/Data Handling": 2, "Git": 1}.items():
        set_skill_claim(session, user_id, catalog["skills"][name], level)
    for name, level, day in [("Python", 2, 0), ("SQL", 1, 1)]:
        session.add(m.AssessmentAttempt(user_id=user_id, skill_id=catalog["skills"][name], form_name="fixture",
                                        status="completed", resulting_level=level,
                                        completed_at=datetime(2025, 1, 1 + day, tzinfo=timezone.utc)))
    session.flush()
    mark_roadmap_item_completed(session, user_id, "learn:999")
    application_id = save_opportunity(session, user_id, catalog["opportunity_id"])["application_id"]
    update_application_status(session, user_id, application_id, "applied")
    add_evidence(session, user_id, catalog["skills"]["SQL"], "Supporting certificate")
    session.commit()
    assert session.scalar(select(func.count()).select_from(m.ProgressEvent)) == 0
    before = snapshots(session, catalog)
    for event_type, subject, detail, expected in CASES:
        record(session, catalog, event_type=event_type, subject=subject, detail=detail)
    session.commit()
    session.expire_all()
    assert snapshots(session, catalog) == before


def test_listing_does_not_flush_pending_changes(session, catalog, monkeypatch):
    record(session, catalog)
    session.commit()
    session.get(m.User, catalog["user_id"]).name = "Pending"
    with monkeypatch.context() as context:
        context.setattr(session, "flush", Mock(side_effect=AssertionError("Read flushed")))
        assert len(service.list_recent_progress_events(session, catalog["user_id"])) == 1
    session.rollback()


def test_static_isolation_and_no_ui_network():
    core = {"scoring_service", "career_service", "roadmap_service", "opportunity_service", "application_service"}
    for path in Path(service.__file__).parent.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if path.stem != "progress_service":
                if isinstance(node, ast.Import):
                    assert all("progress_service" not in alias.name.split(".") for alias in node.names)
                elif isinstance(node, ast.ImportFrom):
                    assert "progress_service" not in (node.module or "").split(".")
                    assert all(alias.name != "progress_service" for alias in node.names)
            if path.stem in core:
                if isinstance(node, ast.Name):
                    assert node.id != "ProgressEvent"
                elif isinstance(node, ast.Attribute):
                    assert node.attr != "ProgressEvent"
                elif isinstance(node, ast.ImportFrom):
                    assert all(alias.name != "ProgressEvent" for alias in node.names)
            if path.stem == "progress_service":
                forbidden = {"streamlit", "requests", "httpx", "socket", "serpapi", "urllib", "aiohttp"}
                if isinstance(node, ast.Import):
                    assert all(alias.name.split(".")[0] not in forbidden for alias in node.names)
                elif isinstance(node, ast.ImportFrom):
                    assert (node.module or "").split(".")[0] not in forbidden
