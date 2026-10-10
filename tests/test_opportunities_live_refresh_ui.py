"""Intentional live refresh through the real page and transactional ingestion."""
from unittest.mock import Mock

import pytest
from sqlalchemy import select

import config
from database import models as m
from services import opportunity_ingestion_service as ingestion, opportunity_service, serpapi_client
from test_opportunity_application_ui import store, page, text, ranked


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    fetch = Mock(side_effect=AssertionError("Unexpected external request"))
    monkeypatch.setattr(serpapi_client, "search_opportunities", fetch)
    monkeypatch.setattr(config, "get_serpapi_api_key", lambda: "test-only-key")
    return fetch


def refresh(at):
    at.button(key="refresh_live_opportunities").click().run()
    assert not at.exception


def test_no_fetch_on_render_or_filter_rerun(store, no_network):
    at = page(store)
    assert not at.exception
    assert at.button(key="refresh_live_opportunities").label == "Refresh live opportunities"
    at.text_input(key="opportunity_search").set_value("intern").run()
    no_network.assert_not_called()


def test_missing_key_safe(store, monkeypatch, no_network):
    monkeypatch.setattr(config, "get_serpapi_api_key", lambda: None)
    at = page(store)
    refresh(at)
    assert "SerpAPI is not configured yet." in text(at)
    no_network.assert_not_called()


@pytest.mark.parametrize("career,expected", [
    ("AI/ML Engineer", "machine learning"),
    ("Software Engineer", "software engineer"),
    ("Data Analyst", "data analyst"),
])
def test_click_search_arguments_and_reread(store, monkeypatch, career, expected):
    from services import user_service
    with store["factory"]() as session:
        cid = next(c["career_id"] for c in user_service.list_careers(session) if c["name"] == career)
        user_service.set_target_career(session, store["uid"], cid)
        session.commit()
    ingest = Mock(return_value={"fetched": 1})
    read = Mock(wraps=opportunity_service.get_ranked_opportunities)
    monkeypatch.setattr(ingestion, "ingest_opportunities", ingest)
    monkeypatch.setattr(opportunity_service, "get_ranked_opportunities", read)
    at = page(store)
    ingest.assert_not_called()
    before = read.call_count
    refresh(at)
    ingest.assert_called_once()
    assert ingest.call_args.args[1] == "internship"
    assert ingest.call_args.kwargs == dict(keywords=expected, location=None, refresh=True)
    assert read.call_count >= before + 2  # Click render and committed-success rerun.
    assert "Live opportunity search refreshed." in text(at)
    at.run()
    ingest.assert_called_once()


def test_live_ingestion_persists_and_displays_source(store, no_network):
    no_network.side_effect = None
    no_network.return_value = {"jobs_results": [{
        "title": "Fresh SQL Internship", "company_name": "Live Test Labs",
        "location": "Remote", "share_link": "https://example.com/live-sql",
        "description": "Required skills: SQL",
    }]}
    at = page(store)
    refresh(at)
    assert "Fresh SQL Internship" in text(at)
    assert "Source: LIVE" in text(at)
    assert "Source: DEMO DATA" in text(at)
    no_network.assert_called_once()
    with store["factory"]() as session:
        row = session.scalar(select(m.Opportunity).where(m.Opportunity.company == "Live Test Labs"))
        assert row.source == "serpapi" and not row.is_seeded
        assert row.source_url == "https://example.com/live-sql"


def test_failure_rolls_back_and_keeps_stored_results(store, monkeypatch):
    before = ranked(store)
    def fail(session, *args, **kwargs):
        session.get(m.Opportunity, before[0]["opportunity_id"]).title = "Must roll back"
        session.flush()
        raise RuntimeError("sensitive test-only-key")
    monkeypatch.setattr(ingestion, "ingest_opportunities", fail)
    at = page(store)
    refresh(at)
    assert "Your stored opportunities remain available." in text(at)
    assert "test-only-key" not in text(at)
    assert ranked(store) == before
    assert before[0]["title"] in text(at)


def test_selected_location_is_used(store, monkeypatch):
    ingest = Mock(return_value={"fetched": 0})
    monkeypatch.setattr(ingestion, "ingest_opportunities", ingest)
    at = page(store)
    location = next(r["location"] for r in ranked(store) if r["location"] and r["location"].casefold() != "remote")
    at.selectbox(key="opportunity_location").set_value(location).run()
    refresh(at)
    assert ingest.call_args.kwargs["location"] == location
    assert "No live opportunities were returned" in text(at)


def test_serpapi_failure_keeps_stored_results(store, no_network):
    before = ranked(store)
    no_network.side_effect = serpapi_client.SerpAPIRequestError("Fetch unavailable")
    at = page(store)
    refresh(at)
    no_network.assert_called_once()
    assert "Could not refresh live opportunities" in text(at)
    assert ranked(store) == before
    assert "Source: DEMO DATA" in text(at)


@pytest.mark.parametrize("selected,expected", [
    ("Remote", None),
    ("rEmOtE", None),
    ("Any location", None),
    ("", None),
    ("   ", None),
    (None, None),
    ("Chennai", "Chennai"),
    ("Plymouth, MI (+4 others)", None),
    ("New York, NY (+3 others)", None),
])
def test_refresh_sanitizes_listing_location(store, monkeypatch, selected, expected):
    rows = ranked(store)
    for row in rows:
        row["location"] = selected
    monkeypatch.setattr(opportunity_service, "get_ranked_opportunities", Mock(return_value=rows))
    ingest = Mock(return_value={"fetched": 0})
    monkeypatch.setattr(ingestion, "ingest_opportunities", ingest)
    at = page(store)
    if selected:
        at.selectbox(key="opportunity_location").set_value(selected).run()
    ingest.assert_not_called()
    refresh(at)
    ingest.assert_called_once()
    assert ingest.call_args.kwargs["location"] == expected
    assert ingest.call_args.kwargs["refresh"] is True
    at.run()
    ingest.assert_called_once()
