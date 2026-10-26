"""Deterministic, offline BM25 retrieval; no answers or policy decisions."""

from collections import Counter
from copy import deepcopy
import math
import re

from rag.document_loader import PolicyRetrievalError, load_policy

STOP_WORDS = frozenset("a an and are as at be by can do does for from how i in is it of on or the to was what when which who with would please policy rules rule".split())


def tokenize(text):
    # Preserve full policy IDs alongside constituent words; no external model.
    words = re.findall(r"[\w]+(?:-[\w]+)*", text.casefold())
    tokens = []
    for word in words:
        tokens.extend([word] + (word.split("-") if "-" in word else []))
    return [word for word in tokens if word not in STOP_WORDS]


class PolicyRetriever:
    """Index a single local baseline in memory, once per instance."""

    def __init__(self, document_path, expected_version="2.0"):
        self.document = load_policy(document_path, expected_version)
        self.counts = [Counter(tokenize(chunk["section"] + "\n" + chunk["text"]))
                       for chunk in self.document["chunks"]]
        self.lengths = [sum(count.values()) for count in self.counts]
        self.average_length = sum(self.lengths) / len(self.lengths) or 1
        self.frequencies = Counter(token for count in self.counts for token in count)

    def retrieve(self, query, top_k=5):
        if not isinstance(query, str) or not query.strip() or len(query) > 2000:
            raise PolicyRetrievalError("invalid_query", "Query must be non-empty text of at most 2000 characters.")
        if isinstance(top_k, bool) or not isinstance(top_k, int) or not 1 <= top_k <= 20:
            raise PolicyRetrievalError("invalid_top_k", "top_k must be an integer between 1 and 20.")
        tokens = set(tokenize(query))
        ranked = []
        total = len(self.counts)
        for index, count in enumerate(self.counts):
            score = 0.0
            for token in sorted(tokens):
                frequency = count[token]
                if frequency:
                    idf = math.log(1 + (total - self.frequencies[token] + 0.5) /
                                   (self.frequencies[token] + 0.5))
                    score += idf * frequency * 2.5 / (frequency + 1.5 *
                             (0.25 + 0.75 * self.lengths[index] / self.average_length))
            if score > 0:
                ranked.append((score, index))
        ranked.sort(key=lambda item: (-item[0], item[1]))
        matches = []
        for score, index in ranked[:top_k]:
            chunk = deepcopy(self.document["chunks"][index])
            chunk["score"] = round(score, 6)
            matches.append(chunk)
        return {"status": "success" if matches else "no_results", "query": query.strip(),
                "source": self.document["source"],
                "policy_version": self.document["policy_version"],
                "document_sha256": self.document["document_sha256"],
                "data_mode": "local_document", "retrieval_method": "bm25_lexical",
                "matches": matches, "requires_policy_evaluation": True}
