"""Focused tests for live SerpAPI opportunity normalization."""

from datetime import date

import pytest

from services.opportunity_normalizer import (
    LIVE_OPPORTUNITY_SOURCE,
    normalize_opportunity_results,
)


def job(**overrides):
    result = {
        "title": "Software Engineering Intern",
        "company_name": "Example Labs",
        "location": "Bengaluru, India",
        "share_link": "https://www.google.com/search?jobs=example",
        "deadline": "2026-12-31",
        "description": "Role details are not stored by the existing Opportunity model.",
    }
    result.update(overrides)
    return result


def test_normalizes_valid_job_to_existing_opportunity_fields():
    result = normalize_opportunity_results(
        {"jobs_results": [job()]}, opportunity_type="internship",
    )

    assert result == [{
        "title": "Software Engineering Intern",
        "company": "Example Labs",
        "location": "Bengaluru, India",
        "opportunity_type": "internship",
        "source": LIVE_OPPORTUNITY_SOURCE,
        "source_url": "https://www.google.com/search?jobs=example",
        "deadline": date(2026, 12, 31),
        "is_seeded": False,
    }]


@pytest.mark.parametrize("missing", ["title", "company", "source_url"])
def test_skips_jobs_missing_required_fields(missing):
    fields = {"title": "title", "company": "company_name", "source_url": "share_link"}
    incomplete_job = job()
    incomplete_job.pop(fields[missing])
    assert normalize_opportunity_results(
        {"jobs_results": [incomplete_job]},
        opportunity_type="internship",
    ) == []


def test_optional_fields_are_safe_when_missing_or_malformed():
    result = normalize_opportunity_results(
        {"jobs_results": [job(location=None, deadline="not a date")]},
        opportunity_type="entry_level",
    )

    assert result[0]["location"] is None
    assert result[0]["deadline"] is None
    assert result[0]["opportunity_type"] == "entry_level"


def test_cleans_whitespace_and_html_text_formatting():
    result = normalize_opportunity_results(
        {"jobs_results": [job(
            title="  Python&nbsp; \n Developer  ",
            company_name="  Example \t Labs ",
            location="  Bengaluru\n,  India ",
        )]},
        opportunity_type="internship",
    )

    assert result[0]["title"] == "Python Developer"
    assert result[0]["company"] == "Example Labs"
    assert result[0]["location"] == "Bengaluru, India"


def test_deduplicates_case_and_whitespace_variants_using_contract_key():
    results = [
        job(),
        job(
            title=" software engineering   intern ",
            company_name="EXAMPLE LABS",
            location="Bengaluru, INDIA",
            share_link="https://jobs.example.com/duplicate",
        ),
    ]

    normalized = normalize_opportunity_results(
        {"jobs_results": results}, opportunity_type="internship",
    )

    assert len(normalized) == 1
    assert normalized[0]["source_url"] == "https://www.google.com/search?jobs=example"


@pytest.mark.parametrize(
    "response",
    [None, [], {}, {"jobs_results": {}}, {"jobs_results": None}],
)
def test_rejects_malformed_top_level_serpapi_response(response):
    with pytest.raises(ValueError, match="jobs_results list"):
        normalize_opportunity_results(response, opportunity_type="internship")


def test_skips_malformed_job_entries_but_keeps_valid_results():
    normalized = normalize_opportunity_results(
        {"jobs_results": [None, "not a job", {"title": "Only title"}, job()]},
        opportunity_type="internship",
    )

    assert len(normalized) == 1
    assert normalized[0]["company"] == "Example Labs"


def test_live_source_is_distinct_from_seed_convention():
    normalized = normalize_opportunity_results(
        {"jobs_results": [job()]}, opportunity_type="internship",
    )

    assert normalized[0]["source"] != "seed"
    assert normalized[0]["is_seeded"] is False


@pytest.mark.parametrize("deadline", ["2026-12-31T23:59:00Z", "Dec 31, 2026", "12/31/2026"])
def test_parses_supported_deadline_formats(deadline):
    normalized = normalize_opportunity_results(
        {"jobs_results": [job(deadline=deadline)]},
        opportunity_type="internship",
    )

    assert normalized[0]["deadline"] == date(2026, 12, 31)
