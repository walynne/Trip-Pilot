"""Google Hotels search through SerpApi's google-search-results client."""

import os
from datetime import date, datetime, timezone
from dotenv import load_dotenv


SEARCH_GOOGLE_HOTELS_SCHEMA = {
    "type": "function",
    "function": {
        "name": "search_google_hotels",
        "description": "Searches Google Hotels via SerpApi for live nightly rates, guest ratings, and property amenities.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search destination or descriptor (e.g., 'Hotels in Paris near Eiffel Tower', 'Boutique resort in Bali').",
                },
                "check_in": {
                    "type": "string",
                    "description": "Check-in date formatted as YYYY-MM-DD.",
                },
                "check_out": {
                    "type": "string",
                    "description": "Check-out date formatted as YYYY-MM-DD.",
                },
                "adults": {
                    "type": "integer",
                    "description": "Number of adult guests.",
                    "default": 2,
                },
            },
            "required": ["query", "check_in", "check_out"],
        },
    },
}


class GoogleHotelsSearchTool:
    """Search Google Hotels and return a compact, JSON-safe result."""

    def __init__(self, api_key=None, *, search_class=None):
        load_dotenv()
        self.api_key = api_key or os.getenv("SERPAPI_API_KEY")
        if not self.api_key:
            raise ValueError("SERPAPI_API_KEY is required for Google Hotels search")
        self.search_class = search_class

    def search_google_hotels(self, query, check_in, check_out, adults=2):
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty string")
        checkin = self._parse_date(check_in, "check_in")
        checkout = self._parse_date(check_out, "check_out")
        if checkout <= checkin:
            raise ValueError("check_out must be after check_in")
        if type(adults) is not int or not 1 <= adults <= 20:
            raise ValueError("adults must be an integer between 1 and 20")

        search_class = self.search_class
        if search_class is None:
            from serpapi import GoogleSearch

            search_class = GoogleSearch

        params = {
            "engine": "google_hotels",
            "q": query.strip(),
            "check_in_date": check_in,
            "check_out_date": check_out,
            "adults": adults,
            "currency": "USD",
            "api_key": self.api_key,
        }
        try:
            response = search_class(params).get_dict()
        except Exception:
            return {"status": "error", "error": "SerpApi request failed"}

        if not isinstance(response, dict):
            return {"status": "error", "error": "SerpApi returned an invalid response"}
        if response.get("error"):
            return {"status": "error", "error": str(response["error"])}

        properties = []
        for property_data in response.get("properties", []) or []:
            if not isinstance(property_data, dict):
                continue
            nightly = property_data.get("rate_per_night") or {}
            total = property_data.get("total_rate") or {}
            properties.append({
                "name": property_data.get("name"),
                "type": property_data.get("type"),
                "rating": property_data.get("overall_rating"),
                "reviews": property_data.get("reviews"),
                "price_per_night": nightly.get("extracted_lowest"),
                "nightly_price_text": nightly.get("lowest"),
                "total_price": total.get("extracted_lowest"),
                "total_price_text": total.get("lowest"),
                "currency": response.get("search_parameters", {}).get("currency", "USD"),
                "amenities": property_data.get("amenities", []) or [],
                "address": property_data.get("address"),
                "gps_coordinates": property_data.get("gps_coordinates"),
                "free_cancellation": property_data.get("free_cancellation"),
                "link": property_data.get("link"),
                "property_token": property_data.get("property_token"),
            })

        return {
            "status": "success" if properties else "no_results",
            "provider": "google_hotels",
            "data_mode": "live",
            "query": query.strip(),
            "check_in": check_in,
            "check_out": check_out,
            "adults": adults,
            "properties": properties,
            "result_count": len(properties),
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _parse_date(value, label):
        if not isinstance(value, str):
            raise ValueError(f"{label} must be YYYY-MM-DD")
        try:
            parsed = date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(f"{label} must be a valid YYYY-MM-DD date") from exc
        if parsed.isoformat() != value:
            raise ValueError(f"{label} must be YYYY-MM-DD")
        return parsed
