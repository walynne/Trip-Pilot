import pytest

import app as app_module


def test_business_visit_routes_to_full_trip_planning():
    assert app_module._is_trip_plan_request(
        "I need to visit tokyo next week for client meetings on Tuesday and Wednesday"
    )
    assert not app_module._is_trip_plan_request("Find a flight to Tokyo")


def test_research_hotels_route_maps_airport_codes_to_cities(monkeypatch):
    class FakeHotelSearchTool:
        def __init__(self, provider="mock", **kwargs):
            self.provider = provider

        def search_hotels(self, location, check_in, check_out, guests=1, rooms=1):
            assert location == "Hong Kong"
            return {
                "location": location,
                "check_in": check_in,
                "check_out": check_out,
                "guests": guests,
                "rooms": rooms,
                "currency": "USD",
                "status": "success",
                "hotels": [{
                    "hotel_id": "ALT-1",
                    "name": "Research Alternative",
                    "pricing": {"currency": "USD", "room_nightly_rate": "125.00", "total": "250.00"},
                }],
                "result_count": 1,
            }

    monkeypatch.setattr(app_module, "HotelSearchTool", FakeHotelSearchTool)

    response = app_module.app.test_client().post(
        "/research-hotels",
        json={"trip": {"destination": "HKG"}, "guests": 2, "rooms": 1},
    )

    assert response.status_code == 200
    result = response.get_json()
    assert result["summary"]["destination"] == "Hong Kong"
    assert result["hotel"]["options"][0]["name"] == "Research Alternative"


def test_research_hotels_route_works_for_partial_trip(monkeypatch):
    class FakeHotelSearchTool:
        def __init__(self, provider="mock", **kwargs):
            self.provider = provider

        def search_hotels(self, location, check_in, check_out, guests=1, rooms=1):
            return {
                "location": location,
                "check_in": check_in,
                "check_out": check_out,
                "guests": guests,
                "rooms": rooms,
                "currency": "USD",
                "status": "success",
                "hotels": [{
                    "hotel_id": "ALT-1",
                    "name": "Research Alternative",
                    "pricing": {"currency": "USD", "room_nightly_rate": "125.00", "total": "250.00"},
                }],
                "result_count": 1,
            }

    monkeypatch.setattr(app_module, "HotelSearchTool", FakeHotelSearchTool)

    response = app_module.app.test_client().post(
        "/research-hotels",
        json={"trip": {"destination": "Singapore"}, "guests": 2, "rooms": 1},
    )

    assert response.status_code == 200
    result = response.get_json()
    assert result["hotel"]["status"] == "success"
    assert result["hotel"]["options"][0]["name"] == "Research Alternative"
    assert result["summary"]["destination"] == "Singapore"


def test_hotel_unavailable_simulation_returns_monitor_and_replan_payload(monkeypatch):
    class FakeMonitor:
        def analyse(self, trip, event):
            return {"severity": "HIGH", "message": "Hotel risk detected"}

    class FakeReplanner:
        def replan(self, trip, event):
            return {
                "replanned": True,
                "recommendation": "Find a replacement hotel near the meeting location.",
                "alternative_flights": [],
            }

    class FakeTripAgent:
        monitor = FakeMonitor()
        replanner = FakeReplanner()

    class FakeDisruptionSimulator:
        def simulate(self, scenario, context):
            return {
                "type": "HOTEL_UNAVAILABLE",
                "severity": "HIGH",
                "message": "Simulated hotel unavailability.",
                "affected_trip": {
                    "hotel": {
                        "hotel_id": "H-100",
                        "location": "Singapore",
                        "check_in": "2026-11-15",
                        "check_out": "2026-11-17",
                        "nights": 2,
                        "guests": 2,
                        "rooms": 1,
                    }
                },
            }

    monkeypatch.setattr(app_module, "trip_agent", FakeTripAgent())
    monkeypatch.setattr(app_module, "DisruptionSimulator", FakeDisruptionSimulator)

    response = app_module.app.test_client().post(
        "/simulate-disruption",
        json={
            "trip": {"origin": "HKG", "destination": "SIN"},
            "scenario": "hotel_unavailable",
            "context": {"trip_id": "demo-trip", "hotel": {"hotel_id": "H-100", "location": "Singapore", "check_in": "2026-11-15", "check_out": "2026-11-17", "guests": 2, "rooms": 1}},
        },
    )

    assert response.status_code == 200
    result = response.get_json()
    assert result["event"]["type"] == "HOTEL_UNAVAILABLE"
    assert result["monitor_result"]["message"] == "Hotel risk detected"
    assert result["replan_result"]["replanned"] is True
    assert result["human_decision_required"] is True


def test_chat_forwards_booking_proposal_to_trip_agent(monkeypatch):
    proposal = {
        "flight": {"cabin": "economy", "duration_hours": 4},
        "total_cost_usd": 800,
    }
    captured = {}

    class FakeTripAgent:
        def run(self, message, booking_proposal=None):
            captured["message"] = message
            captured["booking_proposal"] = booking_proposal
            return {
                "recommendation": "Example result",
                "policy_result": {"status": "compliant"},
                "booking_gate": {"status": "policy_cleared_not_booked", "booked": False},
            }

    monkeypatch.setattr(app_module, "trip_agent", FakeTripAgent())
    response = app_module.app.test_client().post(
        "/chat",
        json={"message": "Find a flight", "booking_proposal": proposal},
    )

    assert response.status_code == 200
    assert captured == {
        "message": "Find a flight",
        "booking_proposal": proposal,
    }
    assert response.get_json()["policy_result"]["status"] == "compliant"


def test_chat_routes_trip_plan_requests_to_planner(monkeypatch):
    requirements = {
        "origin": "HKG",
        "destination": "SIN",
        "departure_date": "2026-11-15",
        "return_date": "2026-11-18",
    }
    captured = {}

    class FakeTripAgent:
        def extract_trip_details(self, message):
            captured["message"] = message
            return requirements

        def _validate_trip(self, trip):
            captured["validated"] = trip

        def _evaluate_booking_proposal(self, proposal, require_hotel=False):
            captured["policy_proposal"] = proposal
            captured["require_hotel"] = require_hotel
            return (
                {
                    "status": "needs_facts",
                    "missing_facts": ["total_cost_usd", "hotel.nightly_rate_usd", "city_tier"],
                    "violated_rules": [],
                    "evidence": [],
                },
                {"status": "blocked_missing_facts", "booked": False, "message": "Facts required."},
            )

    class FakeTravelPlanner:
        def run(self, trip):
            captured["planned"] = trip
            return {
                "summary": {"destination": "Singapore"},
                "flights": {"status": "success", "options": []},
                "hotel": {"status": "success", "budget_total": 450},
                "weather": {"status": "success", "forecast": []},
                "schedule": [],
                "recommendation": "Full trip recommendation",
            }

    monkeypatch.setattr(app_module, "trip_agent", FakeTripAgent())
    monkeypatch.setattr(app_module, "travel_planner", FakeTravelPlanner())

    class DisruptionSimulatorMustNotRun:
        def simulate(self, *args, **kwargs):
            raise AssertionError("Trip planning must not trigger disruption simulation")

    monkeypatch.setattr(app_module, "DisruptionSimulator", DisruptionSimulatorMustNotRun)
    response = app_module.app.test_client().post(
        "/chat",
        json={"message": "Plan a trip to Singapore", "booking_proposal": {}},
    )

    result = response.get_json()
    assert response.status_code == 200
    assert result["summary"]["destination"] == "Singapore"
    assert result["flights"]["status"] == "success"
    assert result["hotel"]["budget_total"] == 450
    assert result["hotel"]["status"] == "success"
    assert result["weather"]["status"] == "success"
    assert result["recommendation"] == "pending"
    assert result["trip_details"] == requirements
    assert all(captured["planned"][key] == value for key, value in requirements.items())
    assert captured["require_hotel"] is True
    assert captured["policy_proposal"]["flight"]["cabin"] == "economy"
    assert result["policy_result"]["status"] == "needs_facts"
    assert result["booking_gate"]["booked"] is False
    assert "event" not in result
    assert "replan_result" not in result


@pytest.mark.parametrize("message", [
    "Check hotel availability for lp123 from 2026-11-15 to 2026-11-17",
    "Search hotel in Singapore from 2026-11-15 to 2026-11-18",
    "Search for hotel in Singapore",
    "Find hotel in Singapore",
    "Search hotels in Singapore",
])
def test_chat_routes_hotel_rate_requests_to_llm_tool_flow(monkeypatch, message):
    captured = {}

    class FakeTripAgent:
        def search_hotel_rates(self, message):
            captured["message"] = message
            return {
                "message": "Two live offers found.",
                "tool_calls": [{"name": "search_google_hotels"}],
                "tool_results": [{"name": "search_google_hotels", "result": {"properties": []}}],
            }

        def run(self, *_args, **_kwargs):
            raise AssertionError("Hotel rate request must not enter flight search")

    monkeypatch.setattr(app_module, "trip_agent", FakeTripAgent())
    response = app_module.app.test_client().post(
        "/chat",
        json={"message": message},
    )

    result = response.get_json()
    assert response.status_code == 200
    assert captured["message"] == message
    assert result["recommendation"] == "Two live offers found."
    assert result["tool_calls"][0]["name"] == "search_google_hotels"
    assert result["tool_results"][0]["result"] == {"properties": []}


def test_hotel_results_and_weather_are_exposed_to_ui(monkeypatch):
    from tools.weather_search import WeatherSearchTool

    class FakeTripAgent:
        def search_hotel_rates(self, message):
            return {
                "message": "Hotel found",
                "tool_results": [{"name": "search_google_hotels", "result": {
                    "status": "success", "query": "Hotels in Singapore",
                    "check_in": "2026-11-15", "check_out": "2026-11-18",
                    "adults": 1, "properties": [{
                        "name": "Test Singapore Hotel", "price_per_night": 100,
                        "total_price": 300, "currency": "SGD",
                    }],
                }}],
            }

    monkeypatch.setattr(app_module, "trip_agent", FakeTripAgent())
    monkeypatch.setattr(app_module.planner_agent, "weather_tool", WeatherSearchTool("mock"))
    response = app_module.app.test_client().post("/chat", json={
        "message": "Search hotel in Singapore from 2026-11-15 to 2026-11-18",
    })
    assert response.status_code == 200
    result = response.get_json()
    assert result["hotel"]["recommended"]["name"] == "Test Singapore Hotel"
    assert result["hotel"]["recommended"]["pricing"]["total"] == "300.00"
    assert result["summary"]["destination"] == "Singapore"
    assert len(result["weather"]["forecast"]) == 4


def test_hotel_results_survive_unavailable_weather(monkeypatch):
    class UnavailableWeather:
        def search_weather(self, *args):
            raise ValueError("live forecast dates must be within destination today through today + 15 days")

    monkeypatch.setattr(app_module.planner_agent, "weather_tool", UnavailableWeather())
    result = {"tool_results": [{"name": "search_google_hotels", "result": {
        "query": "Hotels in Singapore", "check_in": "2030-11-15",
        "check_out": "2030-11-18", "properties": [{
            "name": "Test Hotel", "price_per_night": 100,
        }],
    }}]}
    app_module._attach_hotel_search_details(result)
    assert result["hotel"]["recommended"]["name"] == "Test Hotel"
    assert result["weather"]["status"] == "unavailable"
    assert "15 days" in result["weather"]["message"]


def test_hotel_provider_error_is_exposed_to_ui():
    result = {"tool_results": [{"name": "search_google_hotels", "result": {
        "status": "error", "error": "SerpApi request failed",
    }}]}
    app_module._attach_hotel_search_details(result)
    assert result["hotel"]["status"] == "unavailable"
    assert result["hotel"]["message"] == "SerpApi request failed"