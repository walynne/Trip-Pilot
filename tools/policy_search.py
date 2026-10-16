"""B2 public tool: retrieve evidence without changing existing agent flows."""

from pathlib import Path

from rag.retriever import PolicyRetriever
from rag.document_loader import PolicyRetrievalError  # public error contract

DEFAULT_POLICY_DOCUMENT = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "TripPilot_Corporate_Travel_Policy_v2.docx"
)


class PolicySearchTool:
    def __init__(self, document_path=DEFAULT_POLICY_DOCUMENT,
                 expected_version="2.0"):
        self.retriever = PolicyRetriever(document_path, expected_version)

    def search_policy(self, query, top_k=5):
        return self.retriever.retrieve(query, top_k=top_k)
