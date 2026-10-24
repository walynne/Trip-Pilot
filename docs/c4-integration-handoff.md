# C4 Disruption Simulator MVP — Person A handoff

## Scope and API

```python
from tools.disruption_simulator import DisruptionSimulator, DisruptionSimulationError

simulator = DisruptionSimulator()
event = simulator.simulate("flight_cancelled", {
    "trip_id": "demo-trip",
    "flight": {
        "flight_id": "demo-flight",
        "origin": "HKG",
        "destination": "SIN",
        "departure_date": "2026-11-15",
    },
})
```

This synchronous tool simulates the four requested Build Plan scenarios. It does not monitor real trips, call a provider or LLM, book/change anything, evaluate corporate policy, update approvals or invoke another agent. Inputs describe a demo, not verified operational facts. The tool has no clock, random seed or persistent state; identical relevant inputs return identical event dictionaries across calls/instances.

## Event contract

All four scenarios return exactly these top-level keys:

```json
{
  "type": "FLIGHT_CANCELLED",
  "severity": "HIGH",
  "message": "Simulated flight cancellation.",
  "source": "disruption_simulator",
  "data_mode": "mock",
  "confirmed_disruption": false,
  "requires_replanning_assessment": true,
  "affected_trip": {
    "trip_id": "demo-trip",
    "flight": {
      "flight_id": "demo-flight",
      "origin": "HKG",
      "destination": "SIN",
      "departure_date": "2026-11-15"
    },
    "hotel": null,
    "meeting": null,
    "budget": null
  },
  "supporting_data": null
}
```

`affected_trip` always has `trip_id`, `flight`, `hotel`, `meeting`, `budget`; exactly the selected scenario component is populated. Its fields depend on the scenario described below. `supporting_data` is null except for hotel catalogue simulation. Values are JSON serializable without custom encoders. There is no synthetic current timestamp, booking confirmation, verified supplier status or approval/compliance verdict.

Uppercase `type`, `severity` and the string `message` match Monitoring's structural contract. HIGH and MEDIUM describe the demo scenario's assessment priority, not the assessed impact of an actual trip. All events require assessment but remain explicitly unconfirmed mocks.

## Input scenarios

Every context must be a dict with a non-empty `trip_id` string (1–200 characters) and the selected nested dict. Identifiers/text are trimmed. Extra fields and unrelated scenario objects are ignored, never executed, changed or echoed. The tool does not infer missing facts from other objects.

| Scenario | Event type / severity | Required nested fields |
| --- | --- | --- |
| `flight_cancelled` | `FLIGHT_CANCELLED` / `HIGH` | `flight`: `flight_id`, `origin`, `destination`, `departure_date` |
| `hotel_unavailable` | `HOTEL_UNAVAILABLE` / `HIGH` | `hotel`: `hotel_id`, `location`, `check_in`, `check_out`, `guests`, `rooms` |
| `meeting_time_changed` | `MEETING_TIME_CHANGED` / `MEDIUM` | `meeting`: `meeting_id`, `original_start`, `new_start` |
| `budget_reduced` | `BUDGET_REDUCED` / `MEDIUM` | `budget`: `currency`, `original_amount`, `new_amount` |

Flight airports must be distinct uppercase three-letter codes. Their format is checked, not their existence or the flight's real status. `departure_date` must be a YYYY-MM-DD calendar date for the specified origin-local departure; destination arrival dates are not inferred.

Hotel uses the existing C2 `HotelSearchTool(provider="mock", mock_scenario="fully_booked")`. It inherits C2 catalogue/location-country, date, stay-length and occupancy validation: currently Singapore, Hong Kong, London and New York; optionally supported country qualifiers; 1–30 nights with inclusive check-in/exclusive check-out; 1–32 guests, 1–8 rooms and at most four guests per room. Guests and rooms must be supplied explicitly, not defaulted from assumptions. The affected hotel metadata adds normalized city and night count. C2's city catalogue cannot verify the supplied hotel ID or establish actual property unavailability. Supporting data contain only `provider`, `data_mode`, `mock_scenario`, `status`, `result_count`; C2's wall-clock `retrieved_at` is deliberately excluded.

Meeting start values must be parseable ISO-8601 timestamps with explicit UTC offsets (or Z) and represent distinct instants. Earlier/later moves and date changes are allowed. Offsets distinguish repeated local times during DST; venue timezone rules and meeting duration are not inferred or validated. These are caller-provided intended meeting-local timestamps.

Budget amounts must be non-negative plain decimal **strings**, with at most 12 integer digits and two fractional digits. The original must be positive and the new amount strictly smaller; zero remaining budget is allowed. Floats, booleans, exponents, NaN/infinity and negative values are rejected. Output is normalized to two decimal places independently of caller Decimal settings. The currency is an explicit uppercase three-letter code; no ISO registry lookup, FX conversion, policy ceiling or approval decision is implied.

Additional examples:

```python
hotel_event = simulator.simulate("hotel_unavailable", {
    "trip_id": "demo-trip",
    "hotel": {"hotel_id": "demo-hotel", "location": "Singapore, SG",
              "check_in": "2026-11-15", "check_out": "2026-11-18",
              "guests": 1, "rooms": 1},
})
meeting_event = simulator.simulate("meeting_time_changed", {
    "trip_id": "demo-trip",
    "meeting": {"meeting_id": "demo-meeting",
                "original_start": "2026-11-16T09:00:00+08:00",
                "new_start": "2026-11-16T14:00:00+08:00"},
})
budget_event = simulator.simulate("budget_reduced", {
    "trip_id": "demo-trip",
    "budget": {"currency": "SGD", "original_amount": "2500.00", "new_amount": "1800.00"},
})
```

No weather-triggered scenario is requested here. C3 weather mocks stay independently available; C4 does not duplicate weather logic or invent a weather cause for a cancellation.

## Errors and failure isolation

Invalid input raises `DisruptionSimulationError`, a `ValueError` with safe `.code` and message. Codes: `unsupported_scenario`, `invalid_context`, `invalid_input`, `invalid_date`, `invalid_flight`, `invalid_hotel`, `invalid_time`, `invalid_budget`. C2 catalogue/validation failures are translated to `invalid_hotel`. No fallback fills missing IDs, dates, occupancy, meeting times, amounts or currency.

```python
try:
    event = simulator.simulate(scenario, context)
except DisruptionSimulationError as error:
    demo_error = {"code": error.code, "message": str(error)}
    # Person A keeps existing tool results and handles the demo-input error.
```

## Person A integration boundary

Person A owns an explicit, opt-in demo route/control that supplies context and consumes the event. No routes or agents were modified. Preserve `data_mode`, `source` and `confirmed_disruption` whenever presenting/forwarding the event. Real disruptions must come from separately verified operational sources; simulations must never be promoted to confirmed events.

**Do not blindly replace TripAgent's existing monitoring event with C4 output.** Current TripAgent invokes its replanner for HIGH/MEDIUM severity, and that replanner searches flights and uses an LLM. C4's uppercase compatibility does not make that path offline or constitute authorization to execute it. Person A must keep demos isolated or provide a separately reviewed assessment-only integration. No orchestration, HITL approval, automatic booking or corporate policy status change is implemented by C4.

## Validation and CI

Python 3.12.14 local environment. Tests use no real credentials. Full-suite imports on current main need Flask and langchain-openai in addition to the existing pytest/requests/openai/python-dotenv test dependencies. Importing app initializes the current LLM client; local full-suite validation uses explicitly synthetic configuration to avoid requiring a real account:

```bash
python -m pytest -q tests/test_disruption_simulator.py
NEXLLM_CHAT_MODEL=offline-test \
NEXLLM_API_KEY=offline-test-not-a-real-key \
NEXLLM_BASE_URL=https://example.invalid/v1 \
python -m pytest -q
python -m compileall -q app.py agents services tools rag scripts tests
```

Unmodified main `a66fbe6`: **231 passed, 0 failed, 0 skipped**. With C4: **80 targeted tests passed; 311 full-suite tests passed, 0 failed, 0 skipped**. Tests cover all scenarios, JSON-safe uniform keys, deterministic independent instances, caller mutation isolation, C2 reuse, bad/missing inputs, decimal precision, explicit offsets, blocked networking and execution without importing agents/LLMs/live providers.

Current main comments out full pytest execution in its workflow. This change adds an active, dedicated C4 test step using the existing lightweight dependencies; it does not silently treat syntax-only checks as test validation or enable credential-dependent app imports in CI. Full-suite local results and targeted hosted CI results must be reported separately. Restoring credential-free full-suite CI is a team integration follow-up, not a completed C4 feature.
