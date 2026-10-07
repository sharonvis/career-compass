"""Database-backed cache behavior for structured SerpAPI searches."""

from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from database import models
from database.db import Base, configure_sqlite_foreign_keys
from services import opportunity_cache_service as cache
from services.serpapi_client import SerpAPIRequestError


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    configure_sqlite_foreign_keys(engine)
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            yield session
    finally:
        engine.dispose()


NOW = datetime(2026, 10, 7, 12, tzinfo=timezone.utc)


def payload(*jobs):
    return {
        "jobs_results": list(jobs),
        "search_metadata": {"id": "query-1", "status": "Success"},
    }


def test_cache_miss_fetches_and_persists_successful_results(session):
    response = payload({"title": "Intern", "extensions": ["Remote"]})
    fetcher = Mock(return_value=response)

    result = cache.get_cached_search_results(
        session, "internship", "python", "Bengaluru", fetcher=fetcher, now=NOW,
    )

    assert result == response
    fetcher.assert_called_once_with(
        "internship", keywords="python", location="Bengaluru",
    )
    stored = session.get(
        models.OpportunitySearchCache,
        cache.build_search_cache_key("internship", "python", "Bengaluru"),
    )
    assert stored.results == response
    assert stored.created_at.tzinfo is timezone.utc
    assert stored.updated_at.tzinfo is timezone.utc
    assert stored.expires_at == NOW + timedelta(seconds=cache.DEFAULT_CACHE_TTL_SECONDS)


def test_cache_hit_skips_fetch_and_returns_deserialized_json(session):
    response = payload({"title": "Intern", "metadata": {"locations": ["Remote", "India"]}})
    fetcher = Mock(return_value=response)
    cache.get_cached_search_results(
        session, "internship", fetcher=fetcher, now=NOW,
    )
    session.commit()
    session.expunge_all()

    result = cache.get_cached_search_results(
        session, "internship", fetcher=fetcher, now=NOW + timedelta(minutes=1),
    )

    assert result == response
    fetcher.assert_called_once()


def test_identical_normalized_searches_reuse_the_same_cache_entry(session):
    fetcher = Mock(return_value=payload({"title": "Intern"}))

    first = cache.get_cached_search_results(
        session, "internship", "  python \t developer ", " Remote ",
        fetcher=fetcher, now=NOW,
    )
    second = cache.get_cached_search_results(
        session, "internship", "python developer", "Remote",
        fetcher=fetcher, now=NOW + timedelta(minutes=1),
    )

    assert first == second
    fetcher.assert_called_once_with(
        "internship", keywords="python developer", location="Remote",
    )
    assert session.query(models.OpportunitySearchCache).count() == 1


def test_different_search_inputs_have_different_keys_and_fetches(session):
    assert cache.build_search_cache_key("internship", "python", "Remote") != (
        cache.build_search_cache_key("internship", "python", "Bengaluru")
    )
    assert cache.build_search_cache_key("internship", "python", "Remote") != (
        cache.build_search_cache_key("entry_level", "python", "Remote")
    )
    fetcher = Mock(side_effect=[payload({"title": "Intern"}), payload({"title": "Role"})])

    cache.get_cached_search_results(
        session, "internship", "python", "Remote", fetcher=fetcher, now=NOW,
    )
    cache.get_cached_search_results(
        session, "internship", "python", "Bengaluru", fetcher=fetcher, now=NOW,
    )

    assert fetcher.call_count == 2


def test_expired_cache_entry_is_refetched_and_replaced(session):
    original = payload({"title": "Old"})
    refreshed = payload({"title": "New"})
    fetcher = Mock(side_effect=[original, refreshed])
    cache.get_cached_search_results(
        session, "internship", fetcher=fetcher, ttl_seconds=60, now=NOW,
    )

    result = cache.get_cached_search_results(
        session, "internship", fetcher=fetcher, ttl_seconds=60,
        now=NOW + timedelta(seconds=61),
    )

    assert result == refreshed
    assert fetcher.call_count == 2
    row = session.get(
        models.OpportunitySearchCache,
        cache.build_search_cache_key("internship"),
    )
    assert row.results == refreshed
    assert row.expires_at == NOW + timedelta(seconds=121)


def test_failed_refresh_does_not_overwrite_valid_cache(session):
    original = payload({"title": "Cached"})
    cache.get_cached_search_results(
        session, "internship", fetcher=Mock(return_value=original), now=NOW,
    )
    session.commit()
    key = cache.build_search_cache_key("internship")
    row = session.get(models.OpportunitySearchCache, key)
    original_created_at = row.created_at
    failing_fetcher = Mock(side_effect=SerpAPIRequestError("unavailable"))

    with pytest.raises(SerpAPIRequestError):
        cache.get_cached_search_results(
            session, "internship", fetcher=failing_fetcher,
            now=NOW + timedelta(minutes=1), refresh=True,
        )

    session.expire_all()
    row = session.get(models.OpportunitySearchCache, key)
    assert row.results == original
    assert row.created_at == original_created_at
    assert row.expires_at == NOW + timedelta(seconds=cache.DEFAULT_CACHE_TTL_SECONDS)


def test_empty_successful_results_are_cached(session):
    empty = payload()
    fetcher = Mock(return_value=empty)

    assert cache.get_cached_search_results(
        session, "entry_level", fetcher=fetcher, now=NOW,
    ) == empty
    assert cache.get_cached_search_results(
        session, "entry_level", fetcher=fetcher, now=NOW + timedelta(minutes=1),
    ) == empty
    fetcher.assert_called_once()


def test_invalid_api_response_does_not_create_or_replace_cache(session):
    with pytest.raises(ValueError, match="jobs_results list"):
        cache.get_cached_search_results(
            session, "internship", fetcher=Mock(return_value={"error": "bad"}),
            now=NOW,
        )

    assert session.query(models.OpportunitySearchCache).count() == 0


def test_cache_key_is_stable_and_does_not_include_credentials():
    first = cache.build_search_cache_key("entry_level", "data analyst", "Chennai")
    second = cache.build_search_cache_key("entry_level", " data   analyst ", " Chennai ")

    assert first == second
    assert len(first) == 64


@pytest.mark.parametrize("ttl_seconds", [0, -1, True, 1.5])
def test_rejects_invalid_ttl(session, ttl_seconds):
    with pytest.raises(ValueError, match="ttl_seconds"):
        cache.get_cached_search_results(
            session, "internship", fetcher=Mock(), ttl_seconds=ttl_seconds,
        )
