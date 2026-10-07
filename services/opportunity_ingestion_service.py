"""Orchestrate cached SerpAPI searches through normalization and persistence."""

from collections.abc import Callable
from datetime import datetime

from sqlalchemy.orm import Session

from services import opportunity_cache_service, opportunity_normalizer
from services import opportunity_persistence_service, serpapi_client


def ingest_opportunities(
    session: Session,
    opportunity_type: str,
    keywords: str | None = None,
    location: str | None = None,
    *,
    fetcher: Callable | None = None,
    ttl_seconds: int = opportunity_cache_service.DEFAULT_CACHE_TTL_SECONDS,
    now: datetime | None = None,
    refresh: bool = False,
) -> dict[str, int | bool]:
    """Fetch, cache, normalize, and persist one opportunity search.

    The caller owns transaction commit/rollback. A supplied fetcher can replace
    the SerpAPI client for tests or other controlled integrations.
    """
    fetch_count = 0
    retrieve = serpapi_client.search_opportunities if fetcher is None else fetcher

    def tracked_fetcher(*args, **kwargs):
        nonlocal fetch_count
        fetch_count += 1
        return retrieve(*args, **kwargs)

    results = opportunity_cache_service.get_cached_search_results(
        session,
        opportunity_type,
        keywords,
        location,
        fetcher=tracked_fetcher,
        ttl_seconds=ttl_seconds,
        now=now,
        refresh=refresh,
    )
    jobs = results["jobs_results"]
    normalized = opportunity_normalizer.normalize_opportunity_results(
        results, opportunity_type,
    )
    persistence = opportunity_persistence_service.persist_normalized_opportunities(
        session, normalized,
    )

    return {
        "cache_hit": fetch_count == 0,
        "fetched": len(jobs),
        "normalized": len(normalized),
        "inserted": persistence["created"],
        "updated": persistence["updated"],
        "skipped": max(0, len(jobs) - len(normalized))
        + persistence["skipped"]
        + persistence["duplicate_inputs"],
    }
