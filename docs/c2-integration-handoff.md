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
