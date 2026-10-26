from datetime import date, datetime
from zoneinfo import ZoneInfo

from flask import (
    Flask,
    render_template,
    request,
    jsonify
)

from agents.planner_agent import PlannerAgent
from agents.travel_planner_agent import TravelPlannerGraph
from agents.trip_agent import TripAgent
from tools.disruption_simulator import DisruptionSimulationError, DisruptionSimulator
from tools.hotel_search import HotelSearchTool
from tools.openmeteo_client import WeatherError


app = Flask(__name__)

trip_agent = TripAgent()
planner_agent = PlannerAgent()
travel_planner = TravelPlannerGraph()

AIRPORT_TIMEZONES = {
    "HKG": "Asia/Hong_Kong",
    "JFK": "America/New_York",
    "LHR": "Europe/London",
    "SIN": "Asia/Singapore",
}


@app.route("/")
def home():
    """
    Main UI page
    """
    return render_template("index.html")


@app.route("/health")
def health():
    """
    Health check endpoint
    """
    return jsonify({
        "status": "ok",
        "service": "TripPilot"
    })


@app.route("/chat", methods=["POST"])
def chat():

    try:

        data = request.get_json()

        message = data.get(
            "message",
            ""
        )

        if not message:

            return jsonify({
                "error":
                "Message cannot be empty"
            }), 400

        booking_proposal = data.get("booking_proposal")
        if _is_hotel_search_request(message) and not _is_trip_plan_request(message):
            result = trip_agent.search_hotel_rates(message)
            result["recommendation"] = result.pop("message", "")
            _attach_hotel_search_details(result)
            result["agent_steps"] = [
                "Asked the model to check hotel IDs and stay dates",
                "Executed Google Hotels search" if result.get("tool_results") else "Requested missing hotel search details",
            ]
        elif _is_trip_plan_request(message):
            requirements = trip_agent.extract_trip_details(message)
            trip_agent._validate_trip(requirements)
            result = travel_planner.run({
                "user_request": message,
                "origin": requirements.get("origin") or requirements.get("from") or requirements.get("departure_airport"),
                "destination": requirements.get("destination") or requirements.get("city") or requirements.get("location"),
                "departure_date": requirements.get("departure_date") or requirements.get("start_date"),
                "return_date": requirements.get("return_date") or requirements.get("end_date"),
                "guests": requirements.get("guests", 1),
                "rooms": requirements.get("rooms", 1),
                "hotel_nights": requirements.get("hotel_nights"),
            })

            final_itinerary = result.get("final_itinerary", {})
            result["requirements"] = requirements
            result["trip_details"] = requirements
            result["recommendation"] = final_itinerary.get("status", "pending")
            result["flights"] = result.get("flights", [])
            result["weather"] = result.get("weather", {})
            result["agent_steps"] = [
                "Extracted travel requirements",
                "Flight search complete",
                "Hotel search complete",
                "Weather check complete",
                "Policy validation complete",
                "Budget optimization complete",
                "Approval state finalized",
                "Booking status determined",
            ]
            if booking_proposal is not None:
                policy_proposal = _build_trip_policy_proposal(result, booking_proposal)
                policy_result, booking_gate = trip_agent._evaluate_booking_proposal(
                    policy_proposal,
                    require_hotel=True,
                )
                result["policy_proposal"] = policy_proposal
                result["policy_result"] = policy_result
                result["booking_gate"] = booking_gate
                result["agent_steps"].append(f"Booking gate: {booking_gate['status']}")
        elif booking_proposal is None:
            result = trip_agent.run(message)
        else:
            result = trip_agent.run(
                message,
                booking_proposal=booking_proposal
            )

        return jsonify(result)

    except ValueError as e:

        print(
            "CHAT VALIDATION ERROR:",
            str(e)
        )

        return jsonify({

            "agent_steps": [
                "Request failed validation"
            ],

            "recommendation":
                f"Error: {str(e)}",

            "flights": [],

            "event": None,

            "monitor_result": None,

            "replan_result": None

        }), 400

    except Exception as e:

        print(
            "CHAT ERROR:",
            str(e)
        )

        return jsonify({

            "agent_steps": [
                "Request failed"
            ],

            "recommendation":
                f"Error: {str(e)}",

            "flights": [],

            "event": None,

            "monitor_result": None,

            "replan_result": None

        }), 500


def _attach_hotel_search_details(result):
    """Expose hotel tool results to the UI and check weather for the same stay."""
    for entry in result.get("tool_results", []):
        if entry.get("name") != "search_google_hotels":
            continue
        raw = entry.get("result") or {}
        if raw.get("error") or raw.get("status") == "error":
            result["hotel"] = {
                "status": "unavailable", "options": [],
                "message": raw.get("error") or "Google Hotels search failed.",
            }
            continue
        check_in, check_out = raw.get("check_in"), raw.get("check_out")
        if not check_in or not check_out:
            continue
        location = raw.get("query") or ""
        if location.lower().startswith("hotels in "):
            location = location[len("Hotels in "):].strip()
        nights = (date.fromisoformat(check_out) - date.fromisoformat(check_in)).days
        hotels = HotelSearchTool.normalize_google_results(
            raw, location, check_in, check_out, nights, raw.get("adults", 2),
        )
        options = hotels["hotels"]
        result["hotel"] = {
            **hotels, "options": options,
            "recommended": options[0] if options else {},
        }
        result["summary"] = {
            "destination": location, "departure_date": check_in,
            "return_date": check_out, "guests": raw.get("adults", 2), "rooms": 1,
        }
        try:
            result["weather"] = planner_agent.weather_tool.search_weather(location, check_in, check_out)
        except (WeatherError, ValueError) as error:
            result["weather"] = {
                "status": "unavailable", "forecast": [],
                "error_code": error.code if isinstance(error, WeatherError) else "forecast_dates_unavailable",
                "message": str(error),
            }


def _is_trip_plan_request(message):
    normalized = message.lower()
    # Business travel is a full trip even without the literal words "trip plan".
    business_visit = (
        any(phrase in normalized for phrase in ("visit ", "travel to ", "going to ", "fly to "))
        and any(phrase in normalized for phrase in ("client meeting", "business meeting", "business trip", "conference"))
    )
    if business_visit:
        return True
    return any(phrase in normalized for phrase in (
        "plan a trip",
        "plan trip",
        "trip plan",
        "itinerary",
        "travel schedule",
    ))


def _is_hotel_search_request(message):
    normalized = message.lower()
    return any(phrase in normalized for phrase in (
        "hotel rates",
        "hotel rate",
        "hotel availability",
        "hotel available",
        "room rates",
        "room availability",
        "rates for hotel",
        "availability for hotel",
        "search hotels",
        "search hotel",
        "search for hotels",
        "search for hotel",
        "find hotels",
        "find hotel",
        "find me a hotel",
        "google hotels",
        "hotel options",
        "hotel recommendations",
    ))


def _build_trip_policy_proposal(plan, submitted):
    submitted = submitted if isinstance(submitted, dict) else {}
    submitted_flight = submitted.get("flight")
    submitted_flight = submitted_flight if isinstance(submitted_flight, dict) else {}
    submitted_hotel = submitted.get("hotel")
    submitted_hotel = submitted_hotel if isinstance(submitted_hotel, dict) else {}

    flight_data = plan.get("flights") or {}
    flight_options = flight_data.get("options", []) if isinstance(flight_data, dict) else []
    flight = (flight_data.get("recommended") if isinstance(flight_data, dict) else None)
    flight = flight or (flight_options[0] if flight_options else {})

    hotel_data = plan.get("hotel") or {}
    hotel = hotel_data.get("recommended") or {}
    pricing = hotel.get("pricing") or {}

    hotel_rate = submitted_hotel.get("nightly_rate_usd")
    if hotel_rate is None and str(pricing.get("currency", "")).upper() == "USD":
        hotel_rate = _positive_amount(pricing.get("room_nightly_rate"))
    hotel_currency = submitted_hotel.get("currency")
    if not hotel_currency:
        hotel_currency = pricing.get("currency") if hotel_rate is None else "USD"

    total_cost = submitted.get("total_cost_usd")
    if total_cost is None:
        flight_price = _flight_price_in_usd(flight)
        hotel_total = None
        if str(pricing.get("currency", "")).upper() == "USD":
            hotel_total = _positive_amount(pricing.get("total"))
        if flight_price is not None and hotel_total is not None:
            total_cost = flight_price + hotel_total

    flight_duration = submitted_flight.get("duration_hours")
    if flight_duration is None:
        flight_duration = _flight_duration_hours(flight)

    proposal = {
        "traveler_role": submitted.get("traveler_role"),
        "city": (plan.get("summary") or {}).get("destination"),
        "city_tier": submitted.get("city_tier"),
        "flight": {
            "cabin": submitted_flight.get("cabin") or "economy",
            "duration_hours": flight_duration,
        },
        "hotel": {
            "nightly_rate_usd": hotel_rate,
            "currency": hotel_currency,
        },
        "total_cost_usd": total_cost,
    }
    if submitted.get("meals_usd") is not None:
        proposal["meals_usd"] = submitted["meals_usd"]
    return proposal


def _positive_amount(value):
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return None
    return amount if amount > 0 else None


def _flight_price_in_usd(flight):
    if not isinstance(flight, dict):
        return None
    for amount_key, currency_key in (
        ("original_price", "original_currency"),
        ("price", "currency"),
    ):
        if str(flight.get(currency_key, "")).upper() == "USD":
            amount = _positive_amount(flight.get(amount_key))
            if amount is not None:
                return amount
    return None


def _flight_duration_hours(flight):
    if not isinstance(flight, dict):
        return None
    try:
        departure = datetime.fromisoformat(flight["departure"])
        arrival = datetime.fromisoformat(flight["arrival"])
        if departure.tzinfo is None:
            departure_zone = AIRPORT_TIMEZONES.get(flight.get("origin"))
            if departure_zone is None:
                return None
            departure = departure.replace(tzinfo=ZoneInfo(departure_zone))
        if arrival.tzinfo is None:
            arrival_zone = AIRPORT_TIMEZONES.get(flight.get("destination"))
            if arrival_zone is None:
                return None
            arrival = arrival.replace(tzinfo=ZoneInfo(arrival_zone))
        hours = (arrival - departure).total_seconds() / 3600
    except (KeyError, TypeError, ValueError):
        return None
    return round(hours, 1) if 0 < hours <= 48 else None


@app.route(
    "/simulate-disruption",
    methods=["POST"]
)
def simulate_disruption():

    try:

        data = request.get_json()

        trip = data.get(
            "trip",
            {}
        )

        scenario = data.get(
            "scenario",
            "delay"
        )

        if scenario == "hotel_unavailable":
            try:
                event = DisruptionSimulator().simulate(
                    scenario,
                    data.get("context"),
                )
            except DisruptionSimulationError as error:
                return jsonify({
                    "error": str(error),
                    "code": error.code,
                }), 400

            return jsonify({
                "event": event,
                "human_decision_required": True,
            })

        if scenario == "meeting_time_changed":
            try:
                event = DisruptionSimulator().simulate(
                    scenario,
                    data.get("context"),
                )
            except DisruptionSimulationError as error:
                return jsonify({
                    "error": str(error),
                    "code": error.code,
                }), 400

            return jsonify({
                "event": event,
                "human_decision_required": True,
            })

        if scenario == "budget_reduced":
            try:
                event = DisruptionSimulator().simulate(
                    scenario,
                    data.get("context"),
                )
            except DisruptionSimulationError as error:
                return jsonify({
                    "error": str(error),
                    "code": error.code,
                }), 400

            return jsonify({
                "event": event,
                "human_decision_required": True,
            })

        event = {

            "type":
                "FLIGHT_DELAY",

            "severity":
                "HIGH",

            "delay_hours":
                6,

            "message":
                "Flight delayed by 6 hours"
        }

        if scenario == "cancel":

            event = {

                "type":
                    "FLIGHT_CANCELLED",

                "severity":
                    "HIGH",

                "message":
                    "Flight cancelled"
            }

        monitor_result = (
            trip_agent.monitor.analyse(
                trip,
                event
            )
        )

        replan_result = (
            trip_agent.replanner.replan(
                trip,
                event
            )
        )

        return jsonify({

            "event":
                event,

            "monitor_result":
                monitor_result,

            "replan_result":
                replan_result
        })

    except Exception as e:

        print(
            "SIMULATE ERROR:",
            str(e)
        )

        return jsonify({
            "error": str(e)
        }), 500

@app.route("/demo")
def demo():

    """
    Simple demo payload
    """

    return jsonify({

        "message":
            "Try asking: "
            "'I need a flight from Hong Kong "
            "to London on 15 Nov 2026'"

    })


if __name__ == "__main__":

    print(
        "\n================================="
    )

    print(
        "TripPilot AI Agent Started"
    )

    print(
        "URL: http://localhost:5000"
    )

    print(
        "=================================\n"
    )

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )