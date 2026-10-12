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
from utils.airport_mapper import (
    is_iata_code
)
from utils.travel_dates import (
    ensure_valid_return_date
)


class TripAgent:

    def __init__(self):

        self.llm = NexLLMClient()

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
        user_message
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

        return {
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