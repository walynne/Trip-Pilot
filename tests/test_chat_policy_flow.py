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
        json={"message": "Plan a trip", "booking_proposal": proposal},
    )

    assert response.status_code == 200
    assert captured == {
        "message": "Plan a trip",
        "booking_proposal": proposal,
    }
    assert response.get_json()["policy_result"]["status"] == "compliant"