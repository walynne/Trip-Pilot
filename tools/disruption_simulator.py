"""C4 deterministic demo events. No monitoring, policy evaluation or execution."""

from datetime import date, datetime
from decimal import Context, Decimal, localcontext
import re

from tools.hotel_search import HotelError, HotelSearchTool


class DisruptionSimulationError(ValueError):
    """Invalid simulation input, with a stable code and no echoed trip facts."""

    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


SCENARIOS = {
    "flight_cancelled": ("flight", "HIGH", "Simulated flight cancellation."),
    "hotel_unavailable": ("hotel", "HIGH", "Simulated hotel unavailability."),
    "meeting_time_changed": ("meeting", "MEDIUM", "Simulated meeting time change."),
    "budget_reduced": ("budget", "MEDIUM", "Simulated trip budget reduction."),
}


def _text(fields, name):
    value = fields.get(name)
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= 200:
        raise DisruptionSimulationError("invalid_input", f"{name} must be text of 1 to 200 characters.")
    return value.strip()


def _departure_date(fields):
    value = _text(fields, "departure_date")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise DisruptionSimulationError("invalid_date", "departure_date must be a valid YYYY-MM-DD date.") from exc
    if parsed.isoformat() != value:
        raise DisruptionSimulationError("invalid_date", "departure_date must use YYYY-MM-DD.")
    return value


def _meeting_time(fields, name):
    value = _text(fields, name)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise DisruptionSimulationError("invalid_time", "Meeting times must be ISO-8601 timestamps.") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise DisruptionSimulationError("invalid_time", "Meeting times require an explicit UTC offset.")
    return value, parsed


def _amount(fields, name):
    value = fields.get(name)
    if not isinstance(value, str) or re.fullmatch(r"\d{1,12}(?:\.\d{1,2})?", value, re.ASCII) is None:
        raise DisruptionSimulationError("invalid_budget", "Budget amounts require decimal strings with at most two decimal places.")
    # Keep results independent of any caller's Decimal precision/rounding/traps.
    with localcontext(Context(prec=28)):
        return Decimal(value), format(Decimal(value).quantize(Decimal("0.01")), "f")


class DisruptionSimulator:
    """simulate(scenario, context) returns a fresh, JSON-safe mock event.

    Context requires trip_id and the selected flight/hotel/meeting/budget object.
    Extra context fields are ignored; no unknown data is echoed into the event.
    """

    def simulate(self, scenario, context):
        if not isinstance(scenario, str) or scenario not in SCENARIOS:
            raise DisruptionSimulationError("unsupported_scenario", "Choose one of the four supported C4 scenarios.")
        if not isinstance(context, dict):
            raise DisruptionSimulationError("invalid_context", "context must be a dictionary.")
        trip_id = _text(context, "trip_id")
        component, severity, message = SCENARIOS[scenario]
        fields = context.get(component)
        if not isinstance(fields, dict):
            raise DisruptionSimulationError("invalid_context", f"context requires a {component} dictionary.")
        supporting_data = None
        if component == "flight":
            affected = {"flight_id": _text(fields, "flight_id")}
            for name in ("origin", "destination"):
                code = _text(fields, name)
                if re.fullmatch(r"[A-Z]{3}", code, re.ASCII) is None:
                    raise DisruptionSimulationError("invalid_flight", "Airports require uppercase three-letter IATA codes.")
                affected[name] = code
            if affected["origin"] == affected["destination"]:
                raise DisruptionSimulationError("invalid_flight", "Flight origin and destination must differ.")
            affected["departure_date"] = _departure_date(fields)
        elif component == "hotel":
            hotel_id = _text(fields, "hotel_id")
            if any(name not in fields for name in ("location", "check_in", "check_out", "guests", "rooms")):
                raise DisruptionSimulationError("invalid_hotel", "Hotel location, dates, guests and rooms are required.")
            try:
                result = HotelSearchTool(provider="mock", mock_scenario="fully_booked").search_hotels(
                    fields["location"], fields["check_in"], fields["check_out"],
                    guests=fields["guests"], rooms=fields["rooms"],
                )
            except (ValueError, HotelError) as exc:
                raise DisruptionSimulationError("invalid_hotel", "Hotel input must satisfy the C2 mock catalogue contract.") from exc
            affected = {"hotel_id": hotel_id, **{key: result[key] for key in
                        ("location", "check_in", "check_out", "nights", "guests", "rooms")}}
            # Select stable fields, never C2's wall-clock retrieved_at. The city
            # catalogue simulation does not verify the caller's specific hotel.
            supporting_data = {key: result[key] for key in
                               ("provider", "data_mode", "mock_scenario", "status", "result_count")}
        elif component == "meeting":
            meeting_id = _text(fields, "meeting_id")
            original, original_time = _meeting_time(fields, "original_start")
            changed, changed_time = _meeting_time(fields, "new_start")
            if original_time == changed_time:
                raise DisruptionSimulationError("invalid_time", "The new meeting start must be a different instant.")
            affected = {"meeting_id": meeting_id, "original_start": original, "new_start": changed}
        else:
            currency = _text(fields, "currency")
            if re.fullmatch(r"[A-Z]{3}", currency, re.ASCII) is None:
                raise DisruptionSimulationError("invalid_budget", "currency must be an uppercase three-letter code.")
            original, original_text = _amount(fields, "original_amount")
            reduced, reduced_text = _amount(fields, "new_amount")
            if not 0 <= reduced < original:
                raise DisruptionSimulationError("invalid_budget", "Budget must decrease from a positive amount to a non-negative amount.")
            affected = {"currency": currency, "original_amount": original_text, "new_amount": reduced_text}

        metadata = {"trip_id": trip_id, "flight": None, "hotel": None, "meeting": None, "budget": None}
        metadata[component] = affected
        return {
            "type": scenario.upper(), "severity": severity, "message": message,
            "source": "disruption_simulator", "data_mode": "mock",
            "confirmed_disruption": False, "requires_replanning_assessment": True,
            "affected_trip": metadata, "supporting_data": supporting_data,
        }
