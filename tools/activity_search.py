"""Live place discovery through SerpApi Google Maps; no reservations."""

import os
from datetime import datetime, timezone
from urllib.parse import urlencode

import requests
from dotenv import load_dotenv

from utils.airport_mapper import CITY_TO_IATA


class ActivitySearchTool:
    def __init__(self, api_key=None):
        load_dotenv()
        self.api_key = api_key if api_key is not None else os.getenv("SERPAPI_API_KEY")

    def search(self, destination):
        fallback = {"status": "unavailable", "places": [], "provider": "serpapi"}
        if not self.api_key:
            return {**fallback, "message": "Live activity search requires SERPAPI_API_KEY; showing offline suggestions."}
        location = str(destination).strip()
        location = next((city.title() for city, code in CITY_TO_IATA.items()
                         if code == location.upper()), location)
        try:
            response = requests.get(
                "https://serpapi.com/search.json",
                params={"engine": "google_maps", "type": "search",
                        "q": f"tourist attractions in {location}", "hl": "en",
                        "api_key": self.api_key},
                timeout=15,
            )
            if response.status_code in (401, 403):
                return {**fallback, "message": "Live activity search credentials were rejected; showing offline suggestions."}
            if response.status_code == 429:
                return {**fallback, "message": "Live activity search quota exceeded; showing offline suggestions."}
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict) or payload.get("error"):
                return {**fallback, "message": "Live activity provider returned an error; showing offline suggestions."}
            places, seen = [], set()
            for item in payload.get("local_results") or []:
                if not isinstance(item, dict):
                    continue
                title = item.get("title")
                if not isinstance(title, str) or not title.strip():
                    continue
                identity = item.get("place_id") or (title, item.get("address"))
                if identity in seen:
                    continue
                seen.add(identity)
                query = {"api": 1, "query": f"{title} {location}"}
                if isinstance(item.get("place_id"), str):
                    query["query_place_id"] = item["place_id"]
                places.append({"name": title[:200],
                               "source_url": "https://www.google.com/maps/search/?" + urlencode(query)})
                if len(places) == 20:
                    break
            return {"status": "success" if places else "empty", "places": places,
                    "provider": "serpapi", "searched_at": datetime.now(timezone.utc).isoformat(),
                    "message": "Live Google Maps search results; confirm suitability, opening hours and tickets."
                    if places else "No live activity results found; showing offline suggestions."}
        except (requests.RequestException, ValueError, TypeError):
            # Do not expose request URLs, which include the API key.
            return {**fallback, "message": "Live activity search failed; showing offline suggestions."}