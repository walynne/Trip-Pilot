from services.flight_service import FlightService
from utils.demo_data import load_demo_trip_data


def test_load_demo_trip_data_returns_expected_sections():
    payload = load_demo_trip_data()

    assert payload["source"] == "demo"
    assert "flights" in payload
    assert "hotel" in payload
    assert "weather" in payload
    assert payload["flights"][0]["airline"]


def test_flight_service_uses_demo_payload_when_live_search_fails():
    service = FlightService(provider="duffel")
    service.tool = type("BrokenTool", (), {"search_flights": lambda self, *args, **kwargs: (_ for _ in ()).throw(RuntimeError("API down"))})()

    flights = service.get_flights("SIN", "LHR", "2026-11-12", "2026-11-16")

    assert flights
    assert flights[0]["provider"] == "demo"
    assert flights[0]["data_mode"] == "mock"
