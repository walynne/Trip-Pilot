import app as app_module


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

    class FakePlannerAgent:
        def plan_trip(self, trip):
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
    monkeypatch.setattr(app_module, "planner_agent", FakePlannerAgent())
    response = app_module.app.test_client().post(
        "/chat",
        json={"message": "Plan a trip to Singapore"},
    )

    result = response.get_json()
    assert response.status_code == 200
    assert result["hotel"]["budget_total"] == 450
    assert result["recommendation"] == "Full trip recommendation"
    assert result["trip_details"] == requirements
    assert captured["planned"] == requirements
    assert captured["require_hotel"] is True
    assert captured["policy_proposal"]["flight"]["cabin"] == "economy"
    assert result["policy_result"]["status"] == "needs_facts"
    assert result["booking_gate"]["booked"] is False