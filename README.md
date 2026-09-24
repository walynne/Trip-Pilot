# Trip-Pilot

TripPilot is an agentic AI corporate travel planner that autonomously creates, manages and adapts business trip itineraries while ensuring compliance with corporate policies and budget constraints. 

Quick start on Windows, in this folder:

    py -m venv .venv
    .venv\Scripts\python -m pip install -r requirements.txt

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
