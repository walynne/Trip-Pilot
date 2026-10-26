from unittest.mock import Mock

import pytest

from tools.google_flights_tool import FlightSearchError, GoogleFlightsSearchTool
from services.flight_service import FlightService


def offer(airline="Cathay Pacific", price=300, origin="HKG", destination="NRT", **extra):
    return {
        "flights": [{
            "airline": airline,
            "departure_airport": {"id": origin, "time": "2030-11-15 09:00"},
            "arrival_airport": {"id": destination, "time": "2030-11-15 14:00"},
        }], "price": price, "total_duration": 240, **extra,
    }


def test_one_way_maps_live_listing_and_ranks_all_options(monkeypatch):
    tool = GoogleFlightsSearchTool(api_key="test-key")
    request = Mock(return_value={"other_flights": [offer(price=500), offer(price=200)]})
    monkeypatch.setattr(tool, "_request", request)
    result = tool.search_flights("HKG", "NRT", "2030-11-15")["flights"]
    assert result[0]["price"] == "200.00"
    assert result[0]["origin"] == "HKG"
    assert result[0]["airline"] == "Cathay Pacific"
    assert result[0]["data_mode"] == "live"
    assert request.call_args.args[0]["type"] == 2


def test_round_trip_selects_return_and_uses_whole_trip_price(monkeypatch):
    tool = GoogleFlightsSearchTool(api_key="test-key")
    request = Mock(side_effect=[
        {"best_flights": [offer(price=500, departure_token="outbound-token")]},
        {"other_flights": [offer(price=550, origin="NRT", destination="HKG")]},
    ])
    monkeypatch.setattr(tool, "_request", request)
    result = tool.search_flights("HKG", "NRT", "2030-11-15", "2030-11-18")["flights"][0]
    assert result["price"] == "550.00"
    assert result["return_origin"] == "NRT"
    assert result["return_destination"] == "HKG"
    assert request.call_args.args[0]["departure_token"] == "outbound-token"


def test_provider_error_does_not_expose_api_key(monkeypatch):
    response = Mock(status_code=401)
    monkeypatch.setattr("tools.google_flights_tool.requests.get", Mock(return_value=response))
    with pytest.raises(FlightSearchError, match="rejected the API key"):
        GoogleFlightsSearchTool(api_key="secret").search_flights("HKG", "NRT", "2030-11-15")


def test_empty_search_returns_no_fabricated_flights(monkeypatch):
    tool = GoogleFlightsSearchTool(api_key="test-key")
    monkeypatch.setattr(tool, "_request", lambda params: {})
    assert tool.search_flights("HKG", "NRT", "2030-11-15") == {"flights": []}


def test_service_provider_selection_and_ranking(monkeypatch):
    monkeypatch.setenv("TRIPPILOT_FLIGHT_PROVIDER", "serpapi")
    service = FlightService()
    assert isinstance(service.tool, GoogleFlightsSearchTool)
    monkeypatch.setattr(service.tool, "search_flights", lambda *args: {"flights": [
        {"stops": 1, "price": "100"}, {"stops": 0, "price": "300"},
    ]})
    assert service.get_flights("HKG", "NRT", "2030-11-15")[0]["stops"] == 0


def test_planner_propagates_live_provider_failure():
    from agents.planner_agent import PlannerAgent
    planner = PlannerAgent.__new__(PlannerAgent)
    planner.flight_service = Mock()
    planner.flight_service.get_flights.side_effect = FlightSearchError("Provider unavailable")
    with pytest.raises(FlightSearchError):
        planner._search_flights("HKG", "NRT", "2030-11-15")