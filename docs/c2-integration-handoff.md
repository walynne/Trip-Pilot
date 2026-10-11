# C2 Hotel Search — Person A / B handoff (Mock-first MVP)

## Boundary and consistency

- Follows C1/C3: synchronous Python `HotelSearchTool` in `tools/`, `search_hotels(...)` returns JSON-safe dict; no new agent framework, no extra service wrapper.
- **Only mock provider has been implemented.** No live hotel inventory, pricing, or reservation bookability is claimed. Do not connect to bookings or approvals as if quotes were real.
- All sample hotel identities, locations, prices, availability, preferred-supplier flags and taxes are synthetic. A realistic test fixture is not official policy evidence.
- No policy evaluation: B3 must use structured policy rules to evaluate these offer attributes.

## Usage

```python
from tools.hotel_search import HotelSearchTool, HotelError

hotels = HotelSearchTool(provider="mock").search_hotels(
    "Singapore, SG", "2030-11-15", "2030-11-18", guests=1, rooms=1
)
# Alternate repeatable scenarios: fully_booked, price_spike, provider_error
```

**Input contract:** location is a supported demo city and optional country qualifier; check-in inclusive / check-out exclusive strict local calendar dates; stay 1–30 nights; integer guests 1–32, rooms 1–8, mock occupancy <=4 guests per room.

**Output contract:** status (`success` or `no_results`), city/country, check-in/out, nights, guests, rooms, local currency, provider, `data_mode="mock"`, mock scenario, attribution, result count, `hotels` list and UTC retrieval time. Each hotel offers `hotel_id`, `name`, `location` (synthetic coordinates), `hotel_tier`, `preferred_supplier`, `amenities`, `cancellation_policy`, synthetic availability and pricing (`room_nightly_rate`, `subtotal`, `taxes`, `fees`, `total`, `currency`, `night_count`, `room_count`). Currency amount strings use two decimal places, based on `Decimal` arithmetic.

**Error contract:** input/configuration => `ValueError`; provider errors and unsupported mock cities => `HotelError(code, safe_message)` with `.code` of `provider_error` or `location_not_found`.

**Person A:** Call C2 only after destination city and local check-in/check-out are known. C1's IATA destination and departure date do not supply enough information. Attach hotels as an optional result without changing current flight response. Tool failures must be isolated.

**Person B:** Treat `preferred_supplier` as candidate metadata, not a policy compliance decision. Policy rules and approval thresholds come from B1/B3, not invented in C2; avoid comparing cross-currency prices until an FX policy/source is defined.

## Next step for real-provider support

Select a licensed hotel search provider with a documented availability and taxation contract; add a separate client adapter and contract tests under the *same* public `HotelSearchTool.search_hotels` interface. Preserve provenance and distinguish cached prices, estimates, quotes and confirmed bookability. Never invent hotel quotes from scraped search snippets.

## Run tests

From repository root after copying `tools/hotel_search.py`, `tests/test_hotel_search.py`:

```bash
python -m pytest -q tests/test_hotel_search.py
```

Integration into `TripAgent`, real API, FX conversion, policy checking, ranking and actual bookings are excluded from this starter deliverable.

## Pricing and provenance contract

- Night count is the difference between the two local calendar dates. Check-out
  is excluded, including leap days and year/DST transitions; no timestamps are inferred.
- Rates are per room per night. All rooms use the same sample rate; requested
  guests do not add per-person charges. The mock allows unused rooms if guests
  are fewer than rooms; it does not allocate guests or report real room inventory.
- `standard` uses fixed sample rates; `price_spike` multiplies each by exactly 1.50.
- Synthetic subtotal = rounded nightly rate × rooms × nights.
- Synthetic taxes = subtotal × 0.10, rounded to cents using ROUND_HALF_UP.
  Fees are 12.00 per room per stay, not per night. The demo tax base excludes fees.
- Total = subtotal + rounded taxes + fees. Every amount is a two-decimal string.
  The tool uses a private Decimal context (precision 28), independent of callers.
- Offer currencies match the response currency. These numbers are independent
  fixtures in SGD/HKD/GBP/USD, not converted quotes or FX-equivalent amounts.
- `fully_booked` returns `no_results` and an empty hotel list; this is simulated,
  not evidence about actual availability. `provider_error` raises `HotelError`.
- Retain the response envelope (`provider`, `data_mode`, scenario and attribution)
  when displaying or forwarding offers. Do not present synthetic rates as verified
  prices, synthetic taxes as official rates, or preferred-supplier fixtures as
  actual approved-supplier evidence. `taxes_are_simulated` is always true.
- Person B receives candidate attributes only. Corporate policy decisions must
  come from policy rules and their provenance; C2 emits no compliance/approval verdict.

## Optional Person A composition and failure isolation

```python
result = trip_agent.run(user_message)  # existing C1 response stays intact
try:
    result["hotels"] = HotelSearchTool().search_hotels(
        destination_city, local_check_in, local_check_out, guests=guests, rooms=rooms
    )
except (HotelError, ValueError) as exc:
    result["hotels"] = {
        "status": "unavailable", "provider": "mock", "data_mode": "mock",
        "error_code": exc.code if isinstance(exc, HotelError) else "invalid_input",
        "message": str(exc),
    }
```

This is a handoff example, not a change to TripAgent. C3 remains independently
callable and optional; neither tool needs the other to be merged. Actual Person A/B
application wiring and policy evaluation remain outstanding team integration work.

PR CI independently runs the full available suite on Python 3.12, with no API
credentials and without importing C3. Regression tests include pricing context,
invalid configuration, exact sample amounts, currency/provenance, calendar bounds,
C1 response compatibility and hotel-failure isolation. Only pytest, requests,
openai and python-dotenv are installed; the latter two support C1 import checks.
