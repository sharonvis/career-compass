"""Opportunity discovery and application tracking UI with real SQLite services."""
import ast
from datetime import date, timedelta
from pathlib import Path
import pytest
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker
from streamlit.testing.v1 import AppTest
from database import db, models as m
from database.seed import seed_database
from services import user_service, opportunity_service as opp, application_service as app

ROOT = Path(__file__).resolve().parents[1]

@pytest.fixture
def store(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'tracking.db'}", connect_args={"check_same_thread": False})
    db.configure_sqlite_foreign_keys(engine)
    db.Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(db, "SessionLocal", factory)
    with factory() as session:
        seed_database(session)
        uid = user_service.create_user(session, "Tracking Student", "tracking@example.com", "BSc", "CS", 2)["user_id"]
        other = user_service.create_user(session, "Other", "other@example.com", "BSc", "CS", 2)["user_id"]
        cid = user_service.list_careers(session)[0]["career_id"]
        user_service.set_target_career(session, uid, cid)
        session.commit()
        rows = opp.get_ranked_opportunities(session, uid, cid)
        assert len(rows) >= 2
        first, second = (session.get(m.Opportunity, row["opportunity_id"]) for row in rows[:2])
        first.source_url = "https://example.com/real-listing"
        first.deadline = date.today() + timedelta(days=90)
        second.source_url = None
        session.commit()
    yield dict(factory=factory, uid=uid, other=other, cid=cid)
    engine.dispose()


def ranked(store):
    with store["factory"]() as session:
        return opp.get_ranked_opportunities(session, store["uid"], store["cid"])


def tracked(store):
    with store["factory"]() as session:
        return app.list_user_applications(session, store["uid"])


def save(store, oid=None, status="saved"):
    with db.session_scope() as session:
        row = app.save_opportunity(session, store["uid"], oid or ranked(store)[0]["opportunity_id"])
        if status != "saved":
            row = app.update_application_status(session, store["uid"], row["application_id"], status)
        return row


def page(store, name="Opportunities", user=True):
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=10).run()
    if user:
        at.session_state["user_id"] = store["uid"]
    return at.switch_page(f"pages/{name}.py").run()


def text(at):
    return " ".join(str(x.value) for group in (at.markdown, at.caption, at.info, at.success, at.error) for x in group)


def click(at, label):
    next(b for b in at.button if b.label == label).click().run()
    assert not at.exception


@pytest.mark.parametrize("name", ["Opportunities", "Applications"])
@pytest.mark.parametrize("invalid", [False, True])
def test_missing_and_unknown_user_safe(store, name, invalid):
    if invalid:
        store["uid"] = 99999
    at = page(store, name, user=invalid)
    assert not at.exception and not at.button
    assert any(link.proto.label == "Go to Onboarding" for link in at.get("page_link"))


def test_no_career_safe(store):
    with store["factory"]() as session:
        session.get(m.User, store["uid"]).target_career_id = None
        session.commit()
    at = page(store)
    assert not at.exception and "Choose a target career" in text(at)


def test_real_ranking_bands_details_links_and_no_mock(store):
    at = page(store)
    rows = ranked(store)
    assert not at.exception
    # Two-column rendering groups the tree by column; check each column's order.
    for index in (0, 1):
        expected = [row["opportunity_id"] for row in rows[index::2]]
        rendered = [int(b.key.removeprefix("save_opportunity_")) for b in at.button if b.key.startswith("save_opportunity_")][sum(len(rows[j::2]) for j in range(index)):sum(len(rows[j::2]) for j in range(index + 1))]
        assert rendered == expected
    for row in rows:
        assert row["title"] in text(at) and row["company"] in text(at)
        assert "Match: " + row["match_band"].replace("_", " ").title() in text(at)
        assert row["reasons"][0]["text"] in text(at)
    urls = [element.proto.url for element in at.get("link_button")]
    assert urls == [row["source_url"] for row in rows[::2] + rows[1::2] if row["source_url"]]
    assert "Eligibility requirements have not been checked" in text(at)
    assert all(mock not in text(at) for mock in ("Northstar Labs", "Brightline Group", "Fieldnote", "Juniper Health", "12 opportunities", "Posted 2 days"))


def test_search_location_and_sort(store):
    rows = ranked(store)
    at = page(store)
    at.text_input(key="opportunity_search").set_value(rows[0]["title"]).run()
    assert len([b for b in at.button if b.key.startswith("save_opportunity_")]) == 1
    at.text_input(key="opportunity_search").set_value("no such role").run()
    assert not [b for b in at.button if b.key.startswith("save_opportunity_")] and at.info
    at.text_input(key="opportunity_search").set_value("").run()
    location = rows[0]["location"]
    at.selectbox(key="opportunity_location").set_value(location).run()
    assert len([b for b in at.button if b.key.startswith("save_opportunity_")]) == sum(row["location"] == location for row in rows)
    at.selectbox(key="opportunity_location").set_value(None).run()
    for sorting, key in (("Title", lambda row: row["title"].casefold()), ("Closing soon", lambda row: row["deadline"] or date.max)):
        at.selectbox(key="opportunity_sort").set_value(sorting).run()
        ordered = sorted(rows, key=key)
        actual = [int(b.key.removeprefix("save_opportunity_")) for b in at.button if b.key.startswith("save_opportunity_")]
        assert actual == [r["opportunity_id"] for r in ordered[::2] + ordered[1::2]]


def test_save_idempotent_preserves_status_notes_and_fresh_session(store):
    oid = ranked(store)[0]["opportunity_id"]
    at = page(store)
    at.button(key=f"save_opportunity_{oid}").click().run()
    assert not at.exception and at.success
    row = tracked(store)[0]
    with db.session_scope() as session:
        app.update_application_status(session, store["uid"], row["application_id"], "interview")
        app.update_application_notes(session, store["uid"], row["application_id"], "keep notes")
    at.button(key=f"save_opportunity_{oid}").click().run()
    assert len(tracked(store)) == 1
    assert tracked(store)[0]["status"] == "interview" and tracked(store)[0]["notes"] == "keep notes"
    fresh = page(store, "Applications")
    assert row["opportunity"]["title"] in text(fresh) and "interview" in text(fresh)


def test_expired_discovery_hidden_tracking_retained(store):
    row = save(store)
    with store["factory"]() as session:
        session.get(m.Opportunity, row["opportunity_id"]).deadline = date.today() - timedelta(days=1)
        session.commit()
    assert row["opportunity_id"] not in [r["opportunity_id"] for r in ranked(store)]
    assert row["opportunity"]["title"] not in text(page(store))
    at = page(store, "Applications")
    assert row["opportunity"]["title"] in text(at) and "has expired" in text(at)


@pytest.mark.parametrize("status", app.APPLICATION_STATUSES)
def test_status_updates_counts_and_noop(store, status):
    row = save(store)
    at = page(store, "Applications")
    assert [metric.label.casefold() for metric in at.metric] == list(app.APPLICATION_STATUSES)
    assert at.selectbox[0].options == list(app.APPLICATION_STATUSES)
    at.selectbox[0].set_value(status)
    click(at, "Update status")
    assert tracked(store)[0]["status"] == status
    assert next(metric.value for metric in at.metric if metric.label.casefold() == status) == "1"
    before = tracked(store)[0]["updated_at"]
    click(at, "Update status")
    assert tracked(store)[0]["updated_at"] == before
    assert row["opportunity"]["company"] in text(page(store, "Applications"))
    assert "Assessment" not in at.selectbox[0].options
    assert all(mock not in text(at) for mock in ("Northstar Labs", "Brightline Group", "Oct 06, 2026"))


@pytest.mark.parametrize("notes,expected", [("  useful note  ", "useful note"), ("   ", None), ("x" * (app.MAX_NOTES_LENGTH + 1), "original")])
def test_notes_normalization_and_validation(store, notes, expected):
    row = save(store)
    with db.session_scope() as session:
        app.update_application_notes(session, store["uid"], row["application_id"], "original")
    at = page(store, "Applications")
    at.text_area[0].set_value(notes)
    click(at, "Save notes")
    assert tracked(store)[0]["notes"] == expected
    if len(notes) > app.MAX_NOTES_LENGTH:
        assert at.error and "2000" in text(at)
    else:
        fresh = page(store, "Applications")
        assert fresh.text_area[0].value == (expected or "")


def test_saved_removal_and_nonremovable_race(store, monkeypatch):
    row = save(store)
    at = page(store, "Applications")
    click(at, "Remove saved application")
    assert tracked(store) == [] and not page(store, "Applications").button
    row = save(store)
    at = page(store, "Applications")
    original = app.remove_saved_application
    def changed_before_write(session, uid, aid):
        with db.session_scope() as concurrent:
            app.update_application_status(concurrent, uid, aid, "applied")
        original(session, uid, aid)
    monkeypatch.setattr(app, "remove_saved_application", changed_before_write)
    click(at, "Remove saved application")
    assert at.error and "cannot be removed" in text(at)
    assert len(tracked(store)) == 1
    assert next(b for b in page(store, "Applications").button if b.label == "Remove saved application").disabled
    with store["factory"]() as session:
        assert session.get(m.Opportunity, row["opportunity_id"]) is not None


@pytest.mark.parametrize("operation", ["save", "status", "notes", "remove"])
def test_write_failure_rollback(store, monkeypatch, operation):
    oid = ranked(store)[0]["opportunity_id"]
    if operation != "save":
        save(store, oid)
    names = {"save": "save_opportunity", "status": "update_application_status", "notes": "update_application_notes", "remove": "remove_saved_application"}
    original = getattr(app, names[operation])
    def fail(*args, **kwargs):
        original(*args, **kwargs)
        args[0].flush()
        raise RuntimeError("after write")
    monkeypatch.setattr(app, names[operation], fail)
    before = tracked(store)
    at = page(store, "Opportunities" if operation == "save" else "Applications")
    if operation == "save":
        at.button(key=f"save_opportunity_{oid}").click().run()
    else:
        if operation == "status":
            at.selectbox[0].set_value("offer")
        if operation == "notes":
            at.text_area[0].set_value("unsaved change")
        click(at, {"status": "Update status", "notes": "Save notes", "remove": "Remove saved application"}[operation])
    assert not at.exception and at.error and tracked(store) == before


def test_ownership_protection_on_stale_control(store, monkeypatch):
    row = save(store)
    at = page(store, "Applications")
    original = app.update_application_status
    def changed_before_write(session, uid, aid, status):
        with db.session_scope() as concurrent:
            concurrent.get(m.Application, aid).user_id = store["other"]
        return original(session, uid, aid, status)
    monkeypatch.setattr(app, "update_application_status", changed_before_write)
    at.selectbox[0].set_value("offer")
    click(at, "Update status")
    assert at.error
    with store["factory"]() as session:
        protected = app.get_application(session, store["other"], row["application_id"])
        assert protected["status"] == "saved"
    assert tracked(store) == []


def test_application_filter_and_service_boundaries(store):
    rows = ranked(store)
    save(store, rows[0]["opportunity_id"], "applied")
    save(store, rows[1]["opportunity_id"])
    at = page(store, "Applications")
    at.radio[0].set_value("applied").run()
    assert len(at.selectbox) == 1 and at.selectbox[0].value == "applied"
    for name in ("Opportunities", "Applications"):
        source = (ROOT / f"pages/{name}.py").read_text(encoding="utf-8-sig")
        tree = ast.parse(source)
        assert "database.models" not in source and "sqlalchemy" not in source
        for forbidden in ("classify_opportunity_match", "classify_required_skill_statuses", "calculate_career_relevance", "BAND_PRIORITY", "_normalize_notes", "_owned_application"):
            assert forbidden not in source
        assert not any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in ("query", "execute", "scalar", "scalars", "commit") for n in ast.walk(tree))
        current = page(store, name)
        assert all(isinstance(v, (str, int, float, bool, type(None))) for v in dict(current.session_state).values())
