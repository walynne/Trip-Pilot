"""Hotel search service with mock, Duffel, and SerpApi providers."""

import os
from dotenv import load_dotenv

from tools.hotel_search import HotelError, HotelSearchTool
from utils.demo_data import load_demo_trip_data


class HotelService:
    """Search hotels using mock or live providers.

    Mirrors FlightService pattern for consistent API across travel services.
    Normalizes and enriches hotel data from multiple providers.
    """

    def __init__(self, provider=None):
        load_dotenv()
        if provider is None:
            if os.getenv("SERPAPI_API_KEY"):
                provider = "serpapi"
            else:
                provider = "duffel" if os.getenv("DUFFEL_API_KEY") else "mock"

        if provider not in {"mock", "duffel", "serpapi"}:
            raise ValueError("Provider must be 'mock', 'duffel', or 'serpapi'")

        self.provider = provider
        self.tool = HotelSearchTool(provider=provider)

    def search_hotels(self, location, check_in, check_out, guests=1, rooms=1):
        """Search for hotels by location and dates.

        Args:
            location: City name (e.g., "Singapore", "London")
            check_in: YYYY-MM-DD format date
            check_out: YYYY-MM-DD format date
            guests: Number of guests (1-32)
            rooms: Number of rooms (1-8)

        Returns:
            Normalized dict with:
            - location: City name
            - country_code: ISO country code
            - check_in/check_out: Date strings
            - nights: Number of nights
            - guests/rooms: Counts
            - currency: Local currency
            - provider: 'mock', 'duffel', or 'serpapi'
            - data_mode: 'mock' or 'live'
            - status: 'success' or 'no_results'
            - hotels: List of normalized hotel dicts
            - result_count: Number of results
            - is_live: Boolean indicating if data is from live provider
        """
        try:
            result = self.tool.search_hotels(
                location=location,
                check_in=check_in,
                check_out=check_out,
                guests=guests,
                rooms=rooms
            )
        except Exception:
            if self.provider == "mock":
                raise
            return self._fallback_to_demo(location, check_in, check_out, guests, rooms, self.provider)

        if isinstance(result, dict) and result.get("status") == "error":
            return self._fallback_to_demo(location, check_in, check_out, guests, rooms, self.provider)

        if result is None:
            return self._fallback_to_demo(location, check_in, check_out, guests, rooms, self.provider)

        if not isinstance(result, dict):
            return self._fallback_to_demo(location, check_in, check_out, guests, rooms, self.provider)

        if self.provider != "mock" and result.get("status") == "no_results":
            return self._fallback_to_mock(location, check_in, check_out, guests, rooms, self.provider)

        if self.provider != "mock" and result.get("status") == "no_results":
            return self._fallback_to_mock(location, check_in, check_out, guests, rooms, self.provider)

        return self._normalize_result(result)

    def _fallback_to_demo(self, location, check_in, check_out, guests, rooms, failed_provider):
        payload = load_demo_trip_data()
        hotel_result = payload.get("hotel", {})
        hotel_result = {
            **hotel_result,
            "location": location,
            "check_in": check_in,
            "check_out": check_out,
            "guests": guests,
            "rooms": rooms,
            "provider": "demo",
            "data_mode": "mock",
            "live_provider_fallback": failed_provider,
            "status": "success",
        }
        return self._normalize_result(hotel_result)

    def _fallback_to_mock(self, location, check_in, check_out, guests, rooms, failed_provider):
        mock_tool = HotelSearchTool(provider="mock")
        result = mock_tool.search_hotels(
            location=location,
            check_in=check_in,
            check_out=check_out,
            guests=guests,
            rooms=rooms,
        )
        result["provider"] = "mock"
        result["data_mode"] = "mock"
        result["live_provider_fallback"] = failed_provider
        if result.get("status") == "success":
            result["status"] = "success"
        return self._normalize_result(result)

    def _normalize_result(self, result):
        """Normalize hotel search result to consistent format."""
        hotels = result.get("hotels", [])

        normalized = {
            "location": result.get("location"),
            "country_code": result.get("country_code"),
            "check_in": result.get("check_in"),
            "check_out": result.get("check_out"),
            "nights": result.get("nights"),
            "guests": result.get("guests"),
            "rooms": result.get("rooms"),
            "currency": result.get("currency"),
            "provider": result.get("provider"),
            "data_mode": result.get("data_mode"),
            "status": result.get("status"),
            "hotels": self._normalize_hotels(hotels),
            "result_count": result.get("result_count", len(hotels)),
            "is_live": result.get("data_mode") == "live",
            "retrieved_at": result.get("retrieved_at"),
        }

        if result.get("mock_scenario"):
            normalized["mock_scenario"] = result["mock_scenario"]

        return normalized

    def _normalize_hotels(self, hotels):
        """Normalize hotel data to consistent format."""
        normalized = []

        for hotel in hotels:
            pricing = hotel.get("pricing", {})
            location = hotel.get("location", {})

            normalized_hotel = {
                "id": hotel.get("hotel_id"),
                "name": hotel.get("name"),
                "city": hotel.get("city"),
                "country_code": hotel.get("country_code"),
                "tier": hotel.get("hotel_tier"),
                "preferred_supplier": hotel.get("preferred_supplier"),
                "amenities": hotel.get("amenities", []),
                "rating": hotel.get("rating"),
                "review_count": hotel.get("review_count"),
                "address": hotel.get("address"),
                "free_cancellation": hotel.get("free_cancellation"),
                "cancellation_policy": hotel.get("cancellation_policy"),
                "availability_status": hotel.get("availability_status"),
                "location": {
                    "latitude": location.get("latitude"),
                    "longitude": location.get("longitude"),
                    "is_synthetic": location.get("coordinates_are_synthetic", False),
                },
                "pricing": {
                    "currency": pricing.get("currency"),
                    "nightly_rate": pricing.get("room_nightly_rate"),
                    "subtotal": pricing.get("subtotal"),
                    "taxes": pricing.get("taxes"),
                    "fees": pricing.get("fees"),
                    "total": pricing.get("total"),
                    "payment_type": pricing.get("payment_type"),
                },
                "booking_url": hotel.get("booking_url"),
            }

            normalized.append(normalized_hotel)

        return normalized

    def get_best_hotel(self, result):
        """Get the best (cheapest) hotel from search results.

        Returns:
            First hotel from sorted results or None if no hotels.
        """
        hotels = result.get("hotels", [])
        return hotels[0] if hotels else None

    def filter_hotels_by_price(self, result, max_nightly_rate=None, max_total=None):
        """Filter hotels by price constraints.

        Args:
            result: Hotel search result
            max_nightly_rate: Maximum nightly rate (in result currency)
            max_total: Maximum total cost (in result currency)

        Returns:
            Filtered list of hotels.
        """
        hotels = result.get("hotels", [])
        filtered = []

        for hotel in hotels:
            pricing = hotel.get("pricing", {})
            nightly = float(pricing.get("nightly_rate", 0) or 0)
            total = float(pricing.get("total", 0) or 0)

            if max_nightly_rate and nightly > max_nightly_rate:
                continue
            if max_total and total > max_total:
                continue

            filtered.append(hotel)

        return filtered

    def filter_hotels_by_amenities(self, result, required_amenities=None):
        """Filter hotels by required amenities.

        Args:
            result: Hotel search result
            required_amenities: List of amenity keywords (e.g., ['wifi', 'gym'])

        Returns:
            Filtered list of hotels that have all required amenities.
        """
        if not required_amenities:
            return result.get("hotels", [])

        hotels = result.get("hotels", [])
        filtered = []
        required = [a.lower() for a in required_amenities]

        for hotel in hotels:
            amenities = [a.lower() for a in hotel.get("amenities", [])]
            if all(req in amenities for req in required):
                filtered.append(hotel)

        return filtered
