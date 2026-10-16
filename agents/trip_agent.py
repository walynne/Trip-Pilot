from llm.nexllm_client import (
    NexLLMClient
)

from services.flight_service import (
    FlightService
)

from agents.extraction_agent import (
    ExtractionAgent
)

from agents.recommendation_agent import (
    RecommendationAgent
)

from agents.monitoring_agent import (
    MonitoringAgent
)

from agents.replanning_agent import (
    ReplanningAgent
)
from agents.policy_agent import PolicyAgent
from rag.document_loader import PolicyRetrievalError
from utils.airport_mapper import (
    is_iata_code
)
from utils.travel_dates import (
    ensure_valid_return_date
)


class TripAgent:

    def __init__(self, policy_agent=None):

        self.llm = NexLLMClient()
        self.policy_agent = policy_agent

        self.flight_service = (
            FlightService()
        )

        self.extractor = (
            ExtractionAgent(
                self.llm
            )
        )

        self.recommender = (
            RecommendationAgent(
                self.llm
            )
        )

        self.monitor = (
            MonitoringAgent(
                self.llm
            )
        )

        self.replanner = (
            ReplanningAgent(
                self.llm,
                self.flight_service
            )
        )

    def run(
        self,
        user_message,
        booking_proposal=None
    ):

        trip = (
            self.extractor.extract(
                user_message
            )
        )

        print("\nTRIP")
        print(trip)

        self._validate_trip(
            trip
        )

        flights = (
            self.flight_service
            .get_flights(
                trip["origin"],
                trip["destination"],
                trip["departure_date"],
                trip.get("return_date")
            )
        )

        recommendation = (
            self.recommender.recommend(
                trip,
                flights
            )
        )

        event = (
            self.monitor.detect(
                trip,
                flights
            )
        )

        monitoring = (
            self.monitor.analyse(
                trip,
                event
            )
        )

        replan = None

        if event["severity"] in [
            "HIGH",
            "MEDIUM"
        ]:

            replan = (
                self.replanner.replan(
                    trip,
                    event
                )
            )

        result = {
            "agent_steps": [
                "Extracted travel requirements",
                f"Searching {trip['origin']} → {trip['destination']}",
                "Retrieved flight offers",
                "Generated recommendation",
                "Monitoring agent executed",
                f"Detected {event['type']}",
                "Replanning executed"
                if replan
                else "No replanning required"
            ],
            "trip_details": trip,
            "flights": flights,
            "recommendation": recommendation,
            "event": event,
            "monitor_result": monitoring,
            "replan_result": replan
        }

        if booking_proposal is not None:
            policy_result, booking_gate = self._evaluate_booking_proposal(
                booking_proposal
            )
            result["policy_result"] = policy_result
            result["booking_gate"] = booking_gate
            result["agent_steps"].append("Evaluated booking proposal against policy")
            result["agent_steps"].append(
                f"Booking gate: {booking_gate['status']}"
            )

        return result

    def _evaluate_booking_proposal(self, proposal):
        if not isinstance(proposal, dict):
            policy_result = self._policy_error(
                "invalid_proposal",
                "Booking proposal must be an object."
            )
            return policy_result, self._booking_gate(
                "error",
                "Policy evaluation could not run. No booking was placed."
            )

        flight = proposal.get("flight")
        if not isinstance(flight, dict):
            flight = {}
        hotel = proposal.get("hotel")
        if not isinstance(hotel, dict):
            hotel = {}

        missing = []
        cabin = flight.get("cabin")
        if cabin not in {"economy", "premium_economy", "business"}:
            missing.append("flight.cabin")
        hours = flight.get("duration_hours")
        if (isinstance(hours, bool) or not isinstance(hours, (int, float))
                or hours <= 0):
            missing.append("flight.duration_hours")
        total = proposal.get("total_cost_usd")
        if (isinstance(total, bool) or not isinstance(total, (int, float))
                or total <= 0):
            missing.append("total_cost_usd")
        if ((hotel.get("nightly_rate_usd") is not None
             or proposal.get("meals_usd") is not None)
                and proposal.get("city_tier") not in (1, 2, 3)):
            missing.append("city_tier")

        if missing:
            policy_result = {
                "status": "needs_facts",
                "violated_rules": [],
                "missing_facts": missing,
                "required_approver": None,
                "explanation": "Missing booking facts: " + ", ".join(missing),
                "evidence": [],
            }
            return policy_result, self._booking_gate(
                "needs_facts",
                "Provide the missing facts before a booking can be considered."
            )

        try:
            policy_agent = self.policy_agent
            if policy_agent is None:
                policy_agent = PolicyAgent(llm=self.llm)
                self.policy_agent = policy_agent
            policy_result = policy_agent.evaluate(proposal)
        except PolicyRetrievalError as error:
            policy_result = self._policy_error(error.code, str(error))
        except Exception as error:
            policy_result = self._policy_error(
                "policy_evaluation_failed",
                str(error)
            )

        return policy_result, self._booking_gate(
            policy_result.get("status"),
            policy_result.get("explanation", "Policy result is unavailable."),
            policy_result.get("required_approver")
        )

    def _booking_gate(self, policy_status, explanation, approver=None):
        if policy_status == "compliant" and approver:
            status = "awaiting_approval"
            message = f"Policy requires approval from {approver}. No booking was placed."
        elif policy_status == "compliant":
            status = "policy_cleared_not_booked"
            message = "Policy checks passed, but no booking operation is available."
        elif policy_status == "escalate":
            status = "human_review_required"
            message = "Policy requires human review. No booking was placed."
        elif policy_status == "non_compliant":
            status = "blocked_by_policy"
            message = "The proposal violates policy. No booking was placed."
        elif policy_status == "needs_facts":
            status = "blocked_missing_facts"
            message = "Required policy facts are missing. No booking was placed."
        else:
            status = "blocked_policy_error"
            message = "Policy could not be verified. No booking was placed."

        return {
            "status": status,
            "booked": False,
            "message": message,
            "policy_explanation": explanation,
        }

    def _policy_error(self, code, message):
        return {
            "status": "error",
            "violated_rules": [],
            "missing_facts": [],
            "required_approver": None,
            "explanation": message,
            "evidence": [],
            "error": {"code": code, "message": message},
        }

    def _validate_trip(
        self,
        trip
    ):

        origin = trip.get(
            "origin"
        )

        destination = trip.get(
            "destination"
        )

        departure_date = trip.get(
            "departure_date"
        )

        return_date = trip.get(
            "return_date"
        )

        if not is_iata_code(origin):
            raise ValueError(
                "Origin airport is required. Please provide a valid 3-letter IATA code or city, for example HKG or Hong Kong."
            )

        if not is_iata_code(destination):
            raise ValueError(
                "Destination airport is required. Please provide a valid 3-letter IATA code or city, for example LHR or London."
            )

        if not departure_date:
            raise ValueError(
                "Departure date is required. Please provide a future travel date."
            )

        if return_date:
            ensure_valid_return_date(
                departure_date,
                return_date
            )