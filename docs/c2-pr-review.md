# PR #5 C2 hotel integration review

## Baseline and scope

Reviewed `a687902f6f531c3fd8186aa34974c94c0403fa50` on
`feature/c2-hotel-integration` against freshly fetched main `6025095`.
PR #5 was OPEN/MERGEABLE, 1 ahead / 0 behind, with no CI checks.
Inspected all three original C2 files and actual main C1 code (flight tool/client,
FlightService, TripAgent, app.py), plus C3 client/tool from its remote feature ref.
C3 is not merged or required by this branch. No branch switch or main merge needed.

Initial untracked `README_C2_DELIVERY.md` and `docs/team-handoff.md` were retained
byte-for-byte and excluded from the commit. Tracked env.txt was also retained
byte-for-byte. C1, B1, C3, TripAgent and unrelated modules remain unmodified.

C2 is one synchronous class backed by static synthetic fixtures. A transport
client/service wrapper would be redundant without a real provider. It imports no
network library or agent framework and preserves:
`HotelSearchTool.search_hotels(location, check_in, check_out, guests=1, rooms=1)`.

## Findings

Locations identify the reviewed original revision unless explicitly current.

| Priority/status | Location | Impact | Remediation |
| --- | --- | --- | --- |
| P1 fixed | tools/hotel_search.py:122-129 (original); :122 (current) | Decimal operations inherited caller precision/rounding/traps. A valid 30-night, 8-room request raised InvalidOperation under precision 4, breaking deterministic pricing and safe integration into financial/policy workflows. | Use private precision-28 ROUND_HALF_UP context for all pricing/formatting; regression tests verify exact totals and unchanged caller context under low precision and enabled rounding traps. |
| P1 fixed | tools/hotel_search.py:95 | Unhashable scenario values such as [] raised TypeError instead of documented ValueError, escaping expected configuration failure handling. | Require a string before set membership; focused tests cover list, dict, None, number and bool. |
| P1 owner action outstanding, pre-existing | env.txt:13; .gitignore:30 | Tracked credential-shaped value remains in shared history; env.txt is not ignored on this branch/main. Validity/rotation were not checked. | Owner must revoke/rotate actual credentials, inspect usage, untrack local credential config and assess historical exposure. No credential or ignore configuration was altered by C2 review. |
| P2 integration safeguard | tools/hotel_search.py:139,153,168-174 (original); docs/c2-integration-handoff.md:25-29 | Individual hotel rows are synthetic; consumers stripping the envelope could lose explicit mock pricing provenance or mistake preferred_supplier for verified approval evidence. | Handoff now requires retaining provider/data_mode/scenario/attribution and treating flags as fictional candidate metadata. C2 emits no compliance verdict. Per-offer provenance duplication may be considered later; no P2 code changes added. |
| P2 team coordination | .github/workflows/python-tests.yml:1 | C2 and unmerged C3 both add this workflow path; their content differs, so the second PR may need branch synchronization/resolution after the first merges. | Resolve that overlap in the later PR, retaining full-suite tests. Do not merge C3 just to obtain C2 CI. |

No P0 finding. No P3 enhancement is necessary for this mock-first MVP.

## Contract assessment

- Dates are strict local calendar dates with [check_in, check_out) nights, 1–30.
  Leap-day, year boundaries and max stay are tested; no timezone timestamps inferred.
- Integer guests 1–32, rooms 1–8; booleans/floats rejected; ceiling 4 guests/room.
  Unused rooms are allowed; there is no actual room/guest allocation.
- Per-room/night sample rate is rounded to cents; subtotal multiplies rooms/nights.
  Fictional tax is 10% of subtotal, rounded HALF_UP; fictional fee is 12.00 per
  room/stay, excluded from tax base. Total is subtotal + taxes + fees.
- Currency is consistent at envelope and pricing levels. City currencies contain
  independent fixtures, not FX-converted or verified quotes.
- Supported countries/qualifiers are explicitly restricted to the four-city mock
  catalogue; mismatched qualifiers fail safely. No geocoding/API lookup occurs.
- standard, fully_booked, price_spike and provider_error are explicit simulations.
  Successes carry provider/data_mode=mock, attribution, synthetic coordinates,
  simulated availability, no booking URL and taxes_are_simulated=true.
- Same inputs/scenario produce identical payloads except UTC retrieval time.
  JSON serialization, sorting, exact spike amounts and currency consistency are tested.
- No policy_compliant/approval_required verdicts are emitted. Person B must use
  authoritative policy rules; synthetic supplier flags are not approved-supplier evidence.
- Person A can optionally compose results after C1, catch ValueError/HotelError,
  and preserve flight response fields. The documented failure-isolation example is
  regression tested. Actual A/B app wiring is still outstanding; no TripAgent edits.

## Validation

macOS arm64; isolated Python 3.12.14 environment with pytest 9.1.1,
requests 2.32.5, openai 3.28.0, python-dotenv 1.1.1. No live credentials used.

Baseline: **41 passed in 0.21s**. After review fixes/tests: **58 passed in 0.51s**,
zero failed/skipped. Full available suite (C3 tests are absent on this branch):

```bash
PYTHONDONTWRITEBYTECODE=1 /private/tmp/trippilot-c3-review-py312/bin/python -m pytest -q
/private/tmp/trippilot-c3-review-py312/bin/python -m compileall -q app.py agents services tools tests
```

compileall, five imports (hotel tool, flight tool/client, FlightService, TripAgent)
and `git diff --check` passed. Imports did not instantiate live API clients.
The two C1 regression/failure-isolation tests use mocked collaborators and HTTP.
Hotel tests prohibit requests.get/post; C2 itself contains no network path.

## CI and delivery

No workflow existed on main/C2, explaining the absent checks. Added independently
`.github/workflows/python-tests.yml`: pull_request trigger, Python 3.12, four
required test/import dependencies, compileall and full pytest; read-only permissions,
no secrets, no persisted checkout credentials, ten-minute timeout. C3 was not copied,
merged or required. Remote CI outcome is reported after publication in the delivery
report; local validation alone is not claimed as remote CI success.

Only hotel tool, its tests/handoff, this report and the independent workflow are
part of review changes. No force push, self-approval or PR merge is performed.

**CHANGES REQUIRED** pending separate owner-confirmed credential remediation.
C2 code corrections are complete and suitable for team review; actual A/B integration
and any later workflow synchronization remain team tasks. This is a mock-first
course-project MVP, not a production hotel search or compliance platform.
