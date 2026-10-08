"""End-to-end tests for the opportunity ingestion orchestration service."""

from datetime import date, datetime, timedelta, timezone
from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from database import models
from database.db import Base, configure_sqlite_foreign_keys
from database.seed import seed_database
from services import opportunity_cache_service as cache
from services import opportunity_ingestion_service as ingestion
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
            seed_database(session)
            session.commit()
            yield session
    finally:
        engine.dispose()


NOW = datetime(2026, 10, 7, 12, tzinfo=timezone.utc)


def raw_job(
    title="Python Internship",
    company="Example Labs",
    url="https://example.com/jobs/python-intern",
    **overrides,
):
    job = {
        "title": title,
        "company_name": company,
        "location": "Bengaluru",
        "share_link": url,
        "deadline": "2026-12-31",
    }
    job.update(overrides)
    return job


def results(*jobs):
    return {"jobs_results": list(jobs), "search_metadata": {"status": "Success"}}


def count_opportunities(session, source):
    return session.scalar(
        select(func.count()).select_from(models.Opportunity).where(
            models.Opportunity.source == source,
        )
    )


def test_valid_cache_hit_skips_serpapi_and_persists_cached_jobs(session):
    cached = results(raw_job())
    cache.get_cached_search_results(
        session, "internship", "python", "Bengaluru",
        fetcher=Mock(return_value=cached), now=NOW,
    )
    session.commit()
    fetcher = Mock(side_effect=AssertionError("cache hit must not call SerpAPI"))

    summary = ingestion.ingest_opportunities(
        session, "internship", "python", "Bengaluru",
        fetcher=fetcher, now=NOW + timedelta(minutes=1),
    )

    fetcher.assert_not_called()
    assert summary == {
        "cache_hit": True,
        "fetched": 1,
        "normalized": 1,
        "inserted": 1,
        "updated": 0,
        "skipped": 0,
    }


def test_cache_miss_calls_serpapi_and_caches_response(session):
    response = results(raw_job())
    fetcher = Mock(return_value=response)

    summary = ingestion.ingest_opportunities(
        session, "internship", "python", "Bengaluru",
        fetcher=fetcher, now=NOW,
    )

    fetcher.assert_called_once_with(
        "internship", keywords="python", location="Bengaluru",
    )
    assert summary["cache_hit"] is False
    assert session.query(models.OpportunitySearchCache).count() == 1


def test_expired_cache_calls_serpapi_and_refreshes_results(session):
    old_response = results(raw_job(title="Old Python Internship"))
    new_response = results(raw_job(title="New Python Internship"))
    fetcher = Mock(side_effect=[old_response, new_response])
    ingestion.ingest_opportunities(
        session, "internship", "python", "Bengaluru",
        fetcher=fetcher, ttl_seconds=60, now=NOW,
    )

    summary = ingestion.ingest_opportunities(
        session, "internship", "python", "Bengaluru",
        fetcher=fetcher, ttl_seconds=60, now=NOW + timedelta(seconds=61),
    )

    assert fetcher.call_count == 2
    assert summary["cache_hit"] is False
    assert summary["inserted"] == 1
    assert count_opportunities(session, "serpapi") == 2


def test_successful_fetch_normalizes_and_persists(session):
    response = results(raw_job())
    fetcher = Mock(return_value=response)

    summary = ingestion.ingest_opportunities(
        session, "entry_level", "data analyst", fetcher=fetcher, now=NOW,
    )

    row = session.scalar(
        select(models.Opportunity).where(models.Opportunity.source == "serpapi")
    )
    assert summary["fetched"] == summary["normalized"] == summary["inserted"] == 1
    assert row.opportunity_type == "entry_level"
    assert row.source_url == "https://example.com/jobs/python-intern"
    assert row.deadline == date(2026, 12, 31)


def test_repeated_identical_ingestion_is_idempotent(session):
    fetcher = Mock(return_value=results(raw_job()))
    first = ingestion.ingest_opportunities(
        session, "internship", fetcher=fetcher, now=NOW,
    )
    second = ingestion.ingest_opportunities(
        session, "internship", fetcher=fetcher, now=NOW + timedelta(minutes=1),
    )

    assert first["inserted"] == 1
    assert second["cache_hit"] is True
    assert second["inserted"] == 0
    assert second["updated"] == 0
    assert count_opportunities(session, "serpapi") == 1
    fetcher.assert_called_once()


def test_successful_empty_results_return_zero_counts_and_are_cached(session):
    fetcher = Mock(return_value=results())

    first = ingestion.ingest_opportunities(
        session, "internship", fetcher=fetcher, now=NOW,
    )
    second = ingestion.ingest_opportunities(
        session, "internship", fetcher=fetcher, now=NOW + timedelta(minutes=1),
    )

    assert first == {
        "cache_hit": False,
        "fetched": 0,
        "normalized": 0,
        "inserted": 0,
        "updated": 0,
        "skipped": 0,
    }
    assert second["cache_hit"] is True
    fetcher.assert_called_once()


def test_failed_fetch_preserves_valid_cache_and_seeded_opportunities(session):
    original = results(raw_job())
    cache.get_cached_search_results(
        session, "internship", fetcher=Mock(return_value=original), now=NOW,
    )
    session.commit()
    cache_key = cache.build_search_cache_key("internship")
    seeded_before = list(session.scalars(
        select(models.Opportunity.id, models.Opportunity.title,
               models.Opportunity.source, models.Opportunity.is_seeded)
        .where(models.Opportunity.is_seeded.is_(True))
    ))
    fetcher = Mock(side_effect=SerpAPIRequestError("offline"))

    with pytest.raises(SerpAPIRequestError):
        ingestion.ingest_opportunities(
            session, "internship", fetcher=fetcher,
            now=NOW + timedelta(minutes=1), refresh=True,
        )

    session.expire_all()
    cached = session.get(models.OpportunitySearchCache, cache_key)
    seeded_after = list(session.scalars(
        select(models.Opportunity.id, models.Opportunity.title,
               models.Opportunity.source, models.Opportunity.is_seeded)
        .where(models.Opportunity.is_seeded.is_(True))
    ))
    assert cached.results == original
    assert cached.expires_at == NOW + timedelta(seconds=cache.DEFAULT_CACHE_TTL_SECONDS)
    assert seeded_after == seeded_before


def test_pipeline_summary_counts_invalid_and_duplicate_jobs(session):
    fetcher = Mock(return_value=results(
        raw_job(),
        raw_job(title="  python internship ", company="EXAMPLE LABS"),
        raw_job(title="", company="No Title"),
        {"title": "No company", "share_link": "https://example.com/no-company"},
    ))

    summary = ingestion.ingest_opportunities(
        session, "internship", fetcher=fetcher, now=NOW,
    )

    assert summary == {
        "cache_hit": False,
        "fetched": 4,
        "normalized": 1,
        "inserted": 1,
        "updated": 0,
        "skipped": 3,
    }
