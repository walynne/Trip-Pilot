"""Daily destination weather and derived planning signals, independent of the LLM."""

from datetime import date, datetime, timedelta, timezone
import math
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from tools.openmeteo_client import DAILY_FIELDS, OpenMeteoClient, WeatherError


CONDITIONS = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Depositing rime fog", 51: "Light drizzle",
    53: "Moderate drizzle", 55: "Dense drizzle", 56: "Light freezing drizzle",
    57: "Dense freezing drizzle", 61: "Slight rain", 63: "Moderate rain",
    65: "Heavy rain", 66: "Light freezing rain", 67: "Heavy freezing rain",
    71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow", 77: "Snow grains",
    80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
    85: "Slight snow showers", 86: "Heavy snow showers", 95: "Thunderstorm",
    96: "Thunderstorm with slight hail", 99: "Thunderstorm with heavy hail",
}
DEFAULT_THRESHOLDS = {
    "rain_probability_moderate": 60, "rain_probability_high": 90,
    "wind_moderate_kmh": 40, "wind_high_kmh": 60,
    "heavy_rain_mm_per_day": 30,
}
MOCK_LOCATIONS = {
    "singapore": ("Singapore", 1.3521, 103.8198, "Asia/Singapore"),
    "hong kong": ("Hong Kong", 22.3193, 114.1694, "Asia/Hong_Kong"),
    "london": ("London", 51.5074, -0.1278, "Europe/London"),
    "new york": ("New York", 40.7128, -74.0060, "America/New_York"),
}
MOCK_SCENARIOS = {
    # max C, min C, rain probability %, wind km/h, WMO code, daily rain mm
    "normal": (28, 22, 20, 15, 2, 0),
    "heavy_rain": (25, 21, 85, 25, 65, 40),
    "strong_wind": (24, 19, 30, 70, 3, 1),
    "severe": (23, 18, 95, 85, 99, 60),
}


def _number(value):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value))


def _invalid():
    raise WeatherError("invalid_response", "Weather provider response failed validation.")


class WeatherSearchTool:

    def __init__(self, provider="open_meteo", *, mock_scenario="normal", thresholds=None):
        if not isinstance(provider, str) or provider not in {"open_meteo", "mock"}:
            raise ValueError("provider must be open_meteo or mock")
        if not isinstance(mock_scenario, str) or mock_scenario not in {*MOCK_SCENARIOS, "unavailable", "provider_error"}:
            raise ValueError("unsupported mock_scenario")
        self.provider = provider
        self.mock_scenario = mock_scenario
        self.thresholds = dict(DEFAULT_THRESHOLDS)
        if thresholds is not None:
            if not isinstance(thresholds, dict) or set(thresholds) - set(DEFAULT_THRESHOLDS):
                raise ValueError("unsupported risk thresholds")
            self.thresholds.update(thresholds)
        t = self.thresholds
        if (any(not _number(v) or v <= 0 for v in t.values())
                or not 0 < t["rain_probability_moderate"] <= t["rain_probability_high"] <= 100
                or t["wind_moderate_kmh"] > t["wind_high_kmh"]):
            raise ValueError("invalid risk thresholds")
        self.client = OpenMeteoClient() if provider == "open_meteo" else None

    def classify_risk(self, probability, wind, rain_mm, weather_code):
        """Application heuristics, never official alerts or confirmed disruptions."""
        t = self.thresholds
        level = "low"
        indicators = []
        if probability >= t["rain_probability_moderate"]:
            indicators.append("high_rain_probability")
            level = "moderate"
        if wind >= t["wind_moderate_kmh"]:
            indicators.append("strong_wind")
            level = "moderate"
        if rain_mm >= t["heavy_rain_mm_per_day"]:
            indicators.append("heavy_rain")
            level = "high"
        if weather_code in {95, 96, 99}:
            indicators.append("thunderstorm")
            level = "high"
        if probability >= t["rain_probability_high"] or wind >= t["wind_high_kmh"]:
            level = "high"
        return level, indicators

    def search_weather(self, location, start_date, end_date):
        """Return a JSON-safe dict; ValueError for input, WeatherError for provider failures.

        Dates are explicit destination-local calendar dates, inclusive. No fallback.
        """
        if not isinstance(location, str) or not 2 <= len(location.strip()) <= 200:
            raise ValueError("location must be a destination name of 2 to 200 characters")
        location = location.strip()
        dates = []
        for value in (start_date, end_date):
            if not isinstance(value, str):
                raise ValueError("dates must be YYYY-MM-DD strings")
            try:
                parsed = date.fromisoformat(value)
            except ValueError as exc:
                raise ValueError("dates must be valid YYYY-MM-DD strings") from exc
            if parsed.isoformat() != value:
                raise ValueError("dates must be YYYY-MM-DD strings")
            dates.append(parsed)
        start, end = dates
        if start > end or (end - start).days > 15:
            raise ValueError("date range must be ordered and contain at most 16 days")
        expected_dates = [(start + timedelta(days=i)).isoformat()
                          for i in range((end - start).days + 1)]
        if self.provider == "mock":
            resolved = MOCK_LOCATIONS.get(location.casefold())
            if resolved is None:
                raise WeatherError("location_not_found", "Destination is not in the mock location catalogue.")
            name, lat, lon, tz = resolved
            if self.mock_scenario == "unavailable":
                raise WeatherError("forecast_unavailable", "Simulated forecast unavailable (mock).")
            if self.mock_scenario == "provider_error":
                raise WeatherError("provider_error", "Simulated provider error (mock).")
            values = MOCK_SCENARIOS[self.mock_scenario]
            daily = {key: [value] * len(expected_dates)
                     for key, value in zip(DAILY_FIELDS, values)}
            daily["time"] = expected_dates
        else:
            payload = self.client.lookup_location(location)
            results = payload.get("results", [])
            if not isinstance(results, list):
                _invalid()
            if not results:
                raise WeatherError("location_not_found", "Destination was not found.")
            match = results[0]
            if not isinstance(match, dict):
                _invalid()
            lat, lon = match.get("latitude"), match.get("longitude")
            if not _number(lat) or not _number(lon) or not -90 <= lat <= 90 or not -180 <= lon <= 180:
                raise WeatherError("missing_coordinates", "Destination coordinates are missing or invalid.")
            name, tz = match.get("name"), match.get("timezone")
            if not isinstance(name, str) or not name or not isinstance(tz, str):
                _invalid()
            try:
                destination_zone = ZoneInfo(tz)
            except (ZoneInfoNotFoundError, ValueError) as exc:
                raise WeatherError("invalid_response", "Destination timezone is invalid.") from exc
            today = datetime.now(destination_zone).date()
            if start < today or end > today + timedelta(days=15):
                raise ValueError("live forecast dates must be within destination today through today + 15 days")
            payload = self.client.get_forecast(lat, lon, tz, start_date, end_date)
            if payload.get("timezone") != tz:
                _invalid()
            units = payload.get("daily_units")
            required_units = dict(zip(DAILY_FIELDS, ("°C", "°C", "%", "km/h", "wmo code", "mm")))
            if not isinstance(units, dict) or any(units.get(k) != v for k, v in required_units.items()):
                _invalid()
            daily = payload.get("daily")
        if not isinstance(daily, dict) or daily.get("time") != expected_dates:
            _invalid()
        for key in DAILY_FIELDS:
            column = daily.get(key)
            if not isinstance(column, list) or len(column) != len(expected_dates):
                _invalid()
            if any(value is None for value in column):
                raise WeatherError("forecast_unavailable", "Required daily forecast values are unavailable.")
            if any(not _number(value) for value in column):
                _invalid()
        forecast, events = [], []
        for i, day in enumerate(expected_dates):
            maximum, minimum, probability, wind, code, rain = [daily[k][i] for k in DAILY_FIELDS]
            if maximum < minimum or not 0 <= probability <= 100 or wind < 0 or rain < 0 or code not in CONDITIONS:
                _invalid()
            risk, indicators = self.classify_risk(probability, wind, rain, code)
            forecast.append({
                "date": day, "temperature_max_c": maximum, "temperature_min_c": minimum,
                "precipitation_probability_max": probability, "wind_speed_max_kmh": wind,
                "rain_sum_mm": rain, "weather_code": int(code), "condition": CONDITIONS[code],
                "risk_level": risk, "disruption_indicators": indicators,
            })
            if risk == "high":
                events.append({
                    "event_type": "weather_disruption", "location": name, "affected_date": day,
                    "severity": risk, "requires_replanning_assessment": True,
                    "source": "weather_search", "data_mode": "mock" if self.provider == "mock" else "live",
                    "signal_type": "simulated" if self.provider == "mock" else "derived_forecast_risk",
                    "confirmed_disruption": False,
                })
        return {
            "location": name, "coordinates": {"latitude": lat, "longitude": lon},
            "timezone": tz, "start_date": start_date, "end_date": end_date,
            "provider": self.provider, "data_mode": "mock" if self.provider == "mock" else "live",
            "status": "success", "forecast": forecast, "disruption_events": events,
            "official_alerts": [], "mock_scenario": self.mock_scenario if self.provider == "mock" else None,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "attribution": "Open-Meteo (CC BY 4.0); geocoding: GeoNames" if self.provider == "open_meteo" else "Simulated data",
        }
