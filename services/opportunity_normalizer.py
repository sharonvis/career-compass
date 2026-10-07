"""Normalize and deduplicate live SerpAPI opportunities without database writes."""

import html
import re
from collections.abc import Mapping
from datetime import date, datetime
from urllib.parse import urlparse


LIVE_OPPORTUNITY_SOURCE = "serpapi"
OPPORTUNITY_TYPES = {"internship", "entry_level"}


def _clean_text(value):
    if not isinstance(value, str):
        return None
    cleaned = " ".join(html.unescape(value).split())
    cleaned = re.sub(r"\s+([,.;:])", r"\1", cleaned)
    return cleaned or None


def _usable_url(value):
    cleaned = _clean_text(value)
    if cleaned is None:
        return None
    cleaned = html.unescape(cleaned)
    parsed = urlparse(cleaned)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return None
    return cleaned


def _job_url(job):
    for field in ("share_link", "link", "url"):
        url = _usable_url(job.get(field))
        if url:
            return url

    for field in ("apply_options", "related_links"):
        links = job.get(field)
        if isinstance(links, list):
            for link in links:
                if isinstance(link, Mapping):
                    url = _usable_url(link.get("link") or link.get("url"))
                    if url:
                        return url
    return None


def _parse_deadline(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    cleaned = _clean_text(value)
    if cleaned is None:
        return None
    for parser in (date.fromisoformat,):
        try:
            return parser(cleaned)
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(cleaned.replace("Z", "+00:00")).date()
    except ValueError:
        pass
    for format_string in ("%b %d, %Y", "%B %d, %Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(cleaned, format_string).date()
        except ValueError:
            continue
    return None


def _deadline(job):
    for field in ("deadline", "application_deadline"):
        if field in job:
            return _parse_deadline(job[field])
    extensions = job.get("detected_extensions")
    if isinstance(extensions, Mapping):
        for field in ("deadline", "application_deadline"):
            if field in extensions:
                return _parse_deadline(extensions[field])
    return None


def _deduplication_key(opportunity):
    return (
        opportunity["source"],
        opportunity["title"].casefold(),
        opportunity["company"].casefold(),
        (opportunity["location"] or "").casefold(),
    )


def normalize_opportunity_results(
    search_results: Mapping,
    opportunity_type: str,
) -> list[dict]:
    """Convert a SerpAPI response into normalized, deduplicated model-field data.

    Malformed top-level responses raise ``ValueError``. Invalid individual job
    entries are skipped, so valid results from the same response are retained.
    """
    if not isinstance(search_results, Mapping) or not isinstance(
        search_results.get("jobs_results"), list
    ):
        raise ValueError("SerpAPI response must contain a jobs_results list")
    if not isinstance(opportunity_type, str) or opportunity_type not in OPPORTUNITY_TYPES:
        raise ValueError("opportunity_type must be 'internship' or 'entry_level'")

    normalized = []
    seen = set()
    for job in search_results["jobs_results"]:
        if not isinstance(job, Mapping):
            continue

        title = _clean_text(job.get("title"))
        company = _clean_text(job.get("company_name") or job.get("company"))
        source_url = _job_url(job)
        if not title or not company or not source_url:
            continue

        opportunity = {
            "title": title,
            "company": company,
            "location": _clean_text(job.get("location")),
            "opportunity_type": opportunity_type,
            "source": LIVE_OPPORTUNITY_SOURCE,
            "source_url": source_url,
            "deadline": _deadline(job),
            "is_seeded": False,
        }
        key = _deduplication_key(opportunity)
        if key in seen:
            continue
        seen.add(key)
        normalized.append(opportunity)
    return normalized
