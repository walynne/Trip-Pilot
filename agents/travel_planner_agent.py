from typing import Any, Dict, List, TypedDict

from langgraph.graph import END, StateGraph

from agents.planner_agent import PlannerAgent
from agents.trip_agent import TripAgent


class TravelPlannerState(TypedDict):
    user_request: str
    trip_details: Dict[str, Any]
    flights: List[Dict[str, Any]]
    hotel_options: List[Dict[str, Any]]
    hotel: Dict[str, Any]
    summary: Dict[str, Any]
    schedule: List[Dict[str, Any]]
    weather: Dict[str, Any]
    policy_result: Dict[str, Any]
    budget: Dict[str, Any]
    approval: Dict[str, Any]
    booking_result: Dict[str, Any]
    final_itinerary: Dict[str, Any]


class TravelPlannerGraph:
    """A LangGraph workflow for a travel planner with the requested node sequence."""

    def __init__(self):
        self.planner_agent = PlannerAgent()
        self.trip_agent = TripAgent()
        self.graph = self._build_graph()

    @property
    def node_names(self):
        return [name for name in self.graph.nodes if name != "__start__"]

    def _build_graph(self):
        workflow = StateGraph(TravelPlannerState)

        workflow.add_node("travel_planner_agent", self._travel_planner_agent)
        workflow.add_node("flight_search_node", self._flight_search_node)
        workflow.add_node("hotel_search_node", self._hotel_search_node)
        workflow.add_node("weather_node", self._weather_node)
        workflow.add_node("policy_validation_node", self._policy_validation_node)
        workflow.add_node("budget_optimization_node", self._budget_optimization_node)
        workflow.add_node("approval_node", self._approval_node)
        workflow.add_node("booking_node", self._booking_node)
        workflow.add_node("final_itinerary", self._final_itinerary)

        workflow.set_entry_point("travel_planner_agent")
        workflow.add_edge("travel_planner_agent", "flight_search_node")
        workflow.add_edge("flight_search_node", "hotel_search_node")
        workflow.add_edge("hotel_search_node", "weather_node")
        workflow.add_edge("weather_node", "policy_validation_node")
        workflow.add_edge("policy_validation_node", "budget_optimization_node")
        workflow.add_edge("budget_optimization_node", "approval_node")
        workflow.add_edge("approval_node", "booking_node")
        workflow.add_edge("booking_node", "final_itinerary")
        workflow.add_edge("final_itinerary", END)

        return workflow.compile()

    def run(self, request: Any):
        if isinstance(request, dict):
            user_request = request.get("user_request") or request.get("message") or ""
            state = {**request, "user_request": user_request}
            trip_details = self._coerce_trip_details(request)
            state["trip_details"] = trip_details
        else:
            state = {"user_request": str(request), "trip_details": {}}

        return self.graph.invoke(state)

    def _coerce_trip_details(self, request: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(request, dict):
            return {}

        trip_details = {
            "origin": request.get("origin") or request.get("from") or request.get("departure_airport") or "",
            "destination": request.get("destination") or request.get("city") or request.get("location") or "",
            "departure_date": request.get("departure_date") or request.get("start_date") or "",
            "return_date": request.get("return_date") or request.get("end_date") or "",
            "guests": request.get("guests", 1),
            "rooms": request.get("rooms", 1),
            "hotel_nights": request.get("hotel_nights"),
        }
        if request.get("user_request") or request.get("message"):
            trip_details.update(self.trip_agent.extract_trip_details(request.get("user_request") or request.get("message") or ""))
        return trip_details

    def _travel_planner_agent(self, state: Dict[str, Any]) -> Dict[str, Any]:
        trip_details = state.get("trip_details") or {}
        if not trip_details:
            user_request = state.get("user_request") or ""
            if isinstance(user_request, dict):
                trip_details = user_request
            else:
                trip_details = self.trip_agent.extract_trip_details(user_request)

        return {"trip_details": trip_details}

    def _flight_search_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        trip_details = state.get("trip_details") or {}
        flight_plan = self.planner_agent.plan_trip(trip_details)
        flights = flight_plan.get("flights", {}).get("options", [])
        return {"flights": flights}

    def _hotel_search_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        trip_details = state.get("trip_details") or {}
        trip_plan = self.planner_agent.plan_trip(trip_details)
        hotel_options = trip_plan.get("hotel", {}).get("options", [])
        return {
            "hotel_options": hotel_options,
            "hotel": trip_plan.get("hotel", {}),
            "summary": trip_plan.get("summary", {}),
            "schedule": trip_plan.get("schedule", []),
        }

    def _weather_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        trip_details = state.get("trip_details") or {}
        weather_plan = self.planner_agent.plan_trip(trip_details)
        weather = weather_plan.get("weather", {})
        return {"weather": weather}

    def _policy_validation_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        trip_details = state.get("trip_details") or {}
        flights = state.get("flights") or []
        hotels = state.get("hotel_options") or []

        flight = flights[0] if flights else {"cabin": "economy", "duration_hours": 6}
        hotel = hotels[0] if hotels else {"nightly_rate_usd": 180, "currency": "USD"}
        proposal = {
            "city": trip_details.get("destination") or "",
            "city_tier": 2,
            "flight": {
                "cabin": flight.get("cabin") or "economy",
                "duration_hours": flight.get("duration_hours") or 6,
            },
            "hotel": {
                "nightly_rate_usd": hotel.get("pricing", {}).get("nightly_rate_usd") or hotel.get("nightly_rate_usd") or 180,
                "currency": hotel.get("currency") or "USD",
            },
            "total_cost_usd": self._calculate_total_cost(flight, hotel),
            "traveler_role": "manager",
        }

        policy_result, booking_gate = self.trip_agent._evaluate_booking_proposal(proposal)
        return {
            "policy_result": policy_result,
            "approval": {"status": booking_gate.get("status", "unknown")},
        }

    def _budget_optimization_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        flights = state.get("flights") or []
        hotels = state.get("hotel_options") or []
        total_cost = self._calculate_total_cost(flights[0] if flights else {}, hotels[0] if hotels else {})

        budget = {
            "status": "approved" if total_cost <= 3000 else "needs_review",
            "total_cost_usd": total_cost,
        }
        return {"budget": budget}

    def _approval_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        policy_result = state.get("policy_result") or {}
        budget = state.get("budget") or {}
        weather = state.get("weather") or {}
        approval = {"status": "approved"}

        weather_risk = self._weather_risk(weather)
        if policy_result.get("status") in {"needs_facts", "error", "non_compliant"}:
            approval["status"] = "rejected"
        elif budget.get("status") == "needs_review":
            approval["status"] = "pending"
        elif weather_risk == "high":
            approval["status"] = "pending"
            approval["weather_risk"] = weather_risk

        if weather_risk:
            approval["weather_risk"] = weather_risk

        return {"approval": approval}

    def _booking_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        approval = state.get("approval") or {"status": "approved"}
        trip_details = state.get("trip_details") or {}
        booking = {"status": "booked" if approval.get("status") == "approved" else "not_booked"}
        if booking["status"] == "booked":
            booking["confirmation_id"] = "TP-" + str(abs(hash(str(trip_details.get("destination") or "trip"))))[:8].upper()
        return {"booking_result": booking}

    def _final_itinerary(self, state: Dict[str, Any]) -> Dict[str, Any]:
        trip_details = state.get("trip_details") or {}
        flights = state.get("flights") or []
        hotels = state.get("hotel_options") or []
        approval = state.get("approval") or {"status": "pending"}
        booking = state.get("booking_result") or {"status": "not_booked"}
        weather = state.get("weather") or {}

        itinerary = {
            "origin": trip_details.get("origin") or state.get("origin") or "",
            "destination": trip_details.get("destination") or state.get("destination") or "",
            "departure_date": trip_details.get("departure_date") or state.get("departure_date") or "",
            "return_date": trip_details.get("return_date") or state.get("return_date") or "",
            "status": "approved" if approval.get("status") == "approved" else approval.get("status", "pending"),
            "flight": flights[0] if flights else {},
            "hotel": hotels[0] if hotels else {},
            "weather": weather,
            "booking_status": booking.get("status", "not_booked"),
        }
        return {"final_itinerary": itinerary}

    @staticmethod
    def _calculate_total_cost(flight: Dict[str, Any], hotel: Dict[str, Any]) -> float:
        try:
            flight_price = float(str(flight.get("price", 0)).replace("$", "").replace(",", ""))
        except (TypeError, ValueError):
            flight_price = 0.0

        hotel_pricing = hotel.get("pricing", {}) if isinstance(hotel, dict) else {}
        hotel_total = hotel_pricing.get("total") or hotel.get("nightly_rate_usd") or 0
        try:
            hotel_total = float(hotel_total)
        except (TypeError, ValueError):
            hotel_total = 0.0

        return flight_price + hotel_total

    @staticmethod
    def _weather_risk(weather: Dict[str, Any]) -> str:
        if not isinstance(weather, dict):
            return ""

        forecast = weather.get("forecast") or []
        if not forecast:
            return ""

        risk_order = {"low": 0, "moderate": 1, "high": 2}
        risks = [day.get("risk_level") for day in forecast if isinstance(day, dict)]
        if not risks:
            return ""
        return max(risks, key=lambda level: risk_order.get(level, -1))


__all__ = ["TravelPlannerGraph", "TravelPlannerState"]
