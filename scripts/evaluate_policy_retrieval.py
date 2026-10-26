"""Evaluate locally authored relevance judgments without printing policy text.

Run from the repository root with python -m scripts.evaluate_policy_retrieval.
Cases and baseline remain local. No external API or model is used.
"""

import argparse
import json
from pathlib import Path

from tools.policy_search import PolicySearchTool


def evaluate(tool, cases, top_k=5):
    """Each case requires all expected anchors, or an explicit no-results check.

    Anchors are {body_block, optional row}. Check returned evidence AND context.
    A pass means evidence was retrieved, not that a policy answer is correct.
    """
    if not isinstance(cases, list) or not cases:
        raise ValueError("Evaluation requires a non-empty case list.")
    outcomes = []
    for case in cases:
        if not isinstance(case, dict) or not isinstance(case.get("query"), str):
            raise ValueError("Each evaluation case requires a text query.")
        expected = case.get("expected", [])
        if not isinstance(expected, list) or (not expected and case.get("no_results") is not True):
            raise ValueError("Specify expected source anchors or no_results=true.")
        for anchor in expected:
            if not isinstance(anchor, dict) or not anchor or "body_block" not in anchor:
                raise ValueError("Expected anchors require a body_block.")
            if not set(anchor) <= {"body_block", "row"} or any(
                    isinstance(value, bool) or not isinstance(value, int) or value < 1
                    for value in anchor.values()):
                raise ValueError("Expected anchors require positive integer coordinates.")
        if expected and case.get("no_results"):
            raise ValueError("A case cannot require evidence and no results.")
        result = tool.search_policy(case["query"], top_k)
        references = [reference for match in result["matches"]
                      for evidence in [match] + match["context"]
                      for reference in evidence["references"]]
        hits = sum(any(all(ref.get(key) == value for key, value in anchor.items())
                       for ref in references) for anchor in expected)
        passed = (not result["matches"] if case.get("no_results") is True
                  else hits == len(expected))
        outcomes.append({"case": len(outcomes) + 1, "passed": passed,
                         "expected_anchors": len(expected), "retrieved_anchors": hits})
    return {"cases": len(outcomes), "passed": sum(item["passed"] for item in outcomes),
            "failed": sum(not item["passed"] for item in outcomes), "top_k": top_k,
            "policy_version": tool.retriever.document["policy_version"],
            "document_sha256": tool.retriever.document["document_sha256"],
            "outcomes": outcomes}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--document", required=True)
    parser.add_argument("--cases", required=True)
    parser.add_argument("--version", default="2.0")
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()
    suite = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    tool = PolicySearchTool(args.document, expected_version=args.version)
    if not isinstance(suite, dict) or suite.get("document_sha256") != tool.retriever.document["document_sha256"]:
        raise ValueError("Evaluation judgments must be pinned to this document SHA-256.")
    report = evaluate(tool, suite.get("cases"), args.top_k)
    print(json.dumps(report, indent=2))
    return 1 if report["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
