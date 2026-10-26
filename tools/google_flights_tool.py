"""Live Google Flights listings via SerpApi; never places a booking."""

import os
from decimal import Decimal, InvalidOperation

import requests
from dotenv import load_dotenv

from utils.currency import DEFAULT_TARGET_CURRENCY
from utils.travel_dates import ensure_future_departure_date, ensure_valid_return_date


class FlightSearchError(Exception):
    """Safe provider error suitable for display without exposing credentials."""


class GoogleFlightsSearchTool:
    def __init__(self, api_key=None):
        load_dotenv()
        self.api_key = api_key or os.getenv("SERPAPI_API_KEY")

    def _request(self, params):
        if not self.api_key:
            raise FlightSearchError("SERPAPI_API_KEY is required for live flight search.")
        try:
            response = requests.get(
                "https://serpapi.com/search.json",
                params={**params, "api_key": self.api_key},
                timeout=30,
            )
            if response.status_code == 401:
                raise FlightSearchError("SerpApi rejected the API key. Check SERPAPI_API_KEY.")
            if response.status_code == 429:
                raise FlightSearchError("SerpApi search quota or rate limit was exceeded.")
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise FlightSearchError("Google Flights search could not be completed. Check the provider connection and account.") from exc
        if not isinstance(payload, dict) or payload.get("error"):
            raise FlightSearchError("Google Flights returned a provider error. Check the SerpApi dashboard.")
        return payload

    @staticmethod
    def _options(payload):
        options = []
        seen = set()
        for item in (payload.get("best_flights") or []) + (payload.get("other_flights") or []):
            if not isinstance(item, dict) or not item.get("flights"):
                continue
            try:
                price = Decimal(str(item.get("price")))
                if not price.is_finite() or price < 0:
                    continue
                signature = (str(item["flights"]), str(price), item.get("departure_token"))
                if signature in seen:
                    continue
                seen.add(signature)
                options.append(item)
            except (InvalidOperation, ValueError):
                continue
        return sorted(options, key=lambda item: (
            len(item["flights"]) - 1, Decimal(str(item["price"])), item.get("total_duration") or float("inf"),
        ))

    @staticmethod
    def _leg(item):
        segments = item["flights"]
        first, last = segments[0], segments[-1]
        departure = first.get("departure_airport") or {}
        arrival = last.get("arrival_airport") or {}
        return {
            "stops": len(segments) - 1,
            "departure": departure.get("time"),
            "arrival": arrival.get("time"),
            "origin": departure.get("id"),
            "destination": arrival.get("id"),
        }

    def search_flights(self, origin, destination, departure_date, return_date=None):
        departure_date = ensure_future_departure_date(departure_date)
        return_date = ensure_valid_return_date(departure_date, return_date)
        params = {
            "engine": "google_flights", "departure_id": origin,
            "arrival_id": destination, "outbound_date": departure_date,
            "type": 1 if return_date else 2, "adults": 1,
            "currency": DEFAULT_TARGET_CURRENCY, "hl": "en",
        }
        if return_date:
            params["return_date"] = return_date
        payload = self._request(params)
        flights = []
        for outbound in self._options(payload)[:5]:
            inbound = None
            if return_date:
                token = outbound.get("departure_token")
                if not token:
                    continue
                returns = self._options(self._request({**params, "departure_token": token}))
                if not returns:
                    continue
                inbound = returns[0]
            # Return-selection results quote the whole trip, not an additional fare.
            selected = inbound or outbound
            segments = outbound["flights"] + (inbound["flights"] if inbound else [])
            names = list(dict.fromkeys(segment.get("airline") or "Unknown Airline" for segment in segments))
            price = format(Decimal(str(selected["price"])), ".2f")
            flight = {
                **self._leg(outbound), "airline": ", ".join(names),
                "airlines": names, "airline_names": names,
                "price": price, "currency": DEFAULT_TARGET_CURRENCY,
                "original_price": price, "original_currency": DEFAULT_TARGET_CURRENCY,
                "duration_minutes": (outbound.get("total_duration") or 0) + (inbound.get("total_duration") or 0 if inbound else 0),
                "provider": "google_flights", "data_mode": "live",
                "search_url": payload.get("search_metadata", {}).get("google_flights_url"),
                "fare_note": "Google Flights search listing; price and availability may change. No booking placed.",
            }
            if inbound:
                flight.update({f"return_{key}": value for key, value in self._leg(inbound).items()})
            flights.append(flight)
        return {"flights": flights}