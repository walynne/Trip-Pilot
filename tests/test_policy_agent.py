from agents.policy_agent import PolicyAgent
from rag.document_loader import PolicyRetrievalError


class FakeSearch:
    def search_policy(self, query, top_k=5):
        return {
            "policy_version": "2.0",
            "document_sha256": "abc",
            "matches": [{"chunk_id": "chunk-0001", "section": "3. Hotel",
                         "text": "Tier 1 hotel rates must not exceed USD 300 per night.",
                         "references": []}],
        }


class BrokenSearch:
    def search_policy(self, query, top_k=5):
        raise PolicyRetrievalError("source_not_found", "missing")


class FakeLLM:
    def __init__(self, response="Narrative explanation"):
        self.response = response
        self.system_prompt = None
        self.user_prompt = None

    def chat(self, system_prompt, user_prompt):
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def agent():
    return PolicyAgent(search_tool=FakeSearch())


def test_compliant_manager_short_economy():
    result = agent().evaluate({
        "traveler_role": "manager", "city": "Singapore", "city_tier": 1,
        "flight": {"cabin": "economy", "duration_hours": 4},
        "hotel": {"nightly_rate_usd": 280, "currency": "USD"},
        "meals_usd": 70, "total_cost_usd": 2400,
    })
    assert result["status"] == "compliant"
    assert result["required_approver"] == "department_head"
    assert "approved" not in result


def test_business_on_short_flight():
    result = agent().evaluate({
        "traveler_role": "manager", "city_tier": 1,
        "flight": {"cabin": "business", "duration_hours": 5.5},
        "hotel": {"nightly_rate_usd": 200, "currency": "USD"},
        "total_cost_usd": 2400,
    })
    assert result["status"] == "non_compliant"
    assert "FLIGHT-CABIN-01" in result["violated_rules"]


def test_hotel_over_tier_cap():
    result = agent().evaluate({
        "city_tier": 1,
        "hotel": {"nightly_rate_usd": 380, "currency": "USD"},
    })
    assert result["violated_rules"] == ["HOTEL-RATE-T1"]
    assert "USD 300" in result["explanation"]
    assert "HOTEL-RATE-T1" in result["explanation"]


def test_missing_tier():
    result = agent().evaluate({"hotel": {"nightly_rate_usd": 200, "currency": "USD"}})
    assert result["status"] == "needs_facts"
    assert "city_tier" in result["missing_facts"]


def test_meal_amount_requires_city_tier():
    result = agent().evaluate({"meals_usd": 50})
    assert result["status"] == "needs_facts"
    assert "city_tier" in result["missing_facts"]


def test_exact_six_hours_escalates():
    result = agent().evaluate({
        "traveler_role": "manager", "city_tier": 1,
        "flight": {"cabin": "economy", "duration_hours": 6},
        "hotel": {"nightly_rate_usd": 200, "currency": "USD"},
        "total_cost_usd": 500,
    })
    assert result["status"] == "escalate"


def test_non_usd_needs_facts():
    result = agent().evaluate({
        "city_tier": 1,
        "hotel": {"nightly_rate_usd": 200, "currency": "HKD"},
    })
    assert result["status"] == "needs_facts"


def test_retrieval_error():
    result = PolicyAgent(search_tool=BrokenSearch()).evaluate({"city_tier": 1})
    assert result["status"] == "error"
    assert result["error"]["code"] == "source_not_found"


def test_llm_explains_but_does_not_change_policy_decision():
    llm = FakeLLM("Tier 1 hotel rate exceeds the policy limit.")
    result = PolicyAgent(search_tool=FakeSearch(), llm=llm).evaluate({
        "city_tier": 1,
        "hotel": {"nightly_rate_usd": 380, "currency": "USD"},
    })

    assert result["status"] == "non_compliant"
    assert result["violated_rules"] == ["HOTEL-RATE-T1"]
    assert result["explanation"] == "Tier 1 hotel rate exceeds the policy limit."
    assert "Tier 1 hotel rates must not exceed USD 300" in llm.user_prompt
    assert "Do not change or reinterpret" in llm.system_prompt


def test_llm_failure_keeps_deterministic_explanation():
    llm = FakeLLM(RuntimeError("model unavailable"))
    result = PolicyAgent(search_tool=FakeSearch(), llm=llm).evaluate({
        "city_tier": 1,
        "hotel": {"nightly_rate_usd": 380, "currency": "USD"},
    })

    assert result["status"] == "non_compliant"
    assert result["violated_rules"] == ["HOTEL-RATE-T1"]
    assert "HOTEL-RATE-T1" in result["explanation"]
    assert "USD 300" in result["explanation"]
