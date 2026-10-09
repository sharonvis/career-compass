"""Landing anchors and safe, automatic local startup."""
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import Mock
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from streamlit.testing.v1 import AppTest
from database import db, models as m, seed, startup
from services import user_service

ROOT = Path(__file__).resolve().parents[1]

class Sections(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids, self.links = set(), []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.add(attrs["id"])
        if tag == "a":
            self.links.append(attrs)


def test_landing_links_have_existing_same_page_targets():
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=10).run()
    assert not at.exception
    parsed = Sections()
    parsed.feed("".join(item.value for item in at.markdown))
    for target in ("how", "about"):
        assert target in parsed.ids
        assert any(a.get("href") == f"#{target}" and a.get("target") == "_self" for a in parsed.links)
    assert all(a["href"][1:] in parsed.ids for a in parsed.links if a.get("href", "").startswith("#"))
    assert sum(link.proto.label == "Get Started" for link in at.get("page_link")) == 2


@pytest.fixture
def local(tmp_path, monkeypatch):
    path = tmp_path / "first-run.db"
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    db.configure_sqlite_foreign_keys(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(db, "engine", engine)
    monkeypatch.setattr(db, "SessionLocal", factory)
    monkeypatch.setattr(db, "DATABASE_PATH", path)
    yield engine, factory
    engine.dispose()


def onboarding():
    return AppTest.from_file(str(ROOT / "app.py"), default_timeout=10).run().switch_page("pages/Onboarding.py").run()


@pytest.mark.parametrize("empty_tables", [False, True])
def test_missing_catalog_initializes_once_and_shows_styled_form(local, monkeypatch, empty_tables):
    engine, factory = local
    if empty_tables:
        db.Base.metadata.create_all(engine)
    original = seed.seed_database
    spy = Mock(wraps=original)
    monkeypatch.setattr(seed, "seed_database", spy)
    at = onboarding()
    assert not at.exception and spy.call_count == 1
    assert at.text_input(key="onboarding_email") and at.radio
    output = " ".join(item.value for item in at.markdown)
    assert "cc-onboarding-marker" in output and "<style>" in output
    assert not at.error and not at.info
    assert not any("Initialize" in b.label for b in at.button)
    at.run()
    onboarding()  # A new browser session also must not reseed.
    assert spy.call_count == 1
    with factory() as session:
        assert startup._catalog_ready(session)


def test_initialized_catalog_and_runtime_data_are_untouched(local, monkeypatch):
    engine, factory = local
    startup.ensure_local_catalog()
    with db.session_scope() as session:
        uid = user_service.create_user(session, "Preserved", "preserved@example.com", "BSc", "CS", 2)["user_id"]
        cid = user_service.list_careers(session)[0]["career_id"]
        sid = user_service.list_skills(session)[0]["skill_id"]
        user_service.set_target_career(session, uid, cid)
        user_service.set_skill_claim(session, uid, sid, 3)
        session.add(m.Evidence(user_id=uid, skill_id=sid, title="Retain credential"))
        session.scalars(select(m.Career)).first().description = "Local catalog customization"
    with factory() as session:
        before = {table.name: session.execute(select(table)).all() for table in db.Base.metadata.sorted_tables}
    reseed = Mock(side_effect=AssertionError("Initialized catalogs must not be reseeded"))
    monkeypatch.setattr(seed, "seed_database", reseed)
    at = onboarding()
    at.run()
    assert not at.exception and not reseed.called
    with factory() as session:
        after = {table.name: session.execute(select(table)).all() for table in db.Base.metadata.sorted_tables}
    assert after == before


def test_partial_missing_catalog_is_repaired_without_deleting_user(local):
    _, factory = local
    startup.ensure_local_catalog()
    with db.session_scope() as session:
        uid = user_service.create_user(session, "Keep", "keep@example.com", "BSc", "CS", 1)["user_id"]
        row = session.scalars(select(m.CareerSkillRequirement)).first()
        session.delete(row)
    startup.ensure_local_catalog()
    with factory() as session:
        assert startup._catalog_ready(session)
        assert user_service.get_user_profile(session, uid)["name"] == "Keep"


def test_startup_failure_keeps_brand_and_safe_retry(local, monkeypatch):
    monkeypatch.setattr(startup, "ensure_local_catalog", Mock(side_effect=RuntimeError("private technical details")))
    at = onboarding()
    assert not at.exception and at.error
    assert at.button(key="retry_onboarding_startup")
    assert "private technical details" not in str(at.error)
    assert any("cc-onboarding-marker" in item.value for item in at.markdown)


def test_first_run_creates_missing_data_directory(tmp_path, monkeypatch):
    path = tmp_path / "new-data" / "career.db"
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    monkeypatch.setattr(db, "engine", engine)
    monkeypatch.setattr(db, "SessionLocal", sessionmaker(bind=engine))
    monkeypatch.setattr(db, "DATABASE_PATH", path)
    try:
        at = onboarding()
        assert not at.exception and not at.error and path.exists()
        assert at.text_input(key="onboarding_email")
    finally:
        engine.dispose()
