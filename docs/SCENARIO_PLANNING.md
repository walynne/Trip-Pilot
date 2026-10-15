Scenario planning
Summary

This document lists realistic trip scenarios and test cases to validate the agent’s behavior against policy, approvals, and operational failures. Each item shows the test action and the expected agent behavior in simple language.
Purpose

Provide a single place for operational stress tests, policy compliance tests, governance tests, and evaluation metrics so the team can run reproducible checks and present results.
Template (how to record a scenario)

Title:
Category:
Date:
Owner:
Description (short plain English):
Preconditions (what must be true before testing):
Test Action (what to simulate or input):
Expected Agent Behavior (clear pass/fail criteria):
Policy IDs / Rules referenced:
Notes / Links (issues, dashboards, PRs):
Category 1: Disruption & Re-planning Scenarios (Operational Stress Tests) These simulate real-world chaos mid-trip and check the agent still follows company rules.

Scenario 1 – Flight Cancellation

Title: Flight Cancellation (auto re-plan)
Category: Disruption & Re-planning
Owner: @owner-handle
Description: Simulate a supplier update showing a confirmed flight cancellation for a booked flight.
Preconditions: Itinerary with a confirmed flight exists.
Test Action: Inject a supplier status update indicating the flight is cancelled.
Expected Agent Behavior:
Detect the cancellation automatically.
Propose at least two alternative flights that comply with policy and preserve the business purpose.
Flag any alternative that breaches cabin-class rules (FLIGHT-CABIN-01 / 02).
If viable options exceed cost caps or no compliant options exist, escalate for human review.
Policy IDs: FLIGHT-CABIN-01, FLIGHT-CABIN-02
Notes: Ensure alternatives show costs and approval routing if required.
Scenario 2 – Hotel Unavailable

Title: Hotel Unavailable (rebook to compliant hotel)
Category: Disruption & Re-planning
Owner: @owner-handle
Description: Primary hotel becomes sold-out or marked unsafe during the trip.
Preconditions: Booked hotel in itinerary.
Test Action: Mark primary hotel as unavailable/sold out or unsafe.
Expected Agent Behavior:
Select a safe alternative near the work location.
Enforce city-tier rate caps:
Tier 1: USD 300/night
Tier 2: USD 200/night
Tier 3: USD 150/night
Prioritize preferred suppliers when possible.
If no compliant hotel is available within the cap, escalate.
Policy IDs: HOTEL-RATE-T1, HOTEL-RATE-T2, HOTEL-RATE-T3
Notes: Confirm distance to work location and supplier preference logic.
Scenario 3 – Mid-trip Budget Reduction

Title: Mid-trip Budget Reduction (re-plan to new budget)
Category: Disruption & Re-planning
Owner: @owner-handle
Description: A corporate budget cut is applied while the traveler is mid-trip.
Preconditions: Active itinerary with remaining nights/meals.
Test Action: Inject a new lower budget limit for the trip.
Expected Agent Behavior:
Re-plan remaining nights and meal allowances to fit the new budget while preserving the trip’s core business purpose.
If compliance is impossible under the new budget, flag for a formal policy exception and escalate.
Policy IDs: BUDGET-ADJUST, APPROVAL-EXCEPTION
Notes: Preserve activities essential to the business purpose when reducing spend.
Scenario 4 – Meeting Time Change

Title: Meeting Time Change (cascade impact analysis)
Category: Disruption & Re-planning
Owner: @owner-handle
Description: A confirmed client meeting is moved by several hours.
Preconditions: Itinerary with flight, hotel, and ground transport tied to meeting time.
Test Action: Shift the confirmed meeting time earlier or later by 4 hours.
Expected Agent Behavior:
Assess impacts across flights, hotels, and ground transport.
Alter only bookings necessary to meet the new meeting time.
Route any material cost increases or cabin changes for re-approval.
Policy IDs: SCHEDULE-CHANGE, APPROVAL-ROUTING
Notes: Keep changes minimal and document trade-offs.
Category 2: Baseline Compliance & Non-Compliance Validation (Rule-Checking Tests) These test the agent’s rule-checking accuracy against the policy rulebook.

Test Case A — Fully Compliant Itinerary

Title: Manager trip — compliant (Singapore, Tier 1)
Category: Baseline Compliance
Owner: @owner-handle
Input Data:
Manager-level traveler
3-night client meeting in Singapore (Tier 1)
Economy flight under 6 hours
Hotel USD 280/night
Daily meals under USD 80
Test Action: Submit itinerary to the agent for validation and routing.
Expected Agent Behavior:
Validate 100% compliance across rules (FLIGHT-CABIN-01, HOTEL-RATE-T1, MEAL-T1).
Calculate total cost (example: USD 2,400) and route to Department Head approval (APPROVAL-02).
No false violation alerts.
Policy IDs: FLIGHT-CABIN-01, HOTEL-RATE-T1, MEAL-T1, APPROVAL-02
Notes: Confirm cost calculation matches itemized costs.
Test Case B — Non-Compliant Itinerary Rejection

Title: Manager trip — non-compliant (London)
Category: Baseline Compliance
Owner: @owner-handle
Input Data:
Manager-level traveler
4-night conference in London (Tier 1)
Business Class ticket on 5-hour sector
Hotel USD 380/night
Test Action: Submit itinerary to the agent for validation and booking.
Expected Agent Behavior:
Immediately detect violations:
Business Class on flight under 6 hours → FLIGHT-CABIN-01
Hotel USD 380/night → HOTEL-RATE-T1 cap exceeded
Reject automated booking and generate a clear escalation notice citing the exact Policy IDs and reasons.
Policy IDs: FLIGHT-CABIN-01, HOTEL-RATE-T1
Notes: Verify the escalation content includes rule IDs and suggested next steps.
Category 3: Human-in-the-Loop Approval & Governance Tests These verify approval routing and safeguards.

Approval Threshold Routing Test

Title: Approval routing by total cost
Category: Human-in-the-Loop
Owner: @owner-handle
Test Action: Submit itineraries at different total price points.
Expected Agent Behavior:
Route approvals according to thresholds:
< USD 1,000 → Line Manager
USD 1,000–3,000 → Department Head
USD 3,000–10,000 → Director
USD 10,000 → CFO/CEO + finance review

Include routing metadata and approver contact in the workflow.
Policy IDs: APPROVAL-THRESHOLDS
Notes: Check audit trail includes each routing decision.
Self-Approval & Expense Splitting Prevention Test

Title: Prevent self-approval & split invoices
Category: Human-in-the-Loop
Owner: @owner-handle
Test Action: Attempt to:
Self-approve a travel request as the requester.
Split a large trip into multiple smaller invoices to bypass thresholds.
Expected Agent Behavior:
Block self-approval attempts based on rule GENERAL-01.
Detect attempts to artificially split expenses and block or escalate per GENERAL-01.
Policy IDs: GENERAL-01
Notes: Ensure evidence is logged (who attempted, timestamps, blocked actions).
Category 4: Evaluation Framework & KPIs (Dashboard Metrics) Metrics to measure system performance and present in slides.

Policy Compliance Rate

Definition: % of agent-recommended options that fully comply with city tiers, budgets, and cabin rules without unauthorized overrides.
How to measure: (Compliant recommendations) / (Total recommendations) over a time period.
Cost Efficiency & Savings

Definition: Financial savings of agent-optimized bookings vs. unguided consumer alternatives.
How to measure: Compare booked option cost to market baseline for same time window.
Re-planning Latency

Definition: Time from disruption detection to delivery of ranked, compliant alternatives.
How to measure: Timestamp of disruption event → timestamp of final recommended options.
Audit Trail Integrity

Definition: % of recommendations, policy checks, overrides, and approvals recorded in immutable logs.
How to measure: Verify each transaction has a corresponding log entry with required metadata.
How to use this file

Add new scenarios by copying the Template block at the top and filling in fields.
Use the Policy IDs field to map tests to the rulebook and to make automated checks easier.
When running tests, capture input data, agent output, timestamps, and any approval records for auditing.
Change log

2026-10-15 — Initial integrated scenarios and KPI definitions (owner: @rasonleekw).
