# C1 / C2 / C3 combined tool-layer handoff

## Validated scope and baseline

This validation branch combines latest main `6025095`, C2 PR #5 head `da46064`,
and C3 PR #4 head `f979499` using normal merges. Neither PR is merged into main.
The only conflict was an add/add Python workflow; retained C2's secure version
with checkout credentials disabled, read-only permissions and Python 3.12.
A push trigger limited to `feature/c2-c3-integration-validation` runs this branch's
CI without requiring another PR; pull-request testing remains enabled.

C1, C2 and C3 remain independent synchronous tools. No public signatures, existing
C2/C3 tests, TripAgent, policy logic, booking systems or orchestration were modified.
The collector in `tests/test_combined_tools.py` is only an offline validation harness;
it is not a new application service or orchestrator. Person A still owns app wiring.

## Explicit destination-local fixture

All of these dates are explicit inputs, not inferred from a flight offer:

| Input | Singapore fixture |
| --- | --- |
| Flight route | HKG → SIN |
| Flight departure date | 2030-11-14 |
| Destination city / timezone | Singapore / Asia/Singapore |
| Hotel check-in (inclusive) | 2030-11-15 |
| Hotel check-out (exclusive) | 2030-11-18 |
| Weather start / end (both inclusive) | 2030-11-15 / 2030-11-17 |
| Guests / rooms | 1 / 1 |

This fixture simulates a three-night, three-day destination stay. Departure does
not establish arrival day: overnight flights and timezone crossings require actual
arrival timestamps or explicit user/itinerary dates. Do not invent dates. Weather
coverage may include the checkout day if Person A explicitly requests it; hotel
checkout stays exclusive. A same-day weather range is valid, a zero-night hotel stay
is not. A historical/far-future live forecast must never be silently replaced by mock.

## Public invocation contracts

```python
from tools.flight_search import FlightSearchTool
from tools.hotel_search import HotelSearchTool
from tools.weather_search import WeatherSearchTool

# C1's real tool performs Duffel HTTP calls; automated validation stubs requests.
# Do not run this line against a provider merely to reproduce the offline demo.
flights = FlightSearchTool().search_flights("HKG", "SIN", "2030-11-14")

hotels = HotelSearchTool(provider="mock").search_hotels(
    "Singapore", "2030-11-15", "2030-11-18", guests=1, rooms=1
)
weather = WeatherSearchTool(provider="mock").search_weather(
    "Singapore", "2030-11-15", "2030-11-17"
)
```

C1 inputs remain IATA origin/destination and departure date. Its output is the raw
Duffel JSON dictionary. FlightService remains a separate existing adapter returning
up to five `{airline, price, currency}` rows. C1 does not supply a provenance envelope;
any composed application/test envelope must accurately identify its actual mode.
The validation suite labels flight results `stubbed`; it does not claim live Duffel
validation or fabricate a `mock` provider implementation inside C1.

C2 inputs are city (optional supported country qualifier), strict local dates,
1–30 nights, 1–32 integer guests, 1–8 integer rooms, max four guests/room. The
output includes provider/mock mode, status, local currency, dates/counts, fictional
hotel attributes and pricing. Monetary fields are two-decimal strings: rate per
room/night × rooms × nights = subtotal; fictional 10% tax on subtotal is rounded
HALF_UP; fictional fee is 12.00 per room/stay; total sums those components.

C3 takes a destination name and strict local dates, inclusive, up to 16 days.
Mock uses the four-city catalogue and permits future dates. Live Open-Meteo requires
destination today through today +15 days and can have missing required variables.
Output includes coordinates/timezone, provenance, daily weather, derived risk,
assessment events, UTC retrieval time and attribution. No official alert feed queried.

C2 and C3 success dictionaries are JSON-safe. Keep them intact inside the combined
response. Do not compare HKD flight cost with SGD hotel cost without an agreed FX
source/policy; currency consistency within a provider is not currency equivalence.

## Failure isolation and optional response composition

Person A should invoke each tool within its own narrow error boundary. Errors from
one must not discard another tool's success or replace C1's existing recommendation.
For example (application wiring proposal; not implemented in TripAgent):

```python
import requests
from tools.hotel_search import HotelError
from tools.openmeteo_client import WeatherError

combined = {}
try:
    raw_flights = flight_tool.search_flights(origin, destination, departure_date)
    combined["flights"] = {
        "status": "success", "provider": "duffel", "data_mode": "live",
        "data": raw_flights,
    }  # use live only when this was an actual provider request
except requests.exceptions.RequestException:
    combined["flights"] = {
        "status": "unavailable", "provider": "duffel", "data_mode": "live",
        "error_code": "flight_provider_error",
    }

try:
    combined["hotels"] = hotel_tool.search_hotels(
        city, check_in, check_out, guests=guests, rooms=rooms
    )
except (HotelError, ValueError) as exc:
    combined["hotels"] = {
        "status": "unavailable", "provider": "mock", "data_mode": "mock",
        "error_code": exc.code if isinstance(exc, HotelError) else "invalid_input",
    }

try:
    combined["weather"] = weather_tool.search_weather(city, weather_start, weather_end)
except (WeatherError, ValueError) as exc:
    combined["weather"] = {
        "status": "unavailable", "provider": weather_tool.provider,
        "data_mode": "mock" if weather_tool.provider == "mock" else "live",
        "error_code": exc.code if isinstance(exc, WeatherError) else "invalid_input",
    }
```

C1 currently raises requests exceptions for network/HTTP failures, while malformed
Duffel JSON/schema can also raise ValueError/KeyError. Its parsing/logging behavior
was not redesigned in this task; an eventual Person A adapter needs focused response
validation rather than a broad catch-all. Combined tests cover a flight timeout;
existing C3 tests cover its other provider errors. Do not expose raw upstream exception
text, headers, credentials or C1 response logs in application error messages.

C2 ValueError identifies invalid inputs/configuration; HotelError codes are
location_not_found/provider_error. Fully booked is `no_results`, not an exception.
C3 ValueError identifies input/configuration/horizon failures; WeatherError exposes
safe `.code` values documented in the C3 handoff. Missing weather remains unavailable,
never fabricated low risk; provider failures never trigger live-to-mock fallback.

## Example composed response (abbreviated, synthetic fixture only)

This illustrates a projection of the independently returned results, not a new
mandatory schema; retain full original dictionaries in application state.

```json
{
  "flights": {
    "status": "success", "provider": "duffel", "data_mode": "stubbed",
    "data": {"data": [{"id": "stub-offer", "owner": {"name": "Sample Airline"},
                        "total_amount": "1500.00", "total_currency": "HKD"}]}
  },
  "hotels": {
    "status": "success", "provider": "mock", "data_mode": "mock",
    "location": "Singapore", "check_in": "2030-11-15", "check_out": "2030-11-18",
    "nights": 3, "currency": "SGD", "result_count": 3,
    "example_cheapest_pricing": {
      "room_nightly_rate": "115.00", "subtotal": "345.00", "taxes": "34.50",
      "fees": "12.00", "total": "391.50", "taxes_are_simulated": true
    }
  },
  "weather": {
    "status": "success", "provider": "mock", "data_mode": "mock",
    "location": "Singapore", "timezone": "Asia/Singapore",
    "start_date": "2030-11-15", "end_date": "2030-11-17", "mock_scenario": "severe",
    "example_event": {
      "event_type": "weather_disruption", "affected_date": "2030-11-15",
      "severity": "high", "requires_replanning_assessment": true,
      "source": "weather_search", "data_mode": "mock", "signal_type": "simulated",
      "confirmed_disruption": false
    }
  }
}
```

Mock hotels/taxes/supplier flags are not verified prices, official tax rates or
approved suppliers. Weather risks are application heuristics, not official warnings
or confirmed disruption. Keep provider, data_mode, scenario, attribution and simulation
flags visible when forwarding/rendering results. Retrieval timestamps can differ while
forecast/offer data repeat. Person A owns assessment; C3 does not replan or book.

## Missing B2/B3 and approval dependencies (separate from tool compatibility)

Inspection found empty policy_agent.py, budget_agent.py, monitoring_agent.py,
replanning_agent.py and travel_agent.py. The README's proposed rag/, knowledge_base/
and harness/ directories are absent. No executable policy evaluation, RAG retrieval,
policy-source citation or human approval workflow was evidenced/tested here.

- B2 still needs policy-document ingestion, retrieval/indexing, point-of-use evidence
  and a tested query/source contract. A requirements entry for a library is not an
  implemented retrieval pipeline.
- B3 still needs authoritative rules, limits, supplier evidence, currency/FX handling,
  explainable evaluation results and tests. C2 candidate metadata cannot make those
  decisions. Human approval state/transitions require a separate implemented contract.
- Person A needs explicit arrival/stay inputs and optional result composition. Current
  TripAgent remains flight-only. Its live LLM/Duffel flow was not exercised by these tests.
- Legacy api/routes/trips.py imports PlannerAgent, but planner_agent.py defines
  FlightRecommendationAgent instead. That route is not the Flask app.py flow and is
  not claimed operational; it remains an unrelated existing integration issue.

## Verification and remaining limits

Baseline after branch merges: 136 existing tests passed. Added 18 focused combined
cases covering success, date boundaries, exact hotel money/currency, provenance,
high-risk weather events, fully booked/spike scenarios, each provider failure,
invalid destination dates, JSON serialization and C1/TripAgent compatibility.

```bash
PYTHONDONTWRITEBYTECODE=1 /private/tmp/trippilot-c3-review-py312/bin/python -m pytest -q
/private/tmp/trippilot-c3-review-py312/bin/python -m compileall -q app.py agents services tools tests
```

Local Python 3.12.14 full suite: 154 passed, zero failed/skipped. Existing hotel and
weather test files remain byte-identical to their feature heads. Automated tests
perform no live Open-Meteo, Duffel or LLM requests; the flight HTTP transport is
stubbed and guarded, and no real credentials enter fixtures. This is tool-layer
validation, not evidence of real booking, autonomous orchestration or policy approval.

Tracked env.txt is retained without reading secret values. The inherited C3 ignore
rule does not remove tracked/history exposure. Owner must revoke/rotate exposed
credentials, inspect usage, untrack local secret configuration and coordinate any
history remediation. No credential action or shared history rewrite is performed.

Technical tool composition is ready for Person A's integration work. Overall delivery
remains CHANGES REQUIRED pending separate owner credential remediation; B2/B3 and
approval capabilities must remain explicitly unavailable until implemented/tested.
