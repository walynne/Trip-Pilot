import json


class ReplanningAgent:

    def __init__(
        self,
        llm,
        flight_service
    ):
        self.llm = llm
        self.flight_service = flight_service

    def replan(
        self,
        trip,
        event
    ):

        alternative_flights = (
            self.flight_service.get_flights(
                trip["origin"],
                trip["destination"],
                trip["departure_date"],
                trip.get("return_date")
            )
        )

        prompt = f"""
Trip:

{json.dumps(trip, indent=2)}

Disruption:

{json.dumps(event, indent=2)}

Alternative Flights:

{json.dumps(alternative_flights[:5], indent=2)}

Choose the best replacement flight.

Explain:
1. Recommended flight
2. Why
3. Business impact
"""

        recommendation = self.llm.chat(
            "Travel replanning specialist",
            prompt
        )

        return {
            "replanned": True,
            "alternative_flights": alternative_flights[:5],
            "recommendation": recommendation
        }