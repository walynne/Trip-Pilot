from app import app
from agents.trip_agent import TripAgent


class FakePolicyAgent:
    def __init__(self, result):
        self.result = result
        self.proposals = []

    def evaluate(self, proposal):
        self.proposals.append(proposal)
        return self.result


def complete_proposal():
    return {
        "traveler_role": "manager",
        "city": "Singapore",
        "city_tier": 1,
        "flight": {"cabin": "economy", "duration_hours": 4},
        "total_cost_usd": 2400,
    }


def test_booking_proposal_waits_for_required_approval():
    policy_agent = FakePolicyAgent({
        "status": "compliant",
        "violated_rules": [],
        "missing_facts": [],
        "required_approver": "department_head",
        "explanation": "Within limits; approval is still required.",
    })
    trip_agent = TripAgent.__new__(TripAgent)
    trip_agent.policy_agent = policy_agent

    policy_result, booking_gate = trip_agent._evaluate_booking_proposal(
        complete_proposal()
    )

    assert policy_result["status"] == "compliant"
    assert booking_gate["status"] == "awaiting_approval"
    assert booking_gate["booked"] is False
    assert len(policy_agent.proposals) == 1


def test_incomplete_proposal_fails_closed_before_policy_evaluation():
    policy_agent = FakePolicyAgent({"status": "compliant"})
    trip_agent = TripAgent.__new__(TripAgent)
    trip_agent.policy_agent = policy_agent

    policy_result, booking_gate = trip_agent._evaluate_booking_proposal({
        "flight": {"cabin": "economy"},
    })

    assert policy_result["status"] == "needs_facts"
    assert "flight.duration_hours" in policy_result["missing_facts"]
    assert "total_cost_usd" in policy_result["missing_facts"]
    assert booking_gate["status"] == "blocked_missing_facts"
    assert booking_gate["booked"] is False
    assert policy_agent.proposals == []


def test_trip_plan_gate_requires_hotel_rate_and_city_tier():
    policy_agent = FakePolicyAgent({"status": "compliant"})
    trip_agent = TripAgent.__new__(TripAgent)
    trip_agent.policy_agent = policy_agent

    policy_result, booking_gate = trip_agent._evaluate_booking_proposal({
        "flight": {"cabin": "economy", "duration_hours": 4},
        "total_cost_usd": 800,
        "hotel": {},
    }, require_hotel=True)

    assert policy_result["status"] == "needs_facts"
    assert set(policy_result["missing_facts"]) == {"hotel.nightly_rate_usd", "city_tier"}
    assert booking_gate["status"] == "blocked_missing_facts"
    assert booking_gate["booked"] is False
    assert policy_agent.proposals == []


def test_noncompliant_proposal_is_blocked():
    policy_agent = FakePolicyAgent({
        "status": "non_compliant",
        "violated_rules": ["FLIGHT-CABIN-01"],
        "missing_facts": [],
        "required_approver": None,
        "explanation": "Violates FLIGHT-CABIN-01.",
    })
    trip_agent = TripAgent.__new__(TripAgent)
    trip_agent.policy_agent = policy_agent

    _, booking_gate = trip_agent._evaluate_booking_proposal(complete_proposal())

    assert booking_gate["status"] == "blocked_by_policy"
    assert booking_gate["booked"] is False


def test_trip_run_includes_policy_gate_for_booking_proposal():
    class Extractor:
        def extract(self, message):
            return {
                "origin": "HKG",
                "destination": "SIN",
                "departure_date": "2035-11-15",
            }

    class FlightService:
        def get_flights(self, *args):
            return [{"airline": "Example Air", "price": 300, "currency": "USD"}]

    class Recommender:
        def recommend(self, trip, flights):
            return "Example Air"

    class Monitor:
        def detect(self, trip, flights):
            return {"type": "NORMAL", "severity": "LOW"}

        def analyse(self, trip, event):
            return "No disruption detected."

    policy_agent = FakePolicyAgent({
        "status": "compliant",
        "violated_rules": [],
        "missing_facts": [],
        "required_approver": "department_head",
        "explanation": "Approval is still required.",
    })
    trip_agent = TripAgent.__new__(TripAgent)
    trip_agent.extractor = Extractor()
    trip_agent.flight_service = FlightService()
    trip_agent.recommender = Recommender()
    trip_agent.monitor = Monitor()
    trip_agent.replanner = None
    trip_agent.policy_agent = policy_agent

    result = trip_agent.run("Find a flight", booking_proposal=complete_proposal())

    assert result["policy_result"]["status"] == "compliant"
    assert result["booking_gate"]["status"] == "awaiting_approval"
    assert result["booking_gate"]["booked"] is False


def test_greeting_without_trip_plan_uses_direct_chat_response():
    client = app.test_client()

    response = client.post("/chat", json={"message": "hello"})

    assert response.status_code == 200
    assert isinstance(response.json["recommendation"], str)
    assert "hello".lower() in response.json["recommendation"].lower() or "travel" in response.json["recommendation"].lower()


def test_manager_approval_and_budget_override_are_detected():
    trip_agent = TripAgent.__new__(TripAgent)

    manager_approval = trip_agent._build_approval_request(
        {"traveler_role": "employee", "total_cost_usd": 2100},
        {"status": "compliant", "required_approver": "department_head"},
    )
    assert manager_approval["requires_human_approval"] is True
    assert manager_approval["approval_type"] == "manager"
    assert manager_approval["required_approver"] == "department_head"

    budget_override = trip_agent._build_approval_request(
        {"traveler_role": "employee", "total_cost_usd": 5200},
        {"status": "compliant", "required_approver": None},
    )
    assert budget_override["requires_human_approval"] is True
    assert budget_override["approval_type"] == "budget_override"
    assert budget_override["required_approver"] == "finance_manager"


def test_policy_exception_approval_is_created_for_non_compliance():
    trip_agent = TripAgent.__new__(TripAgent)

    exception_approval = trip_agent._build_approval_request(
        {"traveler_role": "employee", "total_cost_usd": 1400},
        {"status": "non_compliant", "required_approver": None, "violated_rules": ["CABIN_LIMIT"]},
    )

    assert exception_approval["requires_human_approval"] is True
    assert exception_approval["approval_type"] == "policy_exception"
    assert exception_approval["required_approver"] == "travel_policy_approver"