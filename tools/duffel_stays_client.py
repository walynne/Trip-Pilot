"""Small Duffel Stays search adapter; it never creates a booking."""

import os

import requests

from tools.openmeteo_client import OpenMeteoClient, WeatherError


class DuffelStaysClient:
    def __init__(self, *, session=None):
        self.base_url = (os.getenv("DUFFEL_BASE_URL") or "https://api.duffel.com").rstrip("/")
        self.api_key = os.getenv("DUFFEL_API_KEY")
        if not self.api_key:
            raise ValueError("DUFFEL_API_KEY is required for the Duffel hotel provider")
        self.session = session or requests.Session()
        self.geocoder = OpenMeteoClient()
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Duffel-Version": "v2",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def search(self, location, check_in, check_out, guests, rooms):
        city = location.split(",", 1)[0].strip()
        try:
            geocoding = self.geocoder.lookup_location(location)
        except WeatherError as exc:
            raise ValueError("Could not resolve hotel destination coordinates") from exc
        candidates = geocoding.get("results") or []
        if not candidates:
            raise ValueError("Hotel destination was not found")
        place = candidates[0]
        latitude = place.get("latitude")
        longitude = place.get("longitude")
        if not isinstance(latitude, (int, float)) or not isinstance(longitude, (int, float)):
            raise ValueError("Hotel destination coordinates are unavailable")

        adults_by_room = [guests // rooms + (1 if index < guests % rooms else 0)
                          for index in range(rooms)]
        payload = {
            "data": {
                "check_in_date": check_in,
                "check_out_date": check_out,
                "guests": [{"type": "adult"} for _ in range(guests)],
                "rooms": rooms,
                "location": {
                    "geographic_coordinates": {
                        "latitude": latitude,
                        "longitude": longitude,
                    },
                    "radius": 5,
                },
            }
        }
        search = self._request("POST", "/stays/search", json=payload)
        data = search.get("data")
        results = data.get("results") if isinstance(data, dict) else None

        if not isinstance(results, list):
            raise ValueError("Duffel Stays returned an invalid search response")

        complete_results = []
        for result in results:
            result_id = result.get("id")
            if not result_id:
                raise ValueError("Duffel Stays returned a search result without an ID")
            rates_payload = self._request(
                "POST",
                f"/stays/search_results/{result_id}/actions/fetch_all_rates",
            )
            rates_data = rates_payload.get("data")
            if not isinstance(rates_data, dict):
                raise ValueError("Duffel Stays returned invalid rate details")
            complete_results.append(rates_data)
        return {
            "location": place.get("name") or city,
            "country_code": place.get("country_code"),
            "latitude": latitude,
            "longitude": longitude,
            "results": complete_results,
        }

    def _request(self, method, path, **kwargs):
        try:
            response = self.session.request(
                method,
                f"{self.base_url}{path}",
                headers=self.headers,
                timeout=(5, 20),
                **kwargs,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.exceptions.Timeout as exc:
            raise ValueError("Duffel hotel search timed out") from exc
        except requests.exceptions.HTTPError as exc:
            status_code = exc.response.status_code if exc.response is not None else None
            if status_code in {401, 403}:
                raise ValueError(
                    "Duffel Stays access denied; verify the token and request Stays access for this account"
                ) from exc
            raise ValueError(f"Duffel hotel provider returned HTTP {status_code}") from exc
        except requests.exceptions.RequestException as exc:
            raise ValueError("Duffel hotel provider could not be reached") from exc
        except (TypeError, ValueError) as exc:
            raise ValueError("Duffel hotel provider returned an invalid response") from exc
        if not isinstance(payload, dict):
            raise ValueError("Duffel hotel provider returned an invalid response")
        return payload