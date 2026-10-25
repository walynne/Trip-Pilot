"""B3 policy evaluation. Evidence comes from B2. No booking and no approval."""

import json

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from tools.policy_search import DEFAULT_POLICY_DOCUMENT, PolicySearchTool
from rag.document_loader import PolicyRetrievalError


class PolicyEvaluationError(ValueError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


HOTEL_CAP = {1: 300, 2: 200, 3: 150}
MEAL_CAP = {1: 80, 2: 60, 3: 40}


class PolicyAgent:
    def __init__(self, document_path=DEFAULT_POLICY_DOCUMENT,
                 expected_version="2.0", search_tool=None, llm=None):
        self.search_tool = search_tool or PolicySearchTool(document_path, expected_version)
        self.llm = llm
        self.chain = self._build_chain() if llm else None

    def _build_chain(self):
        """Build a LangChain chain for policy explanations."""
        if not self.llm:
            return None

        llm_model = self.llm.model if hasattr(self.llm, 'model') else None
        if llm_model is None:
            return None

        try:
            prompt = ChatPromptTemplate.from_messages([
                ("system", """You write concise explanations for a policy evaluation that has already been decided.
Do not change or reinterpret the supplied status, rule IDs, missing facts, or approver.
Use only the supplied decision fields and policy evidence. Never say the trip is approved
or booked. Return one short plain-text paragraph. If the evidence is insufficient, use
the fallback explanation exactly."""),
                ("human", "{decision_context}")
            ])

            chain = prompt | llm_model | StrOutputParser()
            return chain
        except (TypeError, AttributeError):
            return None

    def evaluate(self, proposal):
        if not isinstance(proposal, dict):
            raise PolicyEvaluationError("invalid_proposal", "Proposal must be a dict.")
        try:
            evidence = self.search_tool.search_policy(self._query(proposal), top_k=5)
        except PolicyRetrievalError as error:
            return self._error(error.code, str(error))

        missing = []
        violations = []
        escalate = []
        flight = proposal.get("flight") or {}
        hotel = proposal.get("hotel") or {}
        tier = proposal.get("city_tier")
        role = proposal.get("traveler_role")
        cabin = flight.get("cabin")
        hours = flight.get("duration_hours")
        rate = hotel.get("nightly_rate_usd")
        meals = proposal.get("meals_usd")
        total = proposal.get("total_cost_usd")
        currency = hotel.get("currency")

        if currency and str(currency).upper() != "USD":
            missing.append("hotel.currency_usd")
        if (rate is not None or meals is not None) and tier is None:
            missing.append("city_tier")
        if cabin and hours is None:
            missing.append("flight.duration_hours")
        if cabin == "business" and role is None:
            missing.append("traveler_role")
        if missing:
            return self._result("needs_facts", [], missing, None, evidence)

        if hours == 6 or total in (1000, 3000, 10000):
            escalate.append("boundary")
        if cabin and hours is not None and hours != 6:
            if hours < 6 and cabin != "economy":
                violations.append("FLIGHT-CABIN-01")
            elif hours > 6 and cabin == "business" and role == "manager":
                violations.append("FLIGHT-CABIN-02")
        if rate is not None and tier in HOTEL_CAP and rate > HOTEL_CAP[tier]:
            violations.append(f"HOTEL-RATE-T{tier}")
        if meals is not None and tier in MEAL_CAP and meals > MEAL_CAP[tier]:
            violations.append(f"MEAL-T{tier}")

        if escalate and not violations:
            return self._result("escalate", [], [], None, evidence)
        approver = self._approver(total)
        status = "non_compliant" if violations else "compliant"
        return self._result(status, violations, [], approver, evidence)

    def _query(self, proposal):
        city = proposal.get("city") or ""
        tier = proposal.get("city_tier") or ""
        return f"{city} tier {tier} cabin hotel nightly rate meals approval".strip()

    def _approver(self, total):
        if total is None or total in (1000, 3000, 10000):
            return None
        if total < 1000:
            return "line_manager"
        if total < 3000:
            return "department_head"
        if total < 10000:
            return "director"
        return "cfo_ceo"

    def _error(self, code, message):
        return {"status": "error", "violated_rules": [], "missing_facts": [],
                "required_approver": None, "explanation": message,
                "evidence": [], "error": {"code": code, "message": message}}

    def _result(self, status, violations, missing, approver, evidence):
        if status == "needs_facts":
            text = "Missing facts: " + ", ".join(missing)
        elif status == "escalate":
            text = "A boundary in the policy is ambiguous. A human must decide."
        elif status == "non_compliant":
            text = "Violates " + ", ".join(violations)
        else:
            text = f"Checked fields are within the hard limits. Required approver: {approver}."
        result = {
            "status": status,
            "violated_rules": violations,
            "missing_facts": missing,
            "required_approver": approver,
            "explanation": text,
            "policy_version": evidence.get("policy_version"),
            "document_sha256": evidence.get("document_sha256"),
            "evidence": [
                {"chunk_id": m["chunk_id"], "section": m["section"], "references": m["references"]}
                for m in evidence.get("matches", [])
            ],
        }
        self._add_llm_explanation(result, evidence)
        return result

    def _add_llm_explanation(self, result, evidence):
        matches = evidence.get("matches", [])
        if self.llm is None or not matches:
            return

        decision_context = {
            "status": result["status"],
            "violated_rules": result["violated_rules"],
            "missing_facts": result["missing_facts"],
            "required_approver": result["required_approver"],
            "fallback_explanation": result["explanation"],
            "policy_evidence": [
                {
                    "section": match.get("section"),
                    "text": match.get("text"),
                    "context": match.get("context", []),
                    "references": match.get("references", []),
                }
                for match in matches
            ],
        }
        try:
            if self.chain is not None:
                explanation = self.chain.invoke({
                    "decision_context": json.dumps(decision_context, default=str)
                })
            else:
                explanation = self.llm.chat(
                    """You write concise explanations for a policy evaluation that has already been decided.
Do not change or reinterpret the supplied status, rule IDs, missing facts, or approver.
Use only the supplied decision fields and policy evidence. Never say the trip is approved
or booked. Return one short plain-text paragraph. If the evidence is insufficient, use
the fallback explanation exactly.""",
                    json.dumps(decision_context, default=str),
                )
            if isinstance(explanation, str) and explanation.strip():
                result["explanation"] = explanation.strip()
        except Exception:
            pass
