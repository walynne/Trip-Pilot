# C3 handoff to Person A

C3 is an independent synchronous tool. Actual wiring into TripAgent or `/chat`
remains a Person A task; neither module is modified by this PR.

## Input and invocation

```python
from tools.weather_search import WeatherSearchTool
from tools.openmeteo_client import WeatherError

weather_tool = WeatherSearchTool()
try:
    weather = weather_tool.search_weather(
        destination_city, destination_start_date, destination_end_date
    )
except (WeatherError, ValueError) as exc:
    weather = {
        "status": "unavailable",
        "provider": "open_meteo",
        "data_mode": "live",
        "error_code": exc.code if isinstance(exc, WeatherError) else "invalid_input",
        "message": str(exc),
    }
```

- `location`: city name, 2–200 characters after trimming; a country/admin qualifier
  reduces ambiguity, e.g. `Singapore, SG`. Two-letter qualifiers are ISO country
  codes (use GB, not UK); country/admin names must match exactly except case.
  Textual qualifier search is bounded to ten candidates. It is not an IATA code.
- Dates: strict ISO `YYYY-MM-DD`, inclusive, ordered, maximum 16 calendar days.
  Live dates must be destination today through today + 15 days.
- Obtain explicit destination-local travel dates from itinerary/user inputs.
  C1's departure date is not a reliable destination arrival date.
- To compose with C1, run its existing flow, then attach this optional `weather`
  result. Never replace flight recommendations on weather failure.

## Output and errors

Success is a JSON-serializable dictionary with location, coordinates, timezone,
requested dates, `provider`, `data_mode`, `status="success"`, `forecast`,
`disruption_events`, `official_alerts`, `mock_scenario`, `retrieved_at`, attribution.
Daily records include min/max Celsius, max rain probability %, max wind km/h,
`rain_sum_mm`, `showers_sum_mm`, WMO code/description, risk level and indicators.
Existing keys are retained; showers is an additive field.

Input/configuration/horizon failures raise `ValueError`. Provider failures raise
`WeatherError` with safe text and `.code`: `timeout`, `http_error`, `rate_limited`,
`network_error`, `invalid_response`, `location_not_found`, `missing_coordinates`,
`forecast_unavailable`, or mock-only `provider_error`. There is no automatic retry
or live-to-mock fallback. Missing required values fail the whole requested range.

## Mock configuration

```python
weather_tool = WeatherSearchTool(provider="mock", mock_scenario="severe")
weather = weather_tool.search_weather("Singapore", "2030-01-01", "2030-01-03")
```

Scenarios: normal, heavy_rain, strong_wind, severe, unavailable, provider_error.
Catalogue: Singapore, Hong Kong, London, New York. Mock mode makes no network
calls. Forecasts/signals repeat for the same inputs; retrieval timestamps vary.
Both success modes share the same schema and explicitly identify provenance.

## Disruption event example (schema only)

```json
{
  "event_type": "weather_disruption",
  "location": "Singapore",
  "affected_date": "2030-01-01",
  "severity": "high",
  "requires_replanning_assessment": true,
  "source": "weather_search",
  "data_mode": "mock",
  "signal_type": "simulated",
  "confirmed_disruption": false
}
```

Live signals use `signal_type="derived_forecast_risk"`. Only high-risk days
produce events; moderate days still expose daily indicators. Person A decides
whether an assessment warrants replanning. C3 takes no operational action.

## Limits

Risk thresholds are documented application heuristics, not official warnings.
Heavy rain means daily rain + showers ≥30 mm by default, not hourly intensity.
Probability alone never establishes heavy rainfall. No official alert feed is
queried; an empty alerts array does not prove absence of warnings. The classifier
is intentionally not a complete snow/ice/heat/flood/aviation hazard model.

Geocoding selects the first result; callers should verify the resolved destination.
Open-Meteo daily aggregation uses a fixed offset across a DST transition; tests
verify retained calendar dates, not DST-aware physical aggregation. Provider
availability can be shorter than the 16-day upper bound. No historical weather,
caching, booking changes or autonomous replanning are implemented.
