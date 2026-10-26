from unittest.mock import Mock

import pytest
import requests

from tools.activity_search import ActivitySearchTool
from services.activity_service import build_activity_schedule


def test_any_destination_search_and_normalization(monkeypatch):
    response = Mock(status_code=200)
    response.json.return_value = {"local_results": [
        {"title": "City Museum", "place_id": "abc"},
        {"title": "City Museum", "place_id": "abc"}, {}, None,
        {"title": "Central Park"},
    ]}
    get = Mock(return_value=response)
    monkeypatch.setattr("tools.activity_search.requests.get", get)
    result = ActivitySearchTool("secret").search("Reykjavik")
    assert result["status"] == "success"
    assert len(result["places"]) == 2
    assert "Reykjavik" in get.call_args.kwargs["params"]["q"]
    schedule = build_activity_schedule("Reykjavik", "2030-11-15", "2030-11-17", [], result)
    assert "City Museum" in schedule[0]["suggested_activity"]
    assert schedule[0]["activity_source"] == "live_search"
    assert schedule[0]["source_url"].startswith("https://www.google.com/maps/search/")
    assert "Central Park" in schedule[1]["suggested_activity"]
    assert schedule[2]["activity_source"] == "offline_advice"


@pytest.mark.parametrize("status", [401, 403, 429, 500])
def test_http_failure_is_safe(monkeypatch, status):
    response = Mock(status_code=status)
    response.raise_for_status.side_effect = requests.HTTPError("secret URL")
    monkeypatch.setattr("tools.activity_search.requests.get", Mock(return_value=response))
    result = ActivitySearchTool("secret").search("Paris")
    assert result["status"] == "unavailable"
    assert "secret" not in str(result)


@pytest.mark.parametrize("payload, status", [({}, "empty"), ({"error": "secret"}, "unavailable"), ([], "unavailable")])
def test_empty_or_invalid_response(monkeypatch, payload, status):
    response = Mock(status_code=200)
    response.json.return_value = payload
    monkeypatch.setattr("tools.activity_search.requests.get", Mock(return_value=response))
    assert ActivitySearchTool("secret").search("Lima")["status"] == status


def test_missing_key_does_not_call_provider(monkeypatch):
    get = Mock()
    monkeypatch.setattr("tools.activity_search.requests.get", get)
    assert ActivitySearchTool("").search("Lima")["status"] == "unavailable"
    get.assert_not_called()


def test_timeout_falls_back(monkeypatch):
    monkeypatch.setattr("tools.activity_search.requests.get", Mock(side_effect=requests.Timeout("secret")))
    assert ActivitySearchTool("secret").search("Lima")["status"] == "unavailable"


def test_high_risk_overrides_live_suggestion():
    result = {"status": "success", "places": [{"name": "Outdoor Park", "source_url": "https://www.google.com/"}]}
    schedule = build_activity_schedule("Lima", "2030-11-15", "2030-11-15", [
        {"date": "2030-11-15", "risk_level": "high"},
    ], result)
    assert "Outdoor Park" not in schedule[0]["suggested_activity"]
    assert schedule[0]["activity_source"] == "offline_advice"