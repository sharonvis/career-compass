"""Supporting evidence validation, ownership, and structural/scoring neutrality."""

import ast
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from database.db import Base, configure_sqlite_foreign_keys
from database import models as m
from database.seed import seed_database
from services import evidence_service as service, errors
from services.user_service import create_user, set_skill_claim
from services.career_service import get_user_career_summary
from services.roadmap_service import get_user_roadmap
from services.opportunity_service import get_opportunity_match, get_ranked_opportunities
from services.application_service import get_application_status_counts, save_opportunity


TODAY = date(2030, 1, 1)
FIELDS = {"evidence_id", "user_id", "skill_id", "skill_name", "title", "issuer", "url", "evidence_date"}


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:", poolclass=StaticPool,
                           connect_args={"check_same_thread": False})
    configure_sqlite_foreign_keys(engine)
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            seed_database(session)
            for row in session.scalars(select(m.Opportunity)):
                row.deadline = TODAY + timedelta(days=30)
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


def add(session, catalog, **kwargs):
    values = dict(title="SQL Project", today=TODAY)
    values.update(kwargs)
    return service.add_evidence(session, catalog["user_id"], catalog["skills"]["SQL"], **values)


def rows_snapshot(session):
    return {table.name: session.execute(select(table)).all() for table in Base.metadata.sorted_tables}


def test_add_get_exact_return_fields_and_metadata_normalization(session, catalog):
    result = add(session, catalog, title="  SQL\t  Project\n Report  ", issuer="  Example\n Academy ",
                 url="  HTTPS://example.com/certificate  ", evidence_date=TODAY)
    assert result == dict(evidence_id=1, user_id=catalog["user_id"], skill_id=catalog["skills"]["SQL"],
                           skill_name="SQL", title="SQL Project Report", issuer="Example Academy",
                           url="HTTPS://example.com/certificate", evidence_date=TODAY)
    assert set(result) == FIELDS
    assert not any(any(word in key for word in ["verified", "verification", "demonstrated", "readiness"]) for key in result)
    session.commit()
    session.expire_all()
    assert service.get_evidence(session, catalog["user_id"], result["evidence_id"]) == result


@pytest.mark.parametrize("field,value", [
    ("title", None), ("title", 1), ("title", ""), ("title", " \n\t "), ("title", "x" * 201),
    ("issuer", 1), ("issuer", "x" * 151), ("url", 1),
    ("url", "example.com/cert"), ("url", "javascript:alert(1)"), ("url", "ftp://example.com"),
    ("url", "https:///certificate"), ("url", "https://"), ("url", "https://user@"),
    ("url", "https://example.com/my cert"), ("url", "https://example.com/\tcert"),
    ("url", "https://example.com/[" + "x" * 2048), ("url", "https://[invalid"),
    ("evidence_date", TODAY + timedelta(days=1)),
    ("evidence_date", datetime(2020, 1, 1, tzinfo=timezone.utc)), ("evidence_date", "2020-01-01"),
])
def test_invalid_fields_rejected_before_writes(session, catalog, field, value):
    before = rows_snapshot(session)
    with pytest.raises(ValueError):
        add(session, catalog, **{field: value})
    assert not session.new and not session.dirty
    assert rows_snapshot(session) == before


@pytest.mark.parametrize("field,value,expected", [
    ("title", "x" * 200, "x" * 200), ("title", " \n x  \t y ", "x y"),
    ("issuer", None, None), ("issuer", " \t ", None), ("issuer", "x" * 150, "x" * 150),
    ("url", None, None), ("url", " \n ", None), ("url", "HTTP://example.com", "HTTP://example.com"),
    ("url", "HTTPS://example.com", "HTTPS://example.com"),
    ("url", "https://example.com/" + "x" * (2048 - len("https://example.com/")),
     "https://example.com/" + "x" * (2048 - len("https://example.com/"))),
    ("evidence_date", None, None), ("evidence_date", date.min, date.min), ("evidence_date", TODAY, TODAY),
])
def test_boundaries_and_optional_values_accepted(session, catalog, field, value, expected):
    result = add(session, catalog, **{field: value})
    assert result[field] == expected


def test_default_today_validation(session, catalog):
    with pytest.raises(ValueError, match="future"):
        service.add_evidence(session, catalog["user_id"], catalog["skills"]["SQL"], "Future",
                              evidence_date=date.today() + timedelta(days=1))


def test_add_validation_order_user_then_skill(session, catalog):
    with pytest.raises(ValueError, match="title"):
        service.add_evidence(session, 99999, 99999, " ")
    with pytest.raises(errors.UserNotFoundError):
        service.add_evidence(session, 99999, 99999, "Valid")
    with pytest.raises(errors.SkillNotFoundError):
        service.add_evidence(session, catalog["user_id"], 99999, "Valid")


def test_duplicates_normalized_multiple_rows_and_lowest_id(session, catalog):
    first = add(session, catalog, title=" SQL   Project ", issuer=" Demo ", url=" https://example.com ", evidence_date=TODAY)
    repeated = add(session, catalog, title="SQL\nProject", issuer="Demo", url="https://example.com", evidence_date=TODAY)
    assert repeated == first
    duplicate = m.Evidence(user_id=catalog["user_id"], skill_id=catalog["skills"]["SQL"], title="SQL Project",
                            issuer="Demo", url="https://example.com", evidence_date=TODAY)
    session.add(duplicate)
    session.commit()
    assert add(session, catalog, issuer="Demo", url="https://example.com", evidence_date=TODAY)["evidence_id"] == first["evidence_id"]
    different_date = add(session, catalog, issuer="Demo", url="https://example.com", evidence_date=TODAY - timedelta(days=1))
    assert different_date["evidence_id"] != first["evidence_id"]
    different_title = add(session, catalog, title="Another project")
    assert different_title["evidence_id"] != first["evidence_id"]
    assert session.scalar(select(func.count()).select_from(m.Evidence)) == 4


def test_null_duplicate_identity(session, catalog):
    first = add(session, catalog, issuer=" ", url=" ")
    assert add(session, catalog) == first
    assert session.scalar(select(func.count()).select_from(m.Evidence)) == 1


@pytest.mark.parametrize("operation", ["get", "update", "delete"])
def test_missing_and_wrong_owner_hidden_with_same_message(session, catalog, operation):
    result = add(session, catalog)
    session.commit()
    before = rows_snapshot(session)
    function = {"get": service.get_evidence, "update": service.update_evidence, "delete": service.delete_evidence}[operation]
    messages = []
    for user_id, evidence_id in [(catalog["other_id"], result["evidence_id"]), (catalog["user_id"], 99999)]:
        with pytest.raises(errors.EvidenceNotFoundError) as caught:
            function(session, user_id, evidence_id)
        messages.append(str(caught.value))
    assert messages == ["Evidence was not found"] * 2
    assert rows_snapshot(session) == before


def test_list_filter_user_ownership_and_explicit_null_date_order(session, catalog):
    assert service.list_user_evidence(session, catalog["user_id"]) == []
    a = add(session, catalog, title="Undated A")
    b = add(session, catalog, title="Dated B", evidence_date=TODAY)
    c = add(session, catalog, title="Dated C", evidence_date=TODAY - timedelta(days=1))
    d = add(session, catalog, title="Dated D", evidence_date=TODAY)
    e = add(session, catalog, title="Undated E")
    other_skill = service.add_evidence(session, catalog["user_id"], catalog["skills"]["Python"], "Python")
    service.add_evidence(session, catalog["other_id"], catalog["skills"]["SQL"], "Other user", evidence_date=TODAY, today=TODAY)
    result = service.list_user_evidence(session, catalog["user_id"])
    assert [row["evidence_id"] for row in result] == [d["evidence_id"], b["evidence_id"], c["evidence_id"], other_skill["evidence_id"], e["evidence_id"], a["evidence_id"]]
    filtered = service.list_user_evidence(session, catalog["user_id"], catalog["skills"]["SQL"])
    assert [row["evidence_id"] for row in filtered] == [d["evidence_id"], b["evidence_id"], c["evidence_id"], e["evidence_id"], a["evidence_id"]]
    assert service.list_user_evidence(session, catalog["user_id"], catalog["skills"]["Git"]) == []
    with pytest.raises(errors.SkillNotFoundError):
        service.list_user_evidence(session, catalog["user_id"], 99999)
    with pytest.raises(errors.UserNotFoundError):
        service.list_user_evidence(session, 99999, 99999)


@pytest.mark.parametrize("field,value,expected", [
    ("title", " New  Title ", "New Title"), ("issuer", " New\nIssuer ", "New Issuer"),
    ("issuer", None, None), ("url", " HTTPS://example.com/new ", "HTTPS://example.com/new"),
    ("url", None, None), ("evidence_date", TODAY - timedelta(days=1), TODAY - timedelta(days=1)),
    ("evidence_date", None, None),
])
def test_partial_update_and_optional_clear_preserve_other_fields(session, catalog, field, value, expected):
    first = add(session, catalog, issuer="Issuer", url="https://example.com", evidence_date=TODAY)
    result = service.update_evidence(session, catalog["user_id"], first["evidence_id"], today=TODAY, **{field: value})
    assert result == dict(first, **{field: expected})
    session.commit()
    assert service.get_evidence(session, catalog["user_id"], first["evidence_id"]) == result


@pytest.mark.parametrize("fields", [dict(title=None), dict(title=" "), dict(issuer="x" * 151),
                                    dict(url="javascript:bad"), dict(evidence_date=TODAY + timedelta(days=1))])
def test_update_validates_all_fields_before_lookup_and_assignments(session, catalog, fields):
    with pytest.raises(ValueError):
        service.update_evidence(session, 99999, 99999, today=TODAY, **fields)
    first = add(session, catalog)
    fields = dict(fields)
    if "title" not in fields:
        fields["title"] = "Do not change"
    with pytest.raises(ValueError):
        service.update_evidence(session, catalog["user_id"], first["evidence_id"], today=TODAY, **fields)
    assert service.get_evidence(session, catalog["user_id"], first["evidence_id"]) == first
    assert not session.dirty


def test_no_field_or_same_normalized_value_update_is_quiet_noop(session, catalog, monkeypatch):
    first = add(session, catalog, issuer="Issuer", url="https://example.com", evidence_date=TODAY)
    session.commit()
    with monkeypatch.context() as context:
        context.setattr(session, "flush", Mock(side_effect=AssertionError("No-op flushed")))
        assert service.update_evidence(session, catalog["user_id"], first["evidence_id"]) == first
        assert service.update_evidence(session, catalog["user_id"], first["evidence_id"], title=" SQL  Project ",
                                        issuer=" Issuer ", url=" https://example.com ", evidence_date=TODAY, today=TODAY) == first
    assert not session.dirty


def test_delete_only_evidence_and_delete_twice(session, catalog):
    first = add(session, catalog)
    session.commit()
    before = rows_snapshot(session)
    assert service.delete_evidence(session, catalog["user_id"], first["evidence_id"]) is None
    with pytest.raises(errors.EvidenceNotFoundError):
        service.delete_evidence(session, catalog["user_id"], first["evidence_id"])
    after = rows_snapshot(session)
    assert {k: v for k, v in before.items() if k != "evidence"} == {k: v for k, v in after.items() if k != "evidence"}
    session.rollback()
    assert rows_snapshot(session) == before


def test_writes_only_touch_evidence_never_commit_and_rollback(session, catalog, monkeypatch):
    before = rows_snapshot(session)
    touched = []
    def before_flush(session, context, instances):
        touched.extend(list(session.new) + list(session.dirty) + list(session.deleted))
    event.listen(session, "before_flush", before_flush)
    with monkeypatch.context() as context:
        context.setattr(session, "commit", Mock(side_effect=AssertionError("Service committed")))
        first = add(session, catalog)
        service.update_evidence(session, catalog["user_id"], first["evidence_id"], issuer="Updated")
        service.delete_evidence(session, catalog["user_id"], first["evidence_id"])
        add(session, catalog, title="Still pending")
    assert touched and all(isinstance(row, m.Evidence) for row in touched)
    session.rollback()
    assert rows_snapshot(session) == before


def test_read_functions_do_not_flush_other_pending_changes(session, catalog, monkeypatch):
    first = add(session, catalog)
    session.commit()
    session.get(m.User, catalog["user_id"]).name = "Pending"
    with monkeypatch.context() as context:
        for method in ["flush", "commit", "add"]:
            context.setattr(session, method, Mock(side_effect=AssertionError(method)))
        assert service.get_evidence(session, catalog["user_id"], first["evidence_id"]) == first
        assert service.list_user_evidence(session, catalog["user_id"]) == [first]
    session.rollback()


def test_shared_errors_and_skill_claim_unknown_skill(session, catalog):
    assert issubclass(errors.SkillNotFoundError, LookupError)
    assert issubclass(errors.EvidenceNotFoundError, LookupError)
    with pytest.raises(errors.SkillNotFoundError):
        set_skill_claim(session, catalog["user_id"], 99999, 1)


def output_snapshot(session, catalog):
    user_id, career_id, opportunity_id = catalog["user_id"], catalog["career_id"], catalog["opportunity_id"]
    return dict(summary=get_user_career_summary(session, user_id, career_id),
                roadmap=get_user_roadmap(session, user_id, career_id),
                ranked=get_ranked_opportunities(session, user_id, career_id, today=TODAY),
                match=get_opportunity_match(session, user_id, career_id, opportunity_id, today=TODAY),
                application_counts=get_application_status_counts(session, user_id))


def test_full_golden_form_a_neutrality_on_add_update_and_delete(session, catalog):
    for name, level in {"Python": 2, "SQL": 3, "Statistics": 1, "Machine Learning Fundamentals": 1,
                        "Pandas/Data Handling": 2, "Git": 1}.items():
        set_skill_claim(session, catalog["user_id"], catalog["skills"][name], level)
    for name, level, day in [("Python", 2, 0), ("SQL", 1, 1)]:
        session.add(m.AssessmentAttempt(user_id=catalog["user_id"], skill_id=catalog["skills"][name],
                                        form_name="fixture", status="completed", resulting_level=level,
                                        completed_at=datetime(2025, 1, 1 + day, tzinfo=timezone.utc)))
    save_opportunity(session, catalog["user_id"], catalog["opportunity_id"], today=TODAY)
    session.commit()
    before = output_snapshot(session, catalog)
    assert before["summary"]["next_action"] == dict(action_type="improve", skill_name="SQL")
    assert before["match"]["match_band"] == "stretch"
    assert before["summary"]["effective_readiness"] == pytest.approx(12.25 / 24)
    evidence_ids = []
    for name in ["SQL", "Statistics", "Python"]:
        result = service.add_evidence(session, catalog["user_id"], catalog["skills"][name], f"{name} certificate",
                                      issuer="Demo issuer", url="https://example.com/support", evidence_date=TODAY, today=TODAY)
        evidence_ids.append(result["evidence_id"])
    session.commit()
    session.expire_all()
    assert output_snapshot(session, catalog) == before
    for evidence_id in evidence_ids:
        service.update_evidence(session, catalog["user_id"], evidence_id, title="Updated supporting metadata")
    session.commit()
    session.expire_all()
    assert output_snapshot(session, catalog) == before
    for evidence_id in evidence_ids:
        service.delete_evidence(session, catalog["user_id"], evidence_id)
    session.commit()
    session.expire_all()
    assert output_snapshot(session, catalog) == before


@pytest.mark.parametrize("module_name", ["scoring_service", "career_service", "roadmap_service", "opportunity_service", "application_service"])
def test_static_scoring_isolation_guard(module_name):
    path = Path(service.__file__).parent / f"{module_name}.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            assert node.id not in {"Evidence", "evidence_service"}
        elif isinstance(node, ast.Attribute):
            assert node.attr not in {"Evidence", "evidence_service"}
        elif isinstance(node, ast.Import):
            assert all("evidence_service" not in alias.name.split(".") for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert "evidence_service" not in (node.module or "").split(".")
            assert all(alias.name not in {"Evidence", "evidence_service"} for alias in node.names)


def test_evidence_service_has_no_ui_network_or_scoring_imports():
    tree = ast.parse(Path(service.__file__).read_text(encoding="utf-8"))
    forbidden = {"streamlit", "requests", "httpx", "socket", "serpapi", "aiohttp"}
    forbidden_modules = {"services.scoring_service", "services.career_service", "services.roadmap_service",
                         "services.opportunity_service", "services.application_service"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(alias.name.split(".")[0] not in forbidden and alias.name not in forbidden_modules for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert (node.module or "").split(".")[0] not in forbidden
            assert node.module not in forbidden_modules
            if (node.module or "").startswith("urllib"):
                assert node.module == "urllib.parse"
