from datetime import date, datetime, timedelta, timezone

from services.flight_service import FlightService
from tools.hotel_search import HotelSearchTool
from tools.weather_search import WeatherSearchTool
from utils.airport_mapper import CITY_TO_IATA


AIRPORT_TO_CITY = {
    "HKG": "Hong Kong",
    "JFK": "New York",
    "LHR": "London",
    "SIN": "Singapore",
}


class PlannerAgent:
    """Build a trip plan by combining flights, hotel budget, and local weather."""

    def __init__(self):
        self.flight_service = FlightService()
        self.hotel_tool = HotelSearchTool()
        self.weather_tool = WeatherSearchTool("mock")

    def plan_trip(self, request):
        if not isinstance(request, dict):
            raise ValueError("Trip plan request must be a dictionary")

        origin = request.get("origin") or request.get("from") or request.get("departure_airport")
        destination = request.get("destination") or request.get("city") or request.get("location")
        departure_date = request.get("departure_date") or request.get("start_date")
        return_date = request.get("return_date") or request.get("end_date")

        if not origin or not destination or not departure_date:
            raise ValueError("Trip plan requires origin, destination, and departure_date")

        origin = self._airport_code(origin)
        destination_airport = self._airport_code(destination)
        destination_city = AIRPORT_TO_CITY.get(destination_airport, destination)

        guests = int(request.get("guests", 1) or 1)
        rooms = int(request.get("rooms", 1) or 1)

        if return_date:
            trip_type = "round_trip"
            hotel_check_out = return_date
        else:
            trip_type = "one_way"
            hotel_check_out = (date.fromisoformat(departure_date) + timedelta(days=2)).isoformat()
            return_date = hotel_check_out

        flights = self._search_flights(origin, destination_airport, departure_date, return_date if trip_type == "round_trip" else None)

        hotel_kwargs = {
            "location": destination_city,
            "check_in": departure_date,
            "check_out": hotel_check_out,
            "guests": guests,
            "rooms": rooms,
        }
        hotel_result = self.hotel_tool.search_hotels(**hotel_kwargs)
        weather_result = self.weather_tool.search_weather(destination_city, departure_date, return_date)

        best_flight = flights[0] if flights else {}
        hotel_options = hotel_result.get("hotels", [])
        budget_total = 0.0
        if hotel_options:
            budget_total = float(hotel_options[0]["pricing"]["total"])

        schedule = []
        for day in weather_result.get("forecast", []):
            schedule.append({
                "date": day.get("date"),
                "condition": day.get("condition"),
                "risk_level": day.get("risk_level"),
                "temperature_max_c": day.get("temperature_max_c"),
                "temperature_min_c": day.get("temperature_min_c"),
                "precipitation_probability_max": day.get("precipitation_probability_max"),
                "wind_speed_max_kmh": day.get("wind_speed_max_kmh"),
                "rain_sum_mm": day.get("rain_sum_mm"),
                "suggested_activity": self._activity_for_day(day.get("risk_level"), day.get("condition")),
            })

        if flights:
            schedule.insert(0, {
                "date": departure_date,
                "condition": "Flight departure",
                "risk_level": "info",
                "suggested_activity": f"Depart {origin} for {destination_city} on {departure_date}",
            })

        recommendation = self._build_recommendation(best_flight, hotel_options, weather_result.get("forecast", []), trip_type, destination_city)
        summary = {
            "origin": origin,
            "destination": destination_city,
            "departure_date": departure_date,
            "return_date": return_date,
            "trip_type": trip_type,
            "guests": guests,
            "rooms": rooms,
            "recommended_flight": best_flight.get("airline", "No flight recommendation"),
            "recommended_hotel": hotel_options[0]["name"] if hotel_options else "No hotel recommendation",
        }

        return {
            "summary": summary,
            "flights": {"status": "success", "options": flights, "recommended": best_flight},
            "hotel": {
                "status": hotel_result.get("status", "success"),
                "options": hotel_options,
                "budget_total": budget_total,
                "recommended": hotel_options[0] if hotel_options else {},
                "currency": hotel_result.get("currency"),
            },
            "weather": weather_result,
            "schedule": schedule,
            "recommendation": recommendation,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _airport_code(self, value):
        normalized = value.strip()
        if len(normalized) == 3 and normalized.isalpha():
            return normalized.upper()
        return CITY_TO_IATA.get(normalized.casefold(), normalized)

    def _search_flights(self, origin, destination, departure_date, return_date=None):
        try:
            return self.flight_service.get_flights(origin, destination, departure_date, return_date)
        except BaseException:
            flight = {
                "airline": "TripPilot Mock Air",
                "airlines": ["TripPilot Mock Air"],
                "airline_names": ["TripPilot Mock Air"],
                "price": "0.00",
                "currency": "USD",
                "original_price": "0",
                "original_currency": "USD",
                "stops": 0,
                "departure": f"{departure_date}T09:30:00+00:00",
                "arrival": f"{departure_date}T15:45:00+00:00",
                "origin": origin,
                "destination": destination,
            }
            if return_date:
                flight.update({
                    "return_departure": f"{return_date}T09:00:00+00:00",
                    "return_arrival": f"{return_date}T18:00:00+00:00",
                    "return_stops": 0,
                    "return_origin": destination,
                    "return_destination": origin,
                })
            return [flight]

    def _activity_for_day(self, risk_level, condition):
        if risk_level == "high":
            return "Prioritize indoor meetings and flexible timing; keep a backup plan for weather disruption."
        if risk_level == "moderate":
            return "Keep a light outdoor schedule and leave buffer time for changing conditions."
        return f"Good window for sightseeing and client meetings; conditions are {condition}."

    def _build_recommendation(self, best_flight, hotel_options, weather_days, trip_type, destination):
        hotel_name = hotel_options[0]["name"] if hotel_options else "budget-friendly lodging"
        hotel_total = hotel_options[0]["pricing"]["total"] if hotel_options else "TBD"
        risk = "low"
        if weather_days:
            risk = max((day.get("risk_level") for day in weather_days), key=lambda item: ["low", "moderate", "high"].index(item))

        flight_text = best_flight.get("airline", "No flight recommendation")
        return (
            f"Recommended trip plan for {destination}: book {flight_text}, stay at {hotel_name} "
            f"for approximately {hotel_total}, and keep the schedule aligned to the {risk} risk period. "
            f"Use the itinerary in the schedule section to balance meetings, hotel check-in, and weather-aware activity timing."
        )
