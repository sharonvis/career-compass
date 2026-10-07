"""Focused tests for the SerpAPI Google Jobs client."""

from unittest.mock import Mock

import pytest
import requests

from services import serpapi_client as client


def test_config_reads_api_key_from_environment(monkeypatch):
    monkeypatch.setenv("SERPAPI_API_KEY", "  test-key  ")

    assert client.config.get_serpapi_api_key() == "test-key"


def test_config_returns_none_when_api_key_is_missing(monkeypatch):
    monkeypatch.delenv("SERPAPI_API_KEY", raising=False)

    assert client.config.get_serpapi_api_key() is None


@pytest.fixture
def api_key(monkeypatch):
    monkeypatch.setattr(client.config, "get_serpapi_api_key", lambda: "test-key")


def test_search_opportunities_returns_structured_results_and_builds_focused_query(
    monkeypatch, api_key,
):
    payload = {"jobs_results": [{"title": "Python Intern"}], "search_metadata": {"id": "1"}}
    response = Mock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    get = Mock(return_value=response)
    monkeypatch.setattr(client.requests, "get", get)

    result = client.search_opportunities(
        "internship", keywords="  python   developer ", location="  Bengaluru  ",
    )

    assert result is payload
    get.assert_called_once_with(
        client.SERPAPI_SEARCH_URL,
        params={
            "engine": "google_jobs",
            "q": "python developer internship",
            "location": "Bengaluru",
            "api_key": "test-key",
        },
        timeout=client.DEFAULT_TIMEOUT_SECONDS,
    )


@pytest.mark.parametrize(
    ("opportunity_type", "query"),
    [("internship", "internship"), ("entry_level", "entry level")],
)
def test_search_supports_both_opportunity_types(
    monkeypatch, api_key, opportunity_type, query,
):
    response = Mock()
    response.json.return_value = {"jobs_results": []}
    response.raise_for_status.return_value = None
    get = Mock(return_value=response)
    monkeypatch.setattr(client.requests, "get", get)

    client.search_opportunities(opportunity_type)

    assert get.call_args.kwargs["params"]["q"] == query


def test_search_requires_configured_api_key(monkeypatch):
    get = Mock()
    monkeypatch.setattr(client.config, "get_serpapi_api_key", lambda: None)
    monkeypatch.setattr(client.requests, "get", get)

    with pytest.raises(client.MissingSerpAPIKeyError, match="SERPAPI_API_KEY"):
        client.search_opportunities("internship")

    get.assert_not_called()


def test_search_rejects_unsupported_opportunity_type(monkeypatch, api_key):
    get = Mock()
    monkeypatch.setattr(client.requests, "get", get)

    with pytest.raises(ValueError, match="opportunity_type"):
        client.search_opportunities("contract")

    get.assert_not_called()


def test_search_reports_http_errors(monkeypatch, api_key):
    response = Mock(status_code=503)
    response.raise_for_status.side_effect = requests.HTTPError()
    monkeypatch.setattr(client.requests, "get", Mock(return_value=response))

    with pytest.raises(client.SerpAPIHTTPError, match="HTTP 503"):
        client.search_opportunities("internship")


def test_search_reports_timeouts(monkeypatch, api_key):
    monkeypatch.setattr(
        client.requests, "get", Mock(side_effect=requests.Timeout()),
    )

    with pytest.raises(client.SerpAPITimeoutError, match="timed out"):
        client.search_opportunities("internship")


def test_search_reports_request_errors_without_exposing_request_details(
    monkeypatch, api_key,
):
    monkeypatch.setattr(
        client.requests, "get", Mock(side_effect=requests.ConnectionError("offline")),
    )

    with pytest.raises(client.SerpAPIRequestError, match="request failed") as error:
        client.search_opportunities("internship")

    assert "offline" not in str(error.value)


@pytest.mark.parametrize(
    "payload",
    [[], {"jobs_results": {}}, {"error": "invalid key"}],
)
def test_search_rejects_unexpected_response_shapes(monkeypatch, api_key, payload):
    response = Mock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    monkeypatch.setattr(client.requests, "get", Mock(return_value=response))

    with pytest.raises(client.SerpAPIResponseError, match="jobs_results list"):
        client.search_opportunities("internship")


def test_search_rejects_invalid_json(monkeypatch, api_key):
    response = Mock()
    response.json.side_effect = ValueError("not JSON")
    response.raise_for_status.return_value = None
    monkeypatch.setattr(client.requests, "get", Mock(return_value=response))

    with pytest.raises(client.SerpAPIResponseError, match="invalid JSON"):
        client.search_opportunities("internship")
