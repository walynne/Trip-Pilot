"""Synchronous Open-Meteo transport; no credentials or response logging."""

import requests


class WeatherError(Exception):
    """Safe provider failure with a stable machine-readable code."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


class OpenMeteoClient:

    def __init__(self):
        self.base_url = "https://api.open-meteo.com/v1"
        self.geocoding_url = "https://geocoding-api.open-meteo.com/v1/search"
        self.timeout = (5, 15)  # connect, read seconds

    def _get(self, url, params):
        try:
            response = requests.get(url, params=params, timeout=self.timeout)
            if response.status_code == 429:
                raise WeatherError("rate_limited", "Weather provider rate limit reached; retry later.")
            response.raise_for_status()
        except requests.exceptions.Timeout as exc:
            raise WeatherError("timeout", "Weather provider request timed out.") from exc
        except requests.exceptions.HTTPError as exc:
            raise WeatherError("http_error", "Weather provider returned an HTTP error.") from exc
        except requests.exceptions.RequestException as exc:
            raise WeatherError("network_error", "Weather provider could not be reached.") from exc
        try:
            payload = response.json()
        except ValueError as exc:
            raise WeatherError("invalid_response", "Weather provider returned invalid JSON.") from exc
        if not isinstance(payload, dict) or payload.get("error"):
            raise WeatherError("invalid_response", "Weather provider returned an invalid response.")
        return payload

    def lookup_location(self, location):
        city, separator, qualifier = location.partition(",")
        params = {
            "name": city.strip(), "count": 10 if separator else 1,
            "language": "en", "format": "json",
        }
        qualifier = qualifier.strip()
        if separator and len(qualifier) == 2 and qualifier.isascii() and qualifier.isalpha():
            params["countryCode"] = qualifier.upper()
        return self._get(self.geocoding_url, params)

    def get_forecast(self, latitude, longitude, timezone, start_date, end_date):
        return self._get(f"{self.base_url}/forecast", {
            "latitude": latitude, "longitude": longitude, "timezone": timezone,
            "start_date": start_date, "end_date": end_date,
            "temperature_unit": "celsius", "wind_speed_unit": "kmh",
            "precipitation_unit": "mm", "timeformat": "iso8601",
            "daily": ",".join(DAILY_FIELDS),
        })


DAILY_FIELDS = (
    "temperature_2m_max", "temperature_2m_min",
    "precipitation_probability_max", "wind_speed_10m_max", "weather_code",
    "rain_sum", "showers_sum",
)
