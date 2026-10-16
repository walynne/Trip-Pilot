# B3 — Policy evaluation handoff

## Scope

B3 decides whether one proposed itinerary option complies with the local Demo Baseline (policy version 2.0). It uses B2 evidence from PolicySearchTool. It does not search flights or hotels, book travel, or grant approval.

A BM25 success or a high score is not a compliance verdict.

## How Person A calls it

Run from the repository root after one flight and one hotel exist.

    from agents.policy_agent import PolicyAgent, PolicyEvaluationError

    agent = PolicyAgent(
        document_path="policies/TripPilot_Corporate_Travel_Policy_v2.docx",
        expected_version="2.0",
    )

    try:
        verdict = agent.evaluate({
            "traveler_role": "manager",
            "city": "Singapore",
            "city_tier": 1,
            "flight": {"cabin": "economy", "duration_hours": 4.0},
            "hotel": {"nightly_rate_usd": 280, "currency": "USD"},
            "meals_usd": 70,
            "total_cost_usd": 2400,
        })
    except PolicyEvaluationError as error:
        verdict = {
            "status": "error",
            "error": {"code": error.code, "message": str(error)},
        }

Initialize once. If B3 returns error, keep the flight, hotel, and weather results. Do not invent a compliant itinerary.

## Input

Money is USD. null means unknown. Do not fill defaults before calling.

| Field | Required | Notes |
|---|---|---|
| traveler_role | no | manager, director, ceo, or null |
| city | no | Used only to build the B2 query |
| city_tier | no | 1, 2, or 3. B3 will not infer the tier from the city name |
| flight.cabin | no | economy, premium_economy, business |
| flight.duration_hours | no | End-to-end hours |
| hotel.nightly_rate_usd | no | Number |
| hotel.currency | no | If present and not USD, B3 returns needs_facts |
| meals_usd | no | Daily meals and incidentals |
| total_cost_usd | no | Whole-trip estimate |

preferred_supplier and hotel_tier from the hotel tool are mock metadata. B3 ignores them. They are not a SUPPLIER-01 pass.

## Output

    status: compliant | non_compliant | needs_facts | escalate | error
    violated_rules: ["HOTEL-RATE-T1", ...]
    missing_facts: ["city_tier", ...]
    required_approver: line_manager | department_head | director | cfo_ceo | null
    explanation: one short paragraph citing policy IDs
    policy_version: "2.0"
    document_sha256: hash of the loaded DOCX
    evidence: B2 matches actually used (chunk_id, section, references)
    approved: never present

| Status | Meaning |
|---|---|
| compliant | Checked fields are inside the hard limits. required_approver is who must still sign. This is not approval and not a booking. |
| non_compliant | At least one hard rule failed. violated_rules lists policy IDs. |
| needs_facts | A required input was missing or not in USD, so no verdict was made. |
| escalate | The policy text is ambiguous for this case. A human must choose. |
| error | The DOCX could not be read or B2 failed. No verdict. |

## Rules B3 applies

| ID | Rule |
|---|---|
| FLIGHT-CABIN-01 | Under 6 hours: Economy only |
| FLIGHT-CABIN-02 | Over 6 hours: Premium Economy is the default. Business only for director or ceo, and it still needs approval |
| HOTEL-RATE-T1 | Tier 1 hotel max USD 300 / night |
| HOTEL-RATE-T2 | Tier 2 hotel max USD 200 / night |
| HOTEL-RATE-T3 | Tier 3 hotel max USD 150 / night |
| MEAL-T1 / T2 / T3 | Meals and incidentals max USD 80 / 60 / 40 |
| APPROVAL-01 | Total under USD 1,000, line manager |
| APPROVAL-02 | USD 1,000 up to but not including 3,000, department head |
| APPROVAL-03 | USD 3,000 up to but not including 10,000, director |
| APPROVAL-04 | Above USD 10,000, CFO / CEO |

The approver is only reported. B3 never sets an approval flag.

## Cases that must not be guessed

Return escalate instead of compliant or non_compliant when:

- flight duration is exactly 6.0 hours
- total cost is exactly 1000, 3000, or 10000

Return needs_facts when:

- a hotel rate is present and city_tier is missing
- a cabin is present and duration_hours is missing
- the cabin is business and traveler_role is missing
- hotel.currency is present and is not USD

Supplier names in the policy are placeholders. Do not pass or fail SUPPLIER-01.

## What Person A must not do

- Do not book because status is compliant.
- Do not drop flight, hotel, or weather results when status is error.
- Do not log full evidence text. It is policy content.
- Do not call B3 before there is one concrete option. B3 evaluates a proposal. It does not search flights.
