"""Offline provider contracts and regression coverage; never call external APIs."""
from datetime import datetime, timedelta
from unittest.mock import Mock
from zoneinfo import ZoneInfo

import pytest
import requests

from tools.openmeteo_client import DAILY_FIELDS, WeatherError
from tools.weather_search import WeatherSearchTool


@pytest.fixture(autouse=True)
def block_network(monkeypatch):
    def blocked(*args, **kwargs):
        pytest.fail("Unexpected external request")
    monkeypatch.setattr(requests, "get", blocked)
    monkeypatch.setattr(requests, "post", blocked)


def live_dates():
    start = datetime.now(ZoneInfo("Asia/Singapore")).date()
    return start.isoformat(), (start + timedelta(days=1)).isoformat()


def response(payload, status=200):
    result = Mock(status_code=status)
    result.json.return_value = payload
    if status >= 400:
        result.raise_for_status.side_effect = requests.exceptions.HTTPError("sensitive upstream text")
    return result


def live_http(monkeypatch):
    start, end = live_dates()
    geo = {"results": [{"name": "Singapore", "latitude": 1.3521,
                        "longitude": 103.8198, "timezone": "Asia/Singapore", "country_code": "SG", "country": "Singapore"}]}
    daily = {k: [v, v] for k, v in zip(DAILY_FIELDS, [31, 25, 70, 20, 61, 2, 0])}
    daily["time"] = [start, end]
    forecast = {"timezone": "Asia/Singapore", "daily": daily,
                "daily_units": dict(zip(DAILY_FIELDS, ["°C", "°C", "%", "km/h", "wmo code", "mm", "mm"]))}
    http = Mock(side_effect=[response(geo), response(forecast)])
    monkeypatch.setattr(requests, "get", http)
    return http, geo, forecast


def test_initialization():
    assert WeatherSearchTool().client.base_url == "https://api.open-meteo.com/v1"
    assert WeatherSearchTool("mock").client is None
    with pytest.raises(ValueError):
        WeatherSearchTool("unknown")
    with pytest.raises(ValueError):
        WeatherSearchTool("mock", mock_scenario="unknown")


def test_weather_service_delegates_to_tool():
    from services.weather_service import WeatherService

    service = WeatherService("mock")
    assert service.tool.client is None
    result = service.get_weather("Singapore", "2026-11-15", "2026-11-17")
    assert result["status"] == "success"
    assert result["location"] == "Singapore"
    assert service.search_weather("Singapore", "2026-11-15", "2026-11-17")["forecast"][0]["date"] == "2026-11-15"


def test_mock_success_and_provenance():
    result = WeatherSearchTool("mock").search_weather("Singapore", "2026-11-15", "2026-11-17")
    assert len(result["forecast"]) == 3
    assert result["data_mode"] == result["provider"] == "mock"
    assert result["official_alerts"] == result["disruption_events"] == []
    assert result["timezone"] == "Asia/Singapore"
    assert result["forecast"][0]["risk_level"] == "low"


def test_live_success_and_request_contract(monkeypatch):
    http, _, _ = live_http(monkeypatch)
    result = WeatherSearchTool().search_weather("Singapore", *live_dates())
    assert result["data_mode"] == "live"
    assert result["forecast"][0]["condition"] == "Slight rain"
    assert result["forecast"][0]["disruption_indicators"] == ["high_rain_probability"]
    assert all(call.kwargs["timeout"] == (5, 15) for call in http.call_args_list)
    params = http.call_args_list[1].kwargs["params"]
    assert params["timezone"] == "Asia/Singapore"
    assert params["temperature_unit"] == "celsius"
    assert params["wind_speed_unit"] == "kmh"
    assert "rain_sum" in params["daily"]


@pytest.mark.parametrize("location", [None, "", " ", "S", 12])
def test_location_validation(location):
    with pytest.raises(ValueError):
        WeatherSearchTool("mock").search_weather(location, "2026-11-15", "2026-11-16")


@pytest.mark.parametrize("start,end", [
    ("bad", "2026-11-16"), ("2026-02-30", "2026-11-16"),
    ("20261115", "2026-11-16"), (None, "2026-11-16"),
    ("2026-11-17", "2026-11-16"), ("2026-11-01", "2026-11-17"),
])
def test_date_validation(start, end):
    with pytest.raises(ValueError):
        WeatherSearchTool("mock").search_weather("Singapore", start, end)


@pytest.mark.parametrize("offset", [-1, 16])
def test_live_horizon(monkeypatch, offset):
    http, _, _ = live_http(monkeypatch)
    day = (datetime.now(ZoneInfo("Asia/Singapore")).date() + timedelta(days=offset)).isoformat()
    with pytest.raises(ValueError, match="destination today"):
        WeatherSearchTool().search_weather("Singapore", day, day)
    assert http.call_count == 1


def test_live_horizon_includes_day_15(monkeypatch):
    _, _, forecast = live_http(monkeypatch)
    day = (datetime.now(ZoneInfo("Asia/Singapore")).date() + timedelta(days=15)).isoformat()
    forecast["daily"] = {k: [v[0]] for k, v in forecast["daily"].items()}
    forecast["daily"]["time"] = [day]
    assert WeatherSearchTool().search_weather("Singapore", day, day)["status"] == "success"


@pytest.mark.parametrize("failure,code", [
    (requests.exceptions.Timeout("secret"), "timeout"),
    (requests.exceptions.ConnectionError("secret"), "network_error"),
])
def test_network_failure(monkeypatch, failure, code):
    monkeypatch.setattr(requests, "get", Mock(side_effect=failure))
    with pytest.raises(WeatherError) as error:
        WeatherSearchTool().search_weather("Singapore", *live_dates())
    assert error.value.code == code
    assert "secret" not in str(error.value)


@pytest.mark.parametrize("status,code", [(400, "http_error"), (500, "http_error"), (429, "rate_limited")])
def test_http_failure(monkeypatch, status, code):
    monkeypatch.setattr(requests, "get", Mock(return_value=response({}, status)))
    with pytest.raises(WeatherError) as error:
        WeatherSearchTool().search_weather("Singapore", *live_dates())
    assert error.value.code == code
    assert "sensitive" not in str(error.value)


@pytest.mark.parametrize("payload", [[], {"error": True}, {"results": "bad"}, {"results": [None]}])
def test_malformed_geocoding(monkeypatch, payload):
    monkeypatch.setattr(requests, "get", Mock(return_value=response(payload)))
    with pytest.raises(WeatherError) as error:
        WeatherSearchTool().search_weather("Singapore", *live_dates())
    assert error.value.code == "invalid_response"


def test_invalid_json(monkeypatch):
    result = response({})
    result.json.side_effect = requests.exceptions.JSONDecodeError("bad", "x", 0)
    monkeypatch.setattr(requests, "get", Mock(return_value=result))
    with pytest.raises(WeatherError, match="invalid JSON"):
        WeatherSearchTool().search_weather("Singapore", *live_dates())


@pytest.mark.parametrize("match,code", [
    (None, "location_not_found"),
    ({"name": "X", "timezone": "UTC"}, "missing_coordinates"),
    ({"latitude": 100, "longitude": 0}, "missing_coordinates"),
    ({"name": "X", "latitude": 1, "longitude": 2, "timezone": "bad"}, "invalid_response"),
])
def test_location_resolution_errors(monkeypatch, match, code):
    payload = {} if match is None else {"results": [match]}
    monkeypatch.setattr(requests, "get", Mock(return_value=response(payload)))
    with pytest.raises(WeatherError) as error:
        WeatherSearchTool().search_weather("Singapore", *live_dates())
    assert error.value.code == code


@pytest.mark.parametrize("field,value", [
    ("temperature_2m_max", [None, 31]), ("temperature_2m_min", [32, 25]),
    ("precipitation_probability_max", [101, 70]), ("wind_speed_10m_max", [-1, 20]),
    ("rain_sum", [float("nan"), 2]), ("weather_code", [999, 61]),
    ("time", ["2020-01-01", "2020-01-02"]), ("rain_sum", []),
])
def test_invalid_daily(monkeypatch, field, value):
    _, _, forecast = live_http(monkeypatch)
    forecast["daily"][field] = value
    with pytest.raises(WeatherError):
        WeatherSearchTool().search_weather("Singapore", *live_dates())


def test_invalid_units_and_timezone(monkeypatch):
    for key, value in [("daily_units", {}), ("timezone", "UTC"), ("daily", [])]:
        _, _, forecast = live_http(monkeypatch)
        forecast[key] = value
        with pytest.raises(WeatherError):
            WeatherSearchTool().search_weather("Singapore", *live_dates())


@pytest.mark.parametrize("scenario,indicator", [
    ("heavy_rain", "heavy_rain"), ("strong_wind", "strong_wind"), ("severe", "thunderstorm")
])
def test_high_risk_mock(scenario, indicator):
    tool = WeatherSearchTool("mock", mock_scenario=scenario)
    first = tool.search_weather("Singapore", "2026-11-15", "2026-11-17")
    second = tool.search_weather("Singapore", "2026-11-15", "2026-11-17")
    first.pop("retrieved_at")
    second.pop("retrieved_at")
    assert first == second
    assert first["forecast"][0]["risk_level"] == "high"
    assert indicator in first["forecast"][0]["disruption_indicators"]
    assert first["disruption_events"][0]["signal_type"] == "simulated"
    assert first["disruption_events"][0]["confirmed_disruption"] is False


@pytest.mark.parametrize("scenario,code", [("unavailable", "forecast_unavailable"), ("provider_error", "provider_error")])
def test_mock_errors(scenario, code):
    with pytest.raises(WeatherError) as error:
        WeatherSearchTool("mock", mock_scenario=scenario).search_weather("Singapore", "2030-01-01", "2030-01-02")
    assert error.value.code == code


def test_thresholds_and_probability_not_intensity():
    tool = WeatherSearchTool("mock")
    assert tool.classify_risk(59, 39, 29, 2) == ("low", [])
    assert tool.classify_risk(60, 40, 0, 2)[0] == "moderate"
    assert tool.classify_risk(90, 0, 0, 2) == ("high", ["high_rain_probability"])
    assert tool.classify_risk(0, 60, 0, 2)[0] == "high"
    assert tool.classify_risk(0, 0, 30, 2) == ("high", ["heavy_rain"])
    assert WeatherSearchTool("mock", thresholds={"wind_high_kmh": 80}).classify_risk(0, 70, 0, 2)[0] == "moderate"
    for invalid in [{"unknown": 1}, {"wind_high_kmh": 10}, {"rain_probability_high": 101}]:
        with pytest.raises(ValueError):
            WeatherSearchTool(thresholds=invalid)


def test_c1_flight_tool_and_service_regression(monkeypatch):
    from services.flight_service import FlightService
    post = Mock(return_value=response({"data": {"id": "offer-request"}}))
    get = Mock(return_value=response({"data": [
        {"owner": {"name": "Test Airline"}, "total_amount": str(i), "total_currency": "HKD"}
        for i in range(7)
    ]}))
    monkeypatch.setattr(requests, "post", post)
    monkeypatch.setattr(requests, "get", get)
    service = FlightService()
    flights = service.get_flights("HKG", "SIN", "2026-11-15")
    assert len(flights) == 5
    assert flights[0] == {"airline": "Test Airline", "airlines": ["Unknown Airline"], "airline_names": ["Test Airline"], "price": "0.00", "currency": "HKD", "original_price": "0", "original_currency": "HKD", "stops": 0, "departure": None, "arrival": None, "origin": None, "destination": None}
    assert post.call_args.kwargs["json"]["data"]["slices"] == [
        {"origin": "HKG", "destination": "SIN", "departure_date": "2026-11-15"}]
    assert get.call_args.kwargs["params"] == {"offer_request_id": "offer-request"}


def test_c1_trip_agent_response_regression(monkeypatch):
    from agents.trip_agent import TripAgent
    agent = TripAgent.__new__(TripAgent)
    requirements = {"origin": "HKG", "destination": "SIN", "departure_date": "2026-11-15"}
    # Match the real TripAgent attributes used by run()
    agent.extractor = Mock()
    agent.extractor.extract.return_value = requirements
    agent.flight_service = Mock()
    agent.flight_service.get_flights.return_value = [{"airline": "Test Airline"}]
    agent.recommender = Mock()
    agent.recommender.recommend.return_value = "Recommended"
    agent.monitor = Mock()
    agent.monitor.detect.return_value = {"type": "none", "severity": "LOW"}
    agent.monitor.analyse.return_value = {"status": "ok"}
    agent.replanner = Mock()
    agent.replanner.replan.return_value = {"status": "not_needed"}

    result = agent.run("Travel to Singapore")
    assert set(result) == {"agent_steps", "trip_details", "requirements", "flights", "recommendation", "event", "monitor_result", "replan_result"}
    assert result["trip_details"] == requirements
    assert result["recommendation"] == "Recommended"
    agent.flight_service.get_flights.assert_called_once_with("HKG", "SIN", "2026-11-15")


def test_destination_local_horizon_at_utc_boundary(monkeypatch):
    import tools.weather_search as module
    real_datetime = datetime

    class FixedDateTime(real_datetime):
        @classmethod
        def now(cls, tz=None):
            instant = cls(2026, 10, 9, 23, 30, tzinfo=ZoneInfo("UTC"))
            return instant.astimezone(tz) if tz is not None else instant.replace(tzinfo=None)

    monkeypatch.setattr(module, "datetime", FixedDateTime)
    geo = {"results": [{"name": "Singapore", "latitude": 1, "longitude": 103,
                        "timezone": "Asia/Singapore"}]}
    day = "2026-10-10"
    daily = {k: [v] for k, v in zip(DAILY_FIELDS, [31, 25, 20, 15, 2, 0, 0])}
    daily["time"] = [day]
    forecast = {"timezone": "Asia/Singapore", "daily": daily,
                "daily_units": dict(zip(DAILY_FIELDS, ["°C", "°C", "%", "km/h", "wmo code", "mm", "mm"]))}
    monkeypatch.setattr(requests, "get", Mock(side_effect=[response(geo), response(forecast)]))
    assert WeatherSearchTool().search_weather("Singapore", day, day)["forecast"][0]["date"] == day
    monkeypatch.setattr(requests, "get", Mock(return_value=response(geo)))
    with pytest.raises(ValueError):
        WeatherSearchTool().search_weather("Singapore", "2026-10-09", "2026-10-09")


def test_forecast_timeout_does_not_fallback(monkeypatch):
    http, _, _ = live_http(monkeypatch)
    geocoding, _ = list(http.side_effect)
    http.side_effect = [geocoding, requests.exceptions.Timeout()]
    with pytest.raises(WeatherError) as error:
        WeatherSearchTool().search_weather("Singapore", *live_dates())
    assert error.value.code == "timeout"
    assert http.call_count == 2


def test_live_and_mock_schema_match(monkeypatch):
    live_http(monkeypatch)
    live = WeatherSearchTool().search_weather("Singapore", *live_dates())
    mock = WeatherSearchTool("mock").search_weather("Singapore", *live_dates())
    assert set(live) == set(mock)
    assert set(live["forecast"][0]) == set(mock["forecast"][0])


def test_missing_mock_location():
    with pytest.raises(WeatherError) as error:
        WeatherSearchTool("mock").search_weather("Unknown City", "2030-01-01", "2030-01-02")
    assert error.value.code == "location_not_found"


@pytest.mark.parametrize("rain,showers", [(0, 30), (10, 20), (29, 1)])
def test_showers_contribute_to_heavy_rain(monkeypatch, rain, showers):
    _, _, payload = live_http(monkeypatch)
    payload["daily"]["rain_sum"] = [rain, rain]
    payload["daily"]["showers_sum"] = [showers, showers]
    result = WeatherSearchTool().search_weather("Singapore", *live_dates())
    day = result["forecast"][0]
    assert day["rain_sum_mm"] == rain
    assert day["showers_sum_mm"] == showers
    assert day["risk_level"] == "high"
    assert "heavy_rain" in day["disruption_indicators"]
    assert result["disruption_events"][0]["signal_type"] == "derived_forecast_risk"
    assert result["disruption_events"][0]["confirmed_disruption"] is False


@pytest.mark.parametrize("field,value", [
    ("temperature_2m_max", True), ("wind_speed_10m_max", float("inf")),
    ("rain_sum", "30"), ("rain_sum", 10 ** 400),
    ("weather_code", 61.5), ("weather_code", False),
    ("showers_sum", -1), ("showers_sum", None),
])
def test_unexpected_numeric_values(monkeypatch, field, value):
    _, _, payload = live_http(monkeypatch)
    payload["daily"][field][0] = value
    with pytest.raises(WeatherError) as error:
        WeatherSearchTool().search_weather("Singapore", *live_dates())
    assert error.value.code == ("forecast_unavailable" if value is None else "invalid_response")


def test_missing_required_showers_column(monkeypatch):
    _, _, payload = live_http(monkeypatch)
    del payload["daily"]["showers_sum"]
    with pytest.raises(WeatherError) as error:
        WeatherSearchTool().search_weather("Singapore", *live_dates())
    assert error.value.code == "invalid_response"


def test_qualified_city_forwarded_and_first_result_selected(monkeypatch):
    http, geo, _ = live_http(monkeypatch)
    geo["results"].append({"name": "Another Singapore", "latitude": 1, "longitude": 1, "timezone": "UTC"})
    result = WeatherSearchTool().search_weather("  Singapore, SG  ", *live_dates())
    assert http.call_args_list[0].kwargs["params"]["name"] == "Singapore"
    assert http.call_args_list[0].kwargs["params"]["countryCode"] == "SG"
    assert result["coordinates"]["longitude"] == 103.8198


@pytest.mark.parametrize("start,end", [("2026-03-07", "2026-03-09"), ("2026-10-31", "2026-11-02")])
def test_dst_calendar_dates_preserved(monkeypatch, start, end):
    import tools.weather_search as module
    from datetime import date

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls.fromisoformat(start + "T12:00:00+00:00").astimezone(tz)

    monkeypatch.setattr(module, "datetime", FixedDateTime)
    days = [(date.fromisoformat(start) + timedelta(days=i)).isoformat() for i in range(3)]
    geo = {"results": [{"name": "New York", "latitude": 40.7, "longitude": -74,
                        "timezone": "America/New_York", "country_code": "US"}]}
    daily = {k: [v] * 3 for k, v in zip(DAILY_FIELDS, [25, 20, 20, 10, 2, 0, 0])}
    daily["time"] = days
    forecast = {"timezone": "America/New_York", "daily": daily,
                "daily_units": dict(zip(DAILY_FIELDS, ["°C", "°C", "%", "km/h", "wmo code", "mm", "mm"]))}
    http = Mock(side_effect=[response(geo), response(forecast)])
    monkeypatch.setattr(requests, "get", http)
    result = WeatherSearchTool().search_weather("New York, US", start, end)
    assert [day["date"] for day in result["forecast"]] == days
    assert http.call_args.kwargs["params"]["timezone"] == "America/New_York"


@pytest.mark.parametrize("thresholds", [{"wind_high_kmh": 10 ** 400}, {"wind_high_kmh": float("inf")}, {"wind_high_kmh": True}])
def test_invalid_numeric_thresholds(thresholds):
    with pytest.raises(ValueError):
        WeatherSearchTool(thresholds=thresholds)


def test_json_serializable_success(monkeypatch):
    import json
    live_http(monkeypatch)
    live = WeatherSearchTool().search_weather("Singapore", *live_dates())
    mock = WeatherSearchTool("mock", mock_scenario="severe").search_weather("Singapore", *live_dates())
    for result in (live, mock):
        assert json.loads(json.dumps(result, allow_nan=False)) == result


def test_documented_weather_failure_composition_preserves_c1():
    from agents.trip_agent import TripAgent
    agent = TripAgent.__new__(TripAgent)
    agent.extractor = Mock()
    agent.extractor.extract.return_value = {"origin": "HKG", "destination": "SIN", "departure_date": "2030-01-01"}
    agent.flight_service = Mock()
    agent.flight_service.get_flights.return_value = [{"airline": "Test Airline"}]
    agent.recommender = Mock()
    agent.recommender.recommend.return_value = "Recommended"
    agent.monitor = Mock()
    agent.monitor.detect.return_value = {"type": "none", "severity": "LOW"}
    agent.monitor.analyse.return_value = {"status": "ok"}
    agent.replanner = Mock()
    agent.replanner.replan.return_value = {"status": "not_needed"}
    result = agent.run("Trip request")
    try:
        result["weather"] = WeatherSearchTool("mock", mock_scenario="unavailable").search_weather("Singapore", "2030-01-01", "2030-01-02")
    except WeatherError as exc:
        result["weather"] = {"status": "unavailable", "error_code": exc.code, "data_mode": "mock"}
    assert result["recommendation"] == "Recommended"
    assert result["flights"] == [{"airline": "Test Airline"}]
    assert result["weather"]["error_code"] == "forecast_unavailable"


def test_trip_planner_keeps_hotels_when_weather_dates_are_unavailable(monkeypatch):
    from agents.planner_agent import PlannerAgent

    monkeypatch.setenv("TRIPPILOT_HOTEL_PROVIDER", "mock")
    planner = PlannerAgent()
    monkeypatch.setattr(planner, "_search_flights", lambda *args: [])
    planner.weather_tool = Mock(provider="open_meteo")
    planner.weather_tool.search_weather.side_effect = ValueError("live forecast dates must be within destination today through today + 15 days")
    result = planner.plan_trip({
        "origin": "HKG", "destination": "SIN",
        "departure_date": "2030-11-15", "return_date": "2030-11-18",
    })
    assert result["hotel"]["recommended"]["name"]
    assert result["weather"]["status"] == "unavailable"
    assert result["weather"]["error_code"] == "forecast_dates_unavailable"
    assert "15 days" in result["weather"]["message"]


def test_trip_planner_includes_flights_hotel_budget_and_schedule(monkeypatch):
    from agents.planner_agent import PlannerAgent
    from tools.weather_search import WeatherSearchTool

    monkeypatch.setenv("TRIPPILOT_HOTEL_PROVIDER", "mock")
    planner = PlannerAgent()
    planner.weather_tool = WeatherSearchTool("mock")
    plan = planner.plan_trip({
        "origin": "HKG",
        "destination": "SIN",
        "departure_date": "2026-11-15",
        "return_date": "2026-11-18",
        "guests": 2,
        "rooms": 1,
    })

    assert plan["summary"]["destination"] == "Singapore"
    assert plan["summary"]["trip_type"] == "round_trip"
    assert plan["flights"]["status"] == "success"
    assert plan["hotel"]["status"] == "success"
    assert plan["weather"]["status"] == "success"
    assert len(plan["schedule"]) >= 2
    assert plan["hotel"]["budget_total"] > 0
    weather_day = next(day for day in plan["schedule"] if day.get("temperature_min_c") is not None)
    assert weather_day["temperature_max_c"] >= weather_day["temperature_min_c"]
    assert 0 <= weather_day["precipitation_probability_max"] <= 100
    assert weather_day["wind_speed_max_kmh"] >= 0


def test_trip_planner_keeps_return_flight_date_but_uses_explicit_hotel_nights(monkeypatch):
    from agents.planner_agent import PlannerAgent
    from tools.weather_search import WeatherSearchTool

    monkeypatch.setenv("TRIPPILOT_HOTEL_PROVIDER", "mock")
    planner = PlannerAgent()
    planner.weather_tool = WeatherSearchTool("mock")
    flight_requests = []
    monkeypatch.setattr(
        planner.flight_service,
        "get_flights",
        lambda *args: flight_requests.append(args) or [],
    )

    plan = planner.plan_trip({
        "origin": "HKG",
        "destination": "SIN",
        "departure_date": "2026-10-26",
        "return_date": "2026-10-30",
        "hotel_nights": 1,
    })

    assert flight_requests == [("HKG", "SIN", "2026-10-26", "2026-10-30")]
    assert plan["hotel"]["check_in"] == "2026-10-26"
    assert plan["hotel"]["check_out"] == "2026-10-27"
    assert plan["hotel"]["nights"] == 1


def test_trip_planner_returns_partial_plan_when_city_is_outside_mock_catalogues(monkeypatch):
    from agents.planner_agent import PlannerAgent
    from tools.weather_search import WeatherSearchTool

    monkeypatch.setenv("TRIPPILOT_HOTEL_PROVIDER", "mock")
    planner = PlannerAgent()
    planner.weather_tool = WeatherSearchTool("mock")
    monkeypatch.setattr(
        planner.flight_service,
        "get_flights",
        lambda *args: [{"airline": "Sample Airline", "price": "450.00", "currency": "USD"}],
    )

    plan = planner.plan_trip({
        "origin": "HKG",
        "destination": "Tokyo",
        "departure_date": "2026-11-15",
        "return_date": "2026-11-18",
    })

    assert plan["flights"]["status"] == "success"
    assert plan["flights"]["recommended"]["airline"] == "Sample Airline"
    assert plan["hotel"]["status"] == "unavailable"
    assert plan["hotel"]["error_code"] == "location_not_found"
    assert plan["weather"]["status"] == "unavailable"
    assert plan["weather"]["error_code"] == "location_not_found"
    assert "hotel options are unavailable" in plan["recommendation"]
    assert "weather assessment is unavailable" in plan["recommendation"]


@pytest.mark.parametrize("qualifier,field,value", [("Singapore", "country", "Singapore"), ("Central", "admin1", "Central")])
def test_text_qualifier_matches_candidate(monkeypatch, qualifier, field, value):
    http, geo, _ = live_http(monkeypatch)
    geo["results"][0][field] = value
    geo["results"].insert(0, {"name": "Wrong City", "latitude": 0, "longitude": 0, "timezone": "UTC", "country": "Other"})
    result = WeatherSearchTool().search_weather("Singapore, " + qualifier, *live_dates())
    assert result["timezone"] == "Asia/Singapore"
    assert http.call_args_list[0].kwargs["params"]["name"] == "Singapore"
    assert http.call_args_list[0].kwargs["params"]["count"] == 10


def test_country_filter_is_verified(monkeypatch):
    http, geo, _ = live_http(monkeypatch)
    geo["results"][0]["country_code"] = "US"
    with pytest.raises(WeatherError) as error:
        WeatherSearchTool().search_weather("Singapore, SG", *live_dates())
    assert error.value.code == "location_not_found"
    assert http.call_count == 1


@pytest.mark.parametrize("location", ["Singapore,", ", SG", "Singapore, SG, extra"])
def test_invalid_location_qualifier(location):
    with pytest.raises(ValueError):
        WeatherSearchTool().search_weather(location, *live_dates())
