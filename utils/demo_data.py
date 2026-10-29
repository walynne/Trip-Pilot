import json
from pathlib import Path
from typing import Any, Dict, List


_DEMO_DATA_PATH = Path(__file__).resolve().parent.parent / "demo" / "mock_trip_data.json"


def load_demo_trip_data() -> Dict[str, Any]:
    """Load the static demo payload used when live APIs are unavailable."""
    with _DEMO_DATA_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def get_demo_flights() -> List[Dict[str, Any]]:
    payload = load_demo_trip_data()
    return payload.get("flights", [])


def get_demo_hotel_result() -> Dict[str, Any]:
    payload = load_demo_trip_data()
    return payload.get("hotel", {})


def get_demo_weather_result() -> Dict[str, Any]:
    payload = load_demo_trip_data()
    return payload.get("weather", {})
