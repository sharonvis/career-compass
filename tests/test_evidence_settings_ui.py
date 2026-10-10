"""Evidence, profile and identity UI integration using isolated SQLite."""
import ast
from datetime import date, timedelta
from pathlib import Path
import pytest
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session, sessionmaker
from streamlit.testing.v1 import AppTest
from database import db, models as m
from database.seed import seed_database
from services import user_service as users, evidence_service as evidence, progress_service as progress, career_service

ROOT = Path(__file__).resolve().parents[1]

@pytest.fixture
def store(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'evidence.db'}", connect_args={"check_same_thread": False})
    db.configure_sqlite_foreign_keys(engine)
    db.Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(db, "SessionLocal", factory)
    from services import evidence_storage_service
    monkeypatch.setattr(evidence_storage_service, "STORAGE_ROOT", tmp_path / "uploads")
    with factory() as session:
        seed_database(session)
        uid = users.create_user(session, "Actual Student", "actual@example.com", "BSc", "CS", 2)["user_id"]
        other = users.create_user(session, "Other", "other@example.com", "BSc", "CS", 1)["user_id"]
        cid = users.list_careers(session)[0]["career_id"]
        users.set_target_career(session, uid, cid)
        sid = next(s["skill_id"] for s in users.list_skills(session) if s["name"] == "SQL")
        users.set_skill_claim(session, uid, sid, 2)
        session.add(m.AssessmentAttempt(user_id=uid, skill_id=sid, form_name="A", status="completed", resulting_level=1, completed_at=m.utc_now()))
        session.commit()
    yield dict(factory=factory, uid=uid, other=other, cid=cid, sid=sid)
    engine.dispose()


def page(store, name="Evidence", user=True):
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=10).run()
    if user:
        at.session_state["user_id"] = store["uid"]
    return at.switch_page(f"pages/{name}.py").run()


def click(at, label):
    next(b for b in at.button if b.label == label).click().run()
    assert not at.exception


def read(store):
    with store["factory"]() as session:
        return evidence.list_user_evidence(session, store["uid"])


def events(store):
    with store["factory"]() as session:
        return progress.list_recent_progress_events(session, store["uid"])


def summary(store):
    with store["factory"]() as session:
        return career_service.get_user_career_summary(session, store["uid"], store["cid"])


def text(at):
    return " ".join(str(e.value) for group in (at.markdown, at.caption, at.info, at.error, at.success, at.subheader) for e in group)


def add(at, store, title="SQL credential", url="https://example.com/credential", stamp=None):
    at.text_input(key="evidence_add_title").set_value(title)
    at.text_input(key="evidence_add_issuer").set_value("  Training Provider  ")
    at.selectbox(key="evidence_add_skill").set_value(store["sid"])
    at.text_input(key="evidence_add_url").set_value(url)
    at.date_input(key="evidence_add_date").set_value(stamp)
    click(at, "Add evidence")


@pytest.mark.parametrize("name", ["Evidence", "Settings"])
@pytest.mark.parametrize("invalid", [False, True])
def test_safe_user_and_header(store, name, invalid):
    if invalid:
        store["uid"] = 99999
    at = page(store, name, user=invalid)
    assert not at.exception and not at.button
    assert "Guest" in text(at) and "Sharon" not in text(at)
    assert any(e.proto.label == "Go to Onboarding" for e in at.get("page_link"))


def test_evidence_crud_fresh_sessions_neutrality_and_activity(store):
    before = summary(store)
    at = page(store)
    assert "No evidence added yet" in text(at) and "Actual Student" in text(at)
    stamp = date.today() - timedelta(days=10)
    add(at, store, stamp=stamp)
    row = read(store)[0]
    assert row["skill_id"] == store["sid"] and row["evidence_date"] == stamp
    assert row["issuer"] == "Training Provider" and row["url"] == "https://example.com/credential"
    assert summary(store) == before
    assert len(events(store)) == 1 and events(store)[0]["event_type"] == "evidence_added"
    at.run()
    assert len(events(store)) == 1
    add(at, store, stamp=stamp)  # Exact duplicate remains one row and one event.
    assert len(read(store)) == 1 and len(events(store)) == 1
    fresh = page(store)
    assert row["title"] in text(fresh)
    edit_inputs = [e for e in fresh.text_input if e.key is None]
    edit_inputs[0].set_value(" Updated credential ")
    edit_inputs[1].set_value("")
    edit_inputs[2].set_value("")
    next(e for e in fresh.date_input if e.key is None).set_value(None)
    click(fresh, "Save evidence")
    changed = read(store)[0]
    assert changed["title"] == "Updated credential"
    assert changed["issuer"] is None and changed["url"] is None and changed["evidence_date"] is None
    assert summary(store) == before and len(events(store)) == 1
    fresh = page(store)
    assert "Updated credential" in text(fresh) and not fresh.get("link_button")
    click(fresh, "Delete evidence")
    assert not read(store) and "No evidence added yet" in text(page(store))
    assert summary(store) == before and len(events(store)) == 1
    dashboard = page(store, "Dashboard")
    assert not dashboard.exception and events(store)[0]["description"] in text(dashboard)


@pytest.mark.parametrize("title,url,stamp", [("  ", "", None), ("x" * 201, "", None), ("Valid", "javascript:bad", None), ("Valid", "https://bad url", None), ("Valid", "", date.today() + timedelta(days=1))])
def test_evidence_invalid_fields(store, title, url, stamp):
    at = page(store)
    add(at, store, title=title, url=url, stamp=stamp)
    assert at.error and not read(store) and not events(store)


def test_long_title_activity_subject_and_catalog_without_career(store):
    with db.session_scope() as session:
        session.get(m.User, store["uid"]).target_career_id = None
    at = page(store)
    add(at, store, title="x" * 200, url="")
    assert not at.error and len(read(store)[0]["title"]) == 200
    assert events(store)[0]["description"] == "Added evidence: " + "x" * 100 + "."


def test_wrong_owner_ui_and_service(store, monkeypatch):
    with db.session_scope() as session:
        row = evidence.add_evidence(session, store["other"], store["sid"], "Private")
    for method, kwargs in ((evidence.get_evidence, {}), (evidence.update_evidence, {"title": "Changed"}), (evidence.delete_evidence, {})):
        with pytest.raises(LookupError), db.session_scope() as session:
            method(session, store["uid"], row["evidence_id"], **kwargs)
    assert "Private" not in text(page(store))
    with db.session_scope() as session:
        owned = evidence.add_evidence(session, store["uid"], store["sid"], "Owned")
    original = evidence.get_evidence
    def ownership_changed(session, uid, eid):
        with db.session_scope() as concurrent:
            concurrent.get(m.Evidence, eid).user_id = store["other"]
        return original(session, uid, eid)
    at = page(store)
    monkeypatch.setattr(evidence, "get_evidence", ownership_changed)
    click(at, "Delete evidence")
    assert at.error
    with store["factory"]() as session:
        assert evidence.list_user_evidence(session, store["other"])[0]["title"] in ("Owned", "Private")
        assert session.get(m.Evidence, owned["evidence_id"]) is not None


def test_settings_supported_fields_identity_noop_and_email(store):
    at = page(store, "Settings")
    assert "Actual Student" in text(at) and "actual@example.com" in text(at)
    assert [e.value for e in at.text_input] == ["", "Actual Student", "BSc", "CS"]  # Header search plus profile fields.
    assert not at.toggle
    assert "College or university" not in text(at) and "Save preferences" not in text(at)
    inputs = [e for e in at.text_input if e.label != "Search Career Compass"]
    for field, value in zip(inputs, (" New Name ", " MSc ", " Statistics ")):
        field.set_value(value)
    at.selectbox[0].set_value(4)
    click(at, "Save profile")
    with store["factory"]() as session:
        profile = users.get_user_profile(session, store["uid"])
    assert (profile["name"], profile["degree"], profile["branch"], profile["year_of_study"]) == ("New Name", "MSc", "Statistics", 4)
    assert profile["email"] == "actual@example.com"
    fresh = page(store, "Settings")
    assert "New Name" in text(fresh)
    click(fresh, "Save profile")
    assert not events(store)


@pytest.mark.parametrize("kwargs", [{"name": " "}, {"degree": " "}, {"branch": ""}, {"year_of_study": 0}, {"year_of_study": 5}, {"year_of_study": True}, {"year_of_study": 1.5}])
def test_profile_validation_atomic_and_no_commit(store, kwargs):
    with store["factory"]() as session:
        before = users.get_user_profile(session, store["uid"])
        with pytest.raises(ValueError):
            users.update_user_profile(session, store["uid"], **dict({"name": "Should not persist"}, **kwargs))
        assert users.get_user_profile(session, store["uid"]) == before
    with store["factory"]() as session:
        users.update_user_profile(session, store["uid"], name="Uncommitted")
    with store["factory"]() as session:
        assert users.get_user_profile(session, store["uid"])["name"] == before["name"]


def test_profile_missing_user_and_invalid_ui(store):
    with pytest.raises(LookupError), db.session_scope() as session:
        users.update_user_profile(session, 99999, name="Valid")
    at = page(store, "Settings")
    next(e for e in at.text_input if e.label == "Full name").set_value(" ")
    click(at, "Save profile")
    assert at.error
    assert "Actual Student" in text(page(store, "Settings"))


@pytest.mark.parametrize("operation", ["add", "edit", "delete", "profile", "activity"])
def test_write_failure_rollback(store, monkeypatch, operation):
    if operation in ("edit", "delete"):
        with db.session_scope() as session:
            evidence.add_evidence(session, store["uid"], store["sid"], "Original")
    module, method = ({"add": (evidence, "add_evidence"), "edit": (evidence, "update_evidence"), "delete": (evidence, "delete_evidence"), "profile": (users, "update_user_profile"), "activity": (progress, "record_progress_event")}[operation])
    original = getattr(module, method)
    def fail(*args, **kwargs):
        original(*args, **kwargs)
        args[0].flush()
        raise RuntimeError("after write")
    monkeypatch.setattr(module, method, fail)
    before = read(store)
    at = page(store, "Settings" if operation == "profile" else "Evidence")
    if operation in ("add", "activity"):
        add(at, store)
    elif operation == "edit":
        next(e for e in at.text_input if e.label == "Title" and e.key is None).set_value("Changed")
        click(at, "Save evidence")
    elif operation == "delete":
        click(at, "Delete evidence")
    else:
        next(e for e in at.text_input if e.label == "Full name").set_value("Changed")
        click(at, "Save profile")
    assert at.error and read(store) == before and not events(store)
    with store["factory"]() as session:
        assert users.get_user_profile(session, store["uid"])["name"] == "Actual Student"


def test_architecture_and_real_empty_activity(store):
    for path in ("pages/Evidence.py", "pages/Settings.py", "ui/components/header.py"):
        source = (ROOT / path).read_text(encoding="utf-8-sig")
        assert "database.models" not in source and "sqlalchemy" not in source
        assert not any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in ("query", "execute", "scalar", "scalars", "commit") for n in ast.walk(ast.parse(source)))
        assert not any(word in source for word in ("calculate_readiness", "rank_next_actions", "get_latest_demonstrated_level"))
    for name in ("Evidence", "Settings"):
        at = page(store, name)
        assert all(not isinstance(value, (db.Base, Session)) for value in dict(at.session_state).values())
    dashboard = page(store, "Dashboard")
    assert "No recent activity yet" in text(dashboard)
    assert not events(store)


# AppTest cannot set UploadedFile values directly; emulate only that widget's
# return value while running the real page, SQLite services and storage helper.
def test_evidence_uploader_and_download_delete(store, monkeypatch):
    from io import BytesIO
    import streamlit as st
    from services import evidence_storage_service as storage
    from test_evidence_storage_service import image_bytes
    at = page(store)
    assert len(at.get("file_uploader")) == 1
    upload = BytesIO(image_bytes())
    upload.name, upload.type = "certificate.png", "image/png"
    monkeypatch.setattr(st, "file_uploader", lambda *a, **kw: upload)
    downloads = []
    original = st.download_button
    def capture(*args, **kwargs):
        downloads.append(kwargs)
        return original(*args, **kwargs)
    monkeypatch.setattr(st, "download_button", capture)
    at.run()
    before = summary(store)
    add(at, store)
    row = read(store)[0]
    assert downloads[-1]["data"] == upload.getvalue()
    assert downloads[-1]["file_name"] == "certificate.png"
    assert downloads[-1]["mime"] == "image/png"
    assert len(at.get("download_button")) == 1
    assert summary(store) == before
    directory = storage.STORAGE_ROOT / str(store["uid"]) / str(row["evidence_id"])
    click(at, "Delete evidence")
    assert not directory.exists() and not read(store)


def test_evidence_upload_duplicate_preserves_file(store, monkeypatch):
    from io import BytesIO
    import streamlit as st
    from services import evidence_storage_service as storage
    from test_evidence_storage_service import pdf_bytes, image_bytes
    upload = BytesIO(pdf_bytes()); upload.name, upload.type = "first.pdf", "application/pdf"
    monkeypatch.setattr(st, "file_uploader", lambda *a, **kw: upload)
    at = page(store); add(at, store)
    eid = read(store)[0]["evidence_id"]
    upload = BytesIO(image_bytes()); upload.name, upload.type = "second.png", "image/png"
    add(at, store)
    assert at.error and len(read(store)) == 1
    with store["factory"]() as session:
        attachment = storage.get_attachment(session, store["uid"], eid)
    assert attachment["data"] == pdf_bytes() and attachment["original_filename"] == "first.pdf"
    assert len(events(store)) == 1


@pytest.mark.parametrize("fail_activity", [False, True])
def test_evidence_bad_upload_and_db_failure_leave_no_files(store, monkeypatch, fail_activity):
    from io import BytesIO
    import streamlit as st
    from services import evidence_storage_service as storage
    from test_evidence_storage_service import pdf_bytes
    upload = BytesIO(pdf_bytes() if fail_activity else b"invalid")
    upload.name, upload.type = "certificate.pdf", "application/pdf"
    monkeypatch.setattr(st, "file_uploader", lambda *a, **kw: upload)
    if fail_activity:
        def fail(*args, **kwargs):
            raise RuntimeError("activity write failed")
        monkeypatch.setattr(progress, "record_progress_event", fail)
    at = page(store); add(at, store)
    assert at.error and not read(store) and not events(store)
    assert not list(storage.STORAGE_ROOT.rglob("attachment.json"))
    assert not list(storage.STORAGE_ROOT.rglob("*.pdf"))
