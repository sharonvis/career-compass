"""Database-backed cache for structured SerpAPI opportunity searches."""

import copy
import hashlib
import json
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from database.models import OpportunitySearchCache
from services.serpapi_client import OPPORTUNITY_SEARCH_TERMS, search_opportunities


# Search results remain cached for 15 minutes by default; callers may override
# this per request when their operational freshness requirements differ.
DEFAULT_CACHE_TTL_SECONDS = 15 * 60


def _normalized_search_inputs(opportunity_type, keywords, location):
    if not isinstance(opportunity_type, str) or opportunity_type not in OPPORTUNITY_SEARCH_TERMS:
        raise ValueError("opportunity_type must be 'internship' or 'entry_level'")
    if keywords is not None and not isinstance(keywords, str):
        raise ValueError("keywords must be a string or None")
    if location is not None and not isinstance(location, str):
        raise ValueError("location must be a string or None")

    normalized_keywords = " ".join(keywords.split()) if keywords is not None else ""
    normalized_location = " ".join(location.split()) if location is not None else ""
    query = OPPORTUNITY_SEARCH_TERMS[opportunity_type]
    if normalized_keywords:
        query = f"{normalized_keywords} {query}"
    return query, normalized_keywords or None, normalized_location or None


def build_search_cache_key(opportunity_type, keywords=None, location=None) -> str:
    """Build a stable key from the effective Google Jobs query and location."""
    query, _, normalized_location = _normalized_search_inputs(
        opportunity_type, keywords, location,
    )
    inputs = json.dumps(
        {"engine": "google_jobs", "query": query, "location": normalized_location},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(inputs.encode("utf-8")).hexdigest()


def _utc(value):
    if value.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    return value.astimezone(timezone.utc)


def _validated_results(results):
    if not isinstance(results, dict) or not isinstance(results.get("jobs_results"), list):
        raise ValueError("Search results must contain a jobs_results list")
    try:
        return json.loads(json.dumps(results, allow_nan=False))
    except (TypeError, ValueError) as error:
        raise ValueError("Search results must contain JSON-serializable data") from error


def get_cached_search_results(
    session: Session,
    opportunity_type: str,
    keywords: str | None = None,
    location: str | None = None,
    *,
    fetcher: Callable | None = None,
    ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS,
    now: datetime | None = None,
    refresh: bool = False,
) -> dict:
    """Return structured search results from cache or fetch and cache them.

    The injected fetcher defaults to the SerpAPI client and is called only for
    a cache miss, expiry, or explicit refresh. Cache writes remain in the
    caller-owned transaction. Expired rows are replaced only after a successful
    response.
    """
    if type(ttl_seconds) is not int or ttl_seconds <= 0:
        raise ValueError("ttl_seconds must be a positive integer")

    query, normalized_keywords, normalized_location = _normalized_search_inputs(
        opportunity_type, keywords, location,
    )
    cache_key = build_search_cache_key(
        opportunity_type, normalized_keywords, normalized_location,
    )
    current_time = _utc(datetime.now(timezone.utc) if now is None else now)

    with session.no_autoflush:
        cached = session.get(OpportunitySearchCache, cache_key)
        if (
            cached is not None
            and not refresh
            and _utc(cached.expires_at) > current_time
        ):
            return copy.deepcopy(cached.results)

    retrieve = search_opportunities if fetcher is None else fetcher
    results = _validated_results(retrieve(
        opportunity_type,
        keywords=normalized_keywords,
        location=normalized_location,
    ))

    with session.no_autoflush:
        cached = session.get(OpportunitySearchCache, cache_key)
        expires_at = current_time + timedelta(seconds=ttl_seconds)
        if cached is None:
            cached = OpportunitySearchCache(
                cache_key=cache_key,
                results=results,
                expires_at=expires_at,
            )
            session.add(cached)
        else:
            cached.results = results
            cached.expires_at = expires_at
    session.flush()
    return copy.deepcopy(results)
