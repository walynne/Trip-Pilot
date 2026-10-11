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


## B2 Policy Retrieval (local Demo Baseline)

`PolicySearchTool` provides offline, synchronous policy evidence retrieval from an authorized local version 2.0 DOCX. It preserves paragraph/table references, section context and source provenance. This is the retrieval stage of RAG; it does not generate policy answers or make B3 compliance/approval decisions, and TripAgent remains unchanged.

```python
from tools.policy_search import PolicySearchTool

policy_tool = PolicySearchTool()
evidence = policy_tool.search_policy("Singapore hotel maximum nightly rate", top_k=5)
```

Place the approved DOCX at `policies/TripPilot_Corporate_Travel_Policy_v2.docx`, or supply `document_path` explicitly. The document and local evaluation artifacts are ignored by Git; publication requires authorization. No embedding model, API key or new dependency is required for B2. Missing sources fail explicitly without fabricated policy content.

Run `python -m pytest -q` using Python 3.12. Tests use synthetic fixtures and do not require the private DOCX or external services. See [B2 integration handoff](docs/b2-integration-handoff.md) for input/output/error contracts, evaluation instructions, source limitations and outstanding Person A/B3 integration work. The original project structure above includes planned components and should not be treated as proof of executable functionality.
