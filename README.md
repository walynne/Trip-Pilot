# Trip-Pilot

TripPilot is an agentic AI corporate travel planner that autonomously creates, manages and adapts business trip itineraries while ensuring compliance with corporate policies and budget constraints. 

Quick start on Windows, in this folder:
    for mac:
    python3 -m venv .venv && source .venv/bin/activate 
    foc windows:
    python -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    python app.py

## Project structure

```text
Trip-Pilot/
├── README.md
├── requirements.txt
├── .env
├── docker-compose.yml
├── main.py
│
├── api/
│   ├── routes/
│   │   ├── trips.py
│   │   ├── approvals.py
│   │   └── users.py
│   └── middleware/
│
├── agents/
│   ├── planner_agent.py
│   ├── travel_agent.py
│   ├── policy_agent.py
│   ├── budget_agent.py
│   ├── monitoring_agent.py
│   └── replanning_agent.py
│
├── harness/
│   ├── orchestrator.py
│   ├── state_manager.py
│   ├── approval_manager.py
│   ├── rule_engine.py
│   └── action_validator.py
│
├── rag/
│   ├── retriever.py
│   ├── vector_store.py
│   ├── document_loader.py
│   └── embeddings.py
│
├── knowledge_base/
│   ├── travel_policy/
│   │   ├── company_policy.pdf
│   │   ├── supplier_rules.pdf
│   │   └── expense_limits.pdf
│   │
│   └── approval_rules/
│
├── tools/
│   ├── flight_search.py
│   ├── hotel_search.py
│   ├── transport_search.py
│   ├── weather_service.py
│   ├── maps_service.py
│   ├── calendar_service.py
│   └── notification_service.py
│
├── workflows/
│   ├── itinerary_creation.py
│   ├── trip_monitoring.py
│   ├── disruption_management.py
│   └── approval_workflow.py
│
├── models/
│   ├── trip.py
│   ├── itinerary.py
│   ├── traveller.py
│   ├── budget.py
│   └── approval.py
│
├── database/
│   ├── db.py
│   ├── repositories/
│   └── migrations/
│
├── prompts/
│   ├── planner_prompt.txt
│   ├── policy_prompt.txt
│   ├── budget_prompt.txt
│   └── replanner_prompt.txt
│
├── monitoring/
│   ├── event_listener.py
│   ├── flight_updates.py
│   ├── weather_alerts.py
│   └── meeting_changes.py
│
├── logs/
│
├── tests/
│   ├── test_agents.py
│   ├── test_rag.py
│   ├── test_rules.py
│   └── test_workflows.py
│
└── docs/
    ├── architecture.md
    ├── api_design.md
    └── sequence_diagrams.md
```
##Reference
[TripPilot_Corporate_Travel_Policy_v2.docx](https://github.com/user-attachments/files/32784763/TripPilot_Corporate_Travel_Policy_v2.docx)
[Division of labor.docx](https://github.com/user-attachments/files/33254831/Division.of.labor.docx)


## C3 Weather Integration

C3 provides destination-local daily forecasts and deterministic weather risk signals
for Person A's planning workflow. It does not book, replan, or issue official alerts.
C1 and B1 remain unchanged. Architecture: `WeatherSearchTool → OpenMeteoClient →
requests → Open-Meteo`. Classes, synchronous requests and JSON-safe dictionaries
match C1. No service wrapper is needed: C3 already returns normalized data, while
FlightService specifically reduces Duffel offers to flight summaries.

### Provider and interface

Requires Python 3.9+ with IANA timezone data, and the existing `requests` dependency.
No new runtime dependencies or API key are needed for the non-commercial API.

```python
from tools.weather_search import WeatherSearchTool

weather_tool = WeatherSearchTool()  # provider="open_meteo"
# Explicit destination-local dates; choose dates within the live forecast window.
weather = weather_tool.search_weather("Singapore", start_date, end_date)

mock_tool = WeatherSearchTool(provider="mock", mock_scenario="severe")
weather = mock_tool.search_weather("Singapore", "2026-11-15", "2026-11-17")
```

`WeatherSearchTool(provider="open_meteo", *, mock_scenario="normal", thresholds=None)`
exposes `search_weather(location, start_date, end_date)`. Dates are inclusive,
strict `YYYY-MM-DD`, ordered, with at most 16 days per request. Live dates must
fall between destination today and today + 15 days. Unsupported future/past
requests are rejected; historical forecasts are outside C3 scope.

[Open-Meteo forecast documentation](https://open-meteo.com/en/docs) specifies
`/v1/forecast` and up to 16 forecast days, although availability varies by model
and variable. [Geocoding](https://open-meteo.com/en/docs/geocoding-api) resolves
city names to coordinates and an IANA timezone. C3 uses the first matching result and
passes that timezone explicitly to the daily forecast request. Search with an ISO two-letter country qualifier (for example `London, GB`),
or an exact country/admin name; IATA
airport codes are not supported as destination names. Returned dates must match
the complete requested local calendar range. Open-Meteo currently applies a
fixed timezone offset across a range spanning a DST transition; daily calendar
dates are retained, and no arrival timestamps are inferred.

Requested daily variables: `temperature_2m_max`, `temperature_2m_min`,
`precipitation_probability_max`, `wind_speed_10m_max`, `weather_code`, `rain_sum`, `showers_sum`.
Units are explicitly Celsius, km/h, percentages and millimetres; returned units,
array lengths, dates, numeric values, WMO codes and timezone are validated.
Null required values are unavailable, never zero or a low-risk forecast.

[Current free-use terms](https://open-meteo.com/en/terms): non-commercial use only;
less than 10,000 calls/day, 5,000/hour and 600/minute. Weather data require CC BY
4.0 attribution to Open-Meteo; geocoding is based on GeoNames. Preserve the
response attribution in downstream displays. This educational implementation
adds no paid service. Commercial deployment needs a separate licensing decision.

### Response schema

Live and mock success responses have the same keys:

```text
location: resolved destination name
coordinates: {latitude, longitude}
timezone: IANA destination timezone
start_date, end_date: requested local dates
provider: open_meteo | mock
data_mode: live | mock
status: success
forecast: [{date, temperature_max_c, temperature_min_c,
            precipitation_probability_max, wind_speed_max_kmh, rain_sum_mm, showers_sum_mm,
            weather_code, condition, risk_level, disruption_indicators}]
disruption_events: [{event_type: weather_disruption, location, affected_date,
                     severity: high, requires_replanning_assessment: true,
                     source: weather_search, data_mode, signal_type,
                     confirmed_disruption: false}]
official_alerts: []
mock_scenario: null for live, configured scenario for mock
retrieved_at: current UTC ISO-8601 retrieval timestamp
attribution: provider attribution or Simulated data
```

Events flag an assessment opportunity, not a confirmed impact. Live events have
`signal_type="derived_forecast_risk"`; mock events have `signal_type="simulated"`.
No official alert feed is queried: an empty `official_alerts` does **not** mean
there are no official warnings. Weather narrative and replanning decisions stay
with Person A, separate from these deterministic rules.

### Mock mode

No network or geocoding requests occur in mock mode. Supported destination names
(case-insensitive): Singapore, Hong Kong, London, New York. Scenarios:
`normal`, `heavy_rain`, `strong_wind`, `severe`, `unavailable`, `provider_error`.
Choose explicitly using `mock_scenario`; date ranges may be in the distant future.
The same location, dates, thresholds and scenario yield identical forecasts and
signals. Only `retrieved_at` changes between calls. Error scenarios raise
`WeatherError` with an explicitly simulated message; mock is never a live fallback.

### Risk classification

These are application planning heuristics, not meteorological warning thresholds.
All comparisons are inclusive; the highest applicable level wins.

| Rule | Default threshold | Level | Indicator |
| --- | --- | --- | --- |
| Rain probability | ≥60% | moderate | high_rain_probability |
| Rain probability | ≥90% | high | high_rain_probability |
| Maximum sustained wind | ≥40 km/h | moderate | strong_wind |
| Maximum sustained wind | ≥60 km/h | high | strong_wind |
| Forecast daily rain + showers amount | ≥30 mm/day | high | heavy_rain |
| WMO code | 95, 96, 99 | high | thunderstorm |
| No rule triggered | — | low | none |

`heavy_rain` means the configured daily rain + showers amount is met or exceeded; it does not
establish hourly intensity. Rain probability alone never produces `heavy_rain`.
Configure through `thresholds`, using keys `rain_probability_moderate`,
`rain_probability_high`, `wind_moderate_kmh`, `wind_high_kmh`,
`heavy_rain_mm_per_day`. Unknown/non-finite/non-positive thresholds and reversed
moderate/high thresholds are rejected. This intentionally narrow classifier
is not a comprehensive snow, ice, flood, cyclone, heat or aviation hazard model.

### Failure handling and Person A integration

Invalid provider, location strings, dates, ranges or thresholds raise `ValueError`.
Provider failures raise `tools.openmeteo_client.WeatherError`, with safe messages
and a stable `.code`: `timeout`, `http_error`, `rate_limited`, `network_error`,
`invalid_response`, `location_not_found`, `missing_coordinates`,
`forecast_unavailable`, or mock-only `provider_error`. There is no silent fallback,
response logging, automatic retry or raw provider error text in public messages.
Each HTTP call uses `(5, 15)` second connect/read timeouts. On rate limiting,
callers should retry later under their own bounded retry policy.

Person A can compose an optional weather field **after** the existing flight flow:

```python
from tools.openmeteo_client import WeatherError
from tools.weather_search import WeatherSearchTool

result = trip_agent.run(user_message)  # existing C1 contract stays unchanged
# These three values must come from explicit itinerary/user inputs.
try:
    result["weather"] = WeatherSearchTool().search_weather(
        destination_city, destination_start_date, destination_end_date
    )
except (WeatherError, ValueError) as exc:
    result["weather"] = {
        "status": "unavailable", "provider": "open_meteo", "data_mode": "live",
        "error_code": exc.code if isinstance(exc, WeatherError) else "invalid_input",
        "message": str(exc),
    }
```

This adapter is an integration example, not a change to TripAgent or `/chat`.
Weather failure cannot replace C1's recommendation. Do not derive destination
start/end dates from departure date: overnight flights and timezone crossings
can change arrival day. Current FlightService discards arrival timestamps and
TripAgent extracts only IATA codes and departure date. Explicit destination city
and destination-local travel dates are therefore required; missing inputs must
not be invented. No autonomous replanning, booking changes or orchestration added.

### Testing and validation

```bash
python -m pip install pytest requests openai python-dotenv
python -m pytest -q
```

`tests/test_weather_search.py` blocks unmocked requests. Coverage includes mock
provenance/reproducibility, live response normalization via mocked HTTP, input and
horizon validation, timeout/network/HTTP/429 failures, malformed JSON/arrays/units,
missing locations/coordinates/data, threshold boundaries, and unchanged C1 flight
service/tool and TripAgent response contracts. Automated tests never call live
Open-Meteo, Duffel or NexLLM. The repository had no pre-existing test files at the
C3 baseline. An optional manual live smoke must use actual destination-current
dates; real forecast availability is distinct from mocked contract validation.

Known limits: first-result geocoding can be ambiguous; textual qualifier lookup
is bounded to ten candidates and may return no match; max 16 days is an upper
bound, not a guarantee of all variables; any missing required value fails the
whole requested range; no caching, official alerts or historical lookup; mock
catalogue is intentionally small. Person A owns assessment and future replanning.

### C3 review follow-up

PR review adds `showers_sum_mm` without removing existing response keys. The
heavy-rain rule uses `rain_sum_mm + showers_sum_mm`, because Open-Meteo reports
rain and showers separately. This is daily liquid rainfall, not hourly intensity
or total precipitation including snow. Both amounts must be available.

Pull requests run a lightweight Python 3.12 test workflow without API credentials.
See [Person A handoff](docs/c3-integration-handoff.md) for the concise integration
contract and [review report](docs/c3-pr-review.md) for findings and validation.
Actual TripAgent integration is still an outstanding Person A task.

Country-code qualifiers use Open-Meteo `countryCode` explicitly and are verified
against returned `country_code`. Textual country/admin qualifiers are compared
case-insensitively against up to ten city candidates; unmatched qualifiers fail
safely. Two-letter qualifiers mean ISO country codes, not admin abbreviations.
## B2 Policy Retrieval (local Demo Baseline)

`PolicySearchTool` provides offline, synchronous policy evidence retrieval from an authorized local version 2.0 DOCX. It preserves paragraph/table references, section context and source provenance. This is the retrieval stage of RAG; it does not generate policy answers or make B3 compliance/approval decisions, and TripAgent remains unchanged.

```python
from tools.policy_search import PolicySearchTool

policy_tool = PolicySearchTool()
evidence = policy_tool.search_policy("Singapore hotel maximum nightly rate", top_k=5)
```

Place the approved DOCX at `policies/TripPilot_Corporate_Travel_Policy_v2.docx`, or supply `document_path` explicitly. The document and local evaluation artifacts are ignored by Git; publication requires authorization. No embedding model, API key or new dependency is required for B2. Missing sources fail explicitly without fabricated policy content.

Run `python -m pytest -q` using Python 3.12. Tests use synthetic fixtures and do not require the private DOCX or external services. See [B2 integration handoff](docs/b2-integration-handoff.md) for input/output/error contracts, evaluation instructions, source limitations and outstanding Person A/B3 integration work. The original project structure above includes planned components and should not be treated as proof of executable functionality.
