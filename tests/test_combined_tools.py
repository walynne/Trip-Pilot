"""Tool-layer contracts only: stubbed C1 HTTP plus explicit C2/C3 mocks.

The collector is a test harness, not an application orchestrator or TripAgent change.
"""
import json
from decimal import Decimal
from unittest.mock import Mock

import pytest
import requests

from agents.trip_agent import TripAgent
from services.flight_service import FlightService
from tools.flight_search import FlightSearchTool
from tools.hotel_search import HotelError, HotelSearchTool
from tools.openmeteo_client import WeatherError
from tools.weather_search import WeatherSearchTool


@pytest.fixture
def singapore_trip():
    # Explicit destination-local dates: never derive these from departure_date.
    return {
        "origin": "HKG", "destination": "SIN", "departure_date": "2030-11-14",
        "location": "Singapore", "destination_timezone": "Asia/Singapore",
        "check_in": "2030-11-15", "check_out": "2030-11-18",
        "weather_start": "2030-11-15", "weather_end": "2030-11-17",
        "guests": 1, "rooms": 1,
    }


@pytest.fixture(autouse=True)
def flight_http(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Unexpected external HTTP request in combined test")

    monkeypatch.setattr(requests.sessions.Session, "request", forbidden)
    monkeypatch.setenv("DUFFEL_BASE_URL", "https://duffel.invalid")
    monkeypatch.delenv("DUFFEL_API_KEY", raising=False)
    post_response = Mock(status_code=200, text="Synthetic offline flight request")
    post_response.json.return_value = {"data": {"id": "stub-request"}}
    get_response = Mock(status_code=200)
    get_response.json.return_value = {"data": [{
        "id": "stub-offer", "owner": {"name": "Sample Airline"},
        "total_amount": "1500.00", "total_currency": "HKD",
    }]}
    post = Mock(return_value=post_response)
    get = Mock(return_value=get_response)
    monkeypatch.setattr(requests, "post", post)
    monkeypatch.setattr(requests, "get", get)
    return post, get


def collect_tools(trip, hotel_scenario="standard", weather_scenario="normal"):
    """Test-only composition: explicit error boundaries keep independent results."""
    result = {}
    try:
        result["flights"] = {
            "status": "success", "provider": "duffel", "data_mode": "stubbed",
            "data": FlightSearchTool().search_flights(
                trip["origin"], trip["destination"], trip["departure_date"]),
        }
    except requests.exceptions.RequestException:
        result["flights"] = {
            "status": "unavailable", "provider": "duffel", "data_mode": "stubbed",
            "error_code": "flight_provider_error",
        }
    try:
        result["hotels"] = HotelSearchTool(provider="mock", mock_scenario=hotel_scenario).search_hotels(
            trip["location"], trip["check_in"], trip["check_out"],
            guests=trip["guests"], rooms=trip["rooms"])
    except (HotelError, ValueError) as exc:
        result["hotels"] = {
            "status": "unavailable", "provider": "mock", "data_mode": "mock",
            "error_code": exc.code if isinstance(exc, HotelError) else "invalid_input",
        }
    try:
        result["weather"] = WeatherSearchTool(provider="mock", mock_scenario=weather_scenario).search_weather(
            trip["location"], trip["weather_start"], trip["weather_end"])
    except (WeatherError, ValueError) as exc:
        result["weather"] = {
            "status": "unavailable", "provider": "mock", "data_mode": "mock",
            "error_code": exc.code if isinstance(exc, WeatherError) else "invalid_input",
        }
    return result


def test_successful_independent_tool_results(singapore_trip, flight_http):
    result = collect_tools(singapore_trip)
    assert set(result) == {"flights", "hotels", "weather"}
    assert all(value["status"] == "success" for value in result.values())
    assert result["flights"]["data"]["data"][0]["id"] == "stub-offer"
    assert len(result["hotels"]["hotels"]) == len(result["weather"]["forecast"]) == 3
    post, get = flight_http
    post.assert_called_once()
    get.assert_called_once()
    assert post.call_args.kwargs["json"]["data"]["slices"] == [{
        "origin": "HKG", "destination": "SIN", "departure_date": "2030-11-14"}]
    assert get.call_args.kwargs["params"] == {"offer_request_id": "stub-request"}
    # Only the flight HTTP stub is touched; hotel/weather mock mode performs no requests.


def test_explicit_destination_dates_not_departure(singapore_trip):
    result = collect_tools(singapore_trip)
    assert result["hotels"]["check_in"] == "2030-11-15"
    assert result["weather"]["forecast"][0]["date"] == "2030-11-15"
    assert result["weather"]["forecast"][-1]["date"] == "2030-11-17"
    assert result["weather"]["timezone"] == singapore_trip["destination_timezone"]
    assert singapore_trip["departure_date"] != result["hotels"]["check_in"]


def test_hotel_nights_currency_and_amounts(singapore_trip):
    result = collect_tools(singapore_trip)["hotels"]
    assert result["nights"] == 3 and result["currency"] == "SGD"
    cheapest = result["hotels"][0]["pricing"]
    assert cheapest == {
        "currency": "SGD", "room_nightly_rate": "115.00", "room_count": 1,
        "night_count": 3, "subtotal": "345.00", "taxes": "34.50", "fees": "12.00",
        "total": "391.50", "taxes_are_simulated": True,
    }


def test_separate_mock_and_stub_provenance(singapore_trip):
    result = collect_tools(singapore_trip)
    assert result["flights"]["data_mode"] == "stubbed"
    assert result["flights"]["provider"] == "duffel"
    assert result["hotels"]["data_mode"] == result["hotels"]["provider"] == "mock"
    assert result["weather"]["data_mode"] == result["weather"]["provider"] == "mock"
    assert all(row["pricing"]["taxes_are_simulated"] for row in result["hotels"]["hotels"])
    assert all(row["booking_url"] is None for row in result["hotels"]["hotels"])
    assert result["weather"]["official_alerts"] == []
    assert not any("policy_compliant" in row for row in result["hotels"]["hotels"])


def test_weather_high_risk_is_simulated_assessment(singapore_trip):
    result = collect_tools(singapore_trip, weather_scenario="severe")
    events = result["weather"]["disruption_events"]
    assert len(events) == 3
    assert [event["affected_date"] for event in events] == ["2030-11-15", "2030-11-16", "2030-11-17"]
    for event in events:
        assert event == {
            "event_type": "weather_disruption", "location": "Singapore",
            "affected_date": event["affected_date"], "severity": "high",
            "requires_replanning_assessment": True, "source": "weather_search",
            "data_mode": "mock", "signal_type": "simulated", "confirmed_disruption": False,
        }
    assert result["hotels"]["status"] == result["flights"]["status"] == "success"


def test_hotel_fully_booked_does_not_disable_other_tools(singapore_trip):
    result = collect_tools(singapore_trip, hotel_scenario="fully_booked")
    assert result["hotels"]["status"] == "no_results"
    assert result["hotels"]["hotels"] == []
    assert result["hotels"]["data_mode"] == "mock"
    assert result["weather"]["status"] == result["flights"]["status"] == "success"


def test_hotel_price_spike_is_not_a_policy_verdict(singapore_trip):
    standard = collect_tools(singapore_trip)
    spiked = collect_tools(singapore_trip, hotel_scenario="price_spike")
    by_id = {row["hotel_id"]: row for row in standard["hotels"]["hotels"]}
    for row in spiked["hotels"]["hotels"]:
        original_rate = Decimal(by_id[row["hotel_id"]]["pricing"]["room_nightly_rate"])
        assert Decimal(row["pricing"]["room_nightly_rate"]) == original_rate * Decimal("1.50")
        assert "policy_compliant" not in row and "approval_required" not in row
    assert spiked["hotels"]["data_mode"] == "mock"
    assert spiked["flights"] == standard["flights"]
    assert spiked["weather"]["forecast"] == standard["weather"]["forecast"]


@pytest.mark.parametrize("failed_provider", ["flights", "hotels", "weather"])
def test_provider_failure_isolated(singapore_trip, flight_http, failed_provider):
    baseline = collect_tools(singapore_trip)
    hotel_scenario, weather_scenario = "standard", "normal"
    if failed_provider == "flights":
        flight_http[0].side_effect = requests.exceptions.Timeout("upstream text not exposed")
    elif failed_provider == "hotels":
        hotel_scenario = "provider_error"
    else:
        weather_scenario = "provider_error"
    result = collect_tools(singapore_trip, hotel_scenario, weather_scenario)
    assert result[failed_provider]["status"] == "unavailable"
    assert "error_code" in result[failed_provider]
    assert "upstream text" not in json.dumps(result)
    for provider in set(result) - {failed_provider}:
        before = {k: v for k, v in baseline[provider].items() if k != "retrieved_at"}
        after = {k: v for k, v in result[provider].items() if k != "retrieved_at"}
        assert after == before


@pytest.mark.parametrize("start,end", [("invalid", "2030-11-17"), ("2030-11-18", "2030-11-15"), ("2030-02-30", "2030-03-01")])
def test_invalid_destination_dates_keep_flights_usable(singapore_trip, start, end):
    singapore_trip.update(check_in=start, check_out=end, weather_start=start, weather_end=end)
    result = collect_tools(singapore_trip)
    assert result["flights"]["status"] == "success"
    assert result["hotels"]["error_code"] == result["weather"]["error_code"] == "invalid_input"


def test_checkout_exclusive_weather_inclusive_are_distinct(singapore_trip):
    singapore_trip.update(check_out="2030-11-15", weather_end="2030-11-15")
    result = collect_tools(singapore_trip)
    assert result["hotels"]["error_code"] == "invalid_input"
    assert result["weather"]["status"] == "success"
    assert len(result["weather"]["forecast"]) == 1
    assert result["flights"]["status"] == "success"


@pytest.mark.parametrize("hotel_scenario,weather_scenario", [
    ("standard", "normal"), ("fully_booked", "severe"), ("provider_error", "unavailable"),
])
def test_combined_json_serialization(singapore_trip, hotel_scenario, weather_scenario):
    result = collect_tools(singapore_trip, hotel_scenario, weather_scenario)
    assert json.loads(json.dumps(result, allow_nan=False)) == result


def test_existing_flight_service_and_trip_agent_contract(singapore_trip):
    flights = FlightService().get_flights("HKG", "SIN", singapore_trip["departure_date"])
    assert flights == [{"airline": "Sample Airline", "price": "1500.00", "currency": "HKD"}]
    agent = TripAgent.__new__(TripAgent)
    requirements = {k: singapore_trip[k] for k in ["origin", "destination", "departure_date"]}
    agent.extract_trip_details = Mock(return_value=requirements)
    agent.flight_service = Mock()
    agent.flight_service.get_flights.return_value = flights
    agent.recommend_flights = Mock(return_value="Sample recommendation")
    response = agent.run("Business trip to Singapore")
    assert set(response) == {"requirements", "flights", "recommendation", "agent_steps"}
    assert response["flights"] == flights and response["requirements"] == requirements
    assert response["recommendation"] == "Sample recommendation"
    collected = collect_tools(singapore_trip, hotel_scenario="provider_error", weather_scenario="provider_error")
    original = dict(response)
    response["hotels"] = collected["hotels"]
    response["weather"] = collected["weather"]
    assert all(response[key] == value for key, value in original.items())
    assert response["flights"] == flights and response["recommendation"] == "Sample recommendation"
    assert collected["hotels"]["status"] == collected["weather"]["status"] == "unavailable"
