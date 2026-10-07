"""Fetch structured Google Jobs results through SerpAPI."""

import requests

import config


SERPAPI_SEARCH_URL = "https://serpapi.com/search.json"
DEFAULT_TIMEOUT_SECONDS = 10
OPPORTUNITY_SEARCH_TERMS = {
    "internship": "internship",
    "entry_level": "entry level",
}


class SerpAPIError(RuntimeError):
    """Base error for SerpAPI search failures."""


class MissingSerpAPIKeyError(SerpAPIError):
    """SerpAPI credentials are not configured."""


class SerpAPIHTTPError(SerpAPIError):
    """SerpAPI returned an unsuccessful HTTP status."""


class SerpAPITimeoutError(SerpAPIError):
    """The SerpAPI request exceeded its timeout."""


class SerpAPIRequestError(SerpAPIError):
    """The SerpAPI request failed before receiving a response."""


class SerpAPIResponseError(SerpAPIError):
    """SerpAPI returned invalid or unexpected response data."""


def search_opportunities(
    opportunity_type: str,
    keywords: str | None = None,
    location: str | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict:
    """Return the raw structured SerpAPI response for a focused jobs search."""
    if opportunity_type not in OPPORTUNITY_SEARCH_TERMS:
        raise ValueError("opportunity_type must be 'internship' or 'entry_level'")

    api_key = config.get_serpapi_api_key()
    if not api_key:
        raise MissingSerpAPIKeyError("SERPAPI_API_KEY is not configured")

    search_term = OPPORTUNITY_SEARCH_TERMS[opportunity_type]
    if keywords is not None:
        if not isinstance(keywords, str):
            raise ValueError("keywords must be a string or None")
        keywords = " ".join(keywords.split())
        if keywords:
            search_term = f"{keywords} {search_term}"

    params = {
        "engine": "google_jobs",
        "q": search_term,
        "api_key": api_key,
    }
    if location is not None:
        if not isinstance(location, str):
            raise ValueError("location must be a string or None")
        location = " ".join(location.split())
        if location:
            params["location"] = location

    try:
        response = requests.get(SERPAPI_SEARCH_URL, params=params, timeout=timeout)
    except requests.Timeout:
        raise SerpAPITimeoutError("SerpAPI request timed out") from None
    except requests.RequestException:
        raise SerpAPIRequestError("SerpAPI request failed") from None

    try:
        response.raise_for_status()
    except requests.HTTPError:
        raise SerpAPIHTTPError(
            f"SerpAPI returned HTTP {response.status_code}"
        ) from None

    try:
        result = response.json()
    except ValueError:
        raise SerpAPIResponseError("SerpAPI returned invalid JSON") from None

    if not isinstance(result, dict) or not isinstance(result.get("jobs_results"), list):
        raise SerpAPIResponseError("SerpAPI response must contain a jobs_results list")

    return result
