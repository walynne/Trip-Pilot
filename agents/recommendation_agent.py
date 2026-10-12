import json


class RecommendationAgent:

    def __init__(
        self,
        llm
    ):

        self.llm = llm

    def recommend(
        self,
        trip,
        flights
    ):

        if not flights:
            return (
                "No flights found for the requested itinerary."
            )

        best_flight = flights[0]

        return self._format_recommendation(
            trip,
            best_flight,
            flights[1:3]
        )

    def _format_recommendation(
        self,
        trip,
        best_flight,
        alternatives
    ):

        lines = [
            "Recommended Flight",
            "",
            "**Flight Details:**",
            f"- **Airline:** {best_flight.get('airline', 'Unknown Airline')}",
            f"- **Airline Name:** {', '.join(best_flight.get('airline_names', [])) or best_flight.get('airline', 'Unknown Airline')}",
            f"- **Departure:** {best_flight.get('departure', 'N/A')}",
            f"- **Arrival:** {best_flight.get('arrival', 'N/A')}",
            f"- **Price:** {best_flight.get('price', 'N/A')} {best_flight.get('currency', '')}".strip(),
            f"- **Stops:** {best_flight.get('stops', 0)} ({'Direct' if best_flight.get('stops', 0) == 0 else 'Connecting'})"
        ]

        if trip.get("return_date") and best_flight.get("return_departure"):
            lines.extend([
                f"- **Return Departure:** {best_flight.get('return_departure', 'N/A')}",
                f"- **Return Arrival:** {best_flight.get('return_arrival', 'N/A')}",
                f"- **Return Stops:** {best_flight.get('return_stops', 0)} ({'Direct' if best_flight.get('return_stops', 0) == 0 else 'Connecting'})"
            ])

        lines.extend([
            "",
            "Reason",
            "",
            "- Prioritized direct service first, then price.",
            "- Airline and schedule are copied directly from the Duffel offer data.",
            "",
            "Alternative Option"
        ])

        if alternatives:
            alt = alternatives[0]
            lines.extend([
                "",
                f"- **Airline:** {alt.get('airline', 'Unknown Airline')}",
                f"- **Price:** {alt.get('price', 'N/A')} {alt.get('currency', '')}".strip(),
                f"- **Departure:** {alt.get('departure', 'N/A')}",
                f"- **Arrival:** {alt.get('arrival', 'N/A')}"
            ])
        else:
            lines.extend([
                "",
                "- No alternative option available."
            ])

        return "\n".join(lines)