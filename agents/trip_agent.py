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
from tools.google_hotels_tool import GoogleHotelsSearchTool, SEARCH_GOOGLE_HOTELS_SCHEMA


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
            self.extract_trip_details(
                user_message
            )
        )

        print("\nTRIP")
        print(trip)

        self._validate_trip(
            trip
        )

        flight_args = [
            trip["origin"],
            trip["destination"],
            trip["departure_date"],
        ]
        if trip.get("return_date"):
            flight_args.append(trip["return_date"])

        flights = self.flight_service.get_flights(*flight_args)

        recommendation = (
            self.recommend_flights(
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

        legacy_override = (
            "extract_trip_details" in self.__dict__
            or "recommend_flights" in self.__dict__
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
            "requirements": trip,
            "flights": flights,
            "recommendation": recommendation,
        }

        if not legacy_override:
            result.update({
                "trip_details": trip,
                "event": event,
                "monitor_result": monitoring,
                "replan_result": replan,
            })

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

    def search_hotel_rates(self, user_message):
        """Let the LLM search Google Hotels through SerpApi."""
        return self.llm.chat_with_tools(
            "You help search Google Hotels. Use the search_google_hotels function for hotel requests. Preserve the user's destination and preferences in query, and use only dates and adult counts stated or clearly established in context. Do not invent dates or claim prices are guaranteed. Ask for missing check-in or check-out dates.",
            user_message,
            tools=[SEARCH_GOOGLE_HOTELS_SCHEMA],
            tool_handlers={
                "search_google_hotels": lambda **kwargs: GoogleHotelsSearchTool().search_google_hotels(**kwargs),
            },
        )

    def extract_trip_details(
        self,
        user_message
    ):

        return self.extractor.extract(
            user_message
        )

    def recommend_flights(
        self,
        trip,
        flights
    ):

        return self.recommender.recommend(
            trip,
            flights
        )

    def _evaluate_booking_proposal(self, proposal, require_hotel=False):
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
        nightly_rate = hotel.get("nightly_rate_usd")
        if require_hotel and (
                isinstance(nightly_rate, bool)
                or not isinstance(nightly_rate, (int, float))
                or nightly_rate <= 0):
            missing.append("hotel.nightly_rate_usd")
        needs_city_tier = (
            require_hotel
            or hotel.get("nightly_rate_usd") is not None
            or proposal.get("meals_usd") is not None
        )
        if needs_city_tier and proposal.get("city_tier") not in (1, 2, 3):
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

        approval_request = self._build_approval_request(proposal, policy_result)
        if approval_request.get("required_approver"):
            policy_result["required_approver"] = approval_request["required_approver"]
            policy_result["approval_type"] = approval_request["approval_type"]
            policy_result["approval_reason"] = approval_request["reason"]

        return policy_result, self._booking_gate(
            policy_result.get("status"),
            policy_result.get("explanation", "Policy result is unavailable."),
            approval_request.get("required_approver") or policy_result.get("required_approver"),
            approval_type=approval_request.get("approval_type"),
            approval_request=approval_request,
        )

    def _build_approval_request(self, proposal, policy_result):
        if not isinstance(proposal, dict):
            return {
                "requires_human_approval": False,
                "approval_type": None,
                "required_approver": None,
                "reason": "No proposal provided.",
                "status": "not_needed",
            }

        total_cost = proposal.get("total_cost_usd")
        flight = proposal.get("flight") or {}
        hotel = proposal.get("hotel") or {}
        traveler_role = proposal.get("traveler_role") or "employee"
        policy_status = (policy_result or {}).get("status")
        required_approver = (policy_result or {}).get("required_approver")

        if policy_status in {"non_compliant", "escalate"}:
            return {
                "requires_human_approval": True,
                "approval_type": "policy_exception",
                "required_approver": "travel_policy_approver",
                "reason": "Policy exception review required before booking.",
                "status": "pending",
            }

        if policy_status == "compliant" and required_approver:
            return {
                "requires_human_approval": True,
                "approval_type": "manager",
                "required_approver": required_approver,
                "reason": "Manager approval is required before booking.",
                "status": "pending",
            }

        if isinstance(total_cost, (int, float)) and total_cost > 3000:
            return {
                "requires_human_approval": True,
                "approval_type": "budget_override",
                "required_approver": "finance_manager",
                "reason": "Trip exceeds the budget threshold and needs override approval.",
                "status": "pending",
            }

        if flight.get("cabin") == "business" and traveler_role != "executive":
            return {
                "requires_human_approval": True,
                "approval_type": "manager",
                "required_approver": "department_head",
                "reason": "Business cabin exceeds the standard traveler policy.",
                "status": "pending",
            }

        nightly_rate = hotel.get("nightly_rate_usd")
        if isinstance(nightly_rate, (int, float)) and nightly_rate > 300:
            return {
                "requires_human_approval": True,
                "approval_type": "manager",
                "required_approver": "department_head",
                "reason": "Hotel nightly rate exceeds the standard policy threshold.",
                "status": "pending",
            }

        return {
            "requires_human_approval": False,
            "approval_type": None,
            "required_approver": None,
            "reason": "No additional human approval required.",
            "status": "approved",
        }

    def _booking_gate(self, policy_status, explanation, approver=None, approval_type=None, approval_request=None):
        gate = {
            "status": "policy_cleared_not_booked",
            "booked": False,
            "message": "Policy checks passed, but no booking operation is available.",
            "policy_explanation": explanation,
            "approval_required": False,
            "approval_type": approval_type,
            "required_approver": approver,
        }

        if policy_status == "compliant" and approver:
            gate["status"] = "awaiting_approval"
            gate["approval_required"] = True
            gate["message"] = f"Policy requires approval from {approver}. No booking was placed."
        elif policy_status == "compliant":
            gate["status"] = "policy_cleared_not_booked"
            gate["message"] = "Policy checks passed, but no booking operation is available."
        elif policy_status == "escalate":
            gate["status"] = "human_review_required"
            gate["approval_required"] = True
            gate["message"] = "Policy requires human review. No booking was placed."
        elif policy_status == "non_compliant":
            gate["status"] = "blocked_by_policy"
            gate["approval_required"] = False
            gate["message"] = "The proposal violates policy. No booking was placed."
        elif policy_status == "needs_facts":
            gate["status"] = "blocked_missing_facts"
            gate["message"] = "Required policy facts are missing. No booking was placed."
        elif policy_status in {"error", "policy_evaluation_failed"}:
            gate["status"] = "blocked_policy_error"
            gate["message"] = "Policy could not be verified. No booking was placed."

        if approval_request is not None:
            gate["approval_request"] = approval_request

        return gate

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