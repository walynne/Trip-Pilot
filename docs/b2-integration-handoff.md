# B2 — Local policy retrieval handoff

## Implemented scope

B2 loads the local, user-approved Demo Baseline `policies/TripPilot_Corporate_Travel_Policy_v2.docx` (version 2.0), builds an in-memory lexical BM25 index and retrieves source evidence. It does not generate answers, classify a trip as compliant, calculate policy eligibility, approve an exception or execute a booking. B3 and TripAgent integration are separate work owned by the team.

The existing `agents/policy_agent.py` is empty on this branch. A directory shown in the original README is not evidence that its functionality exists. No operational B3 evaluator, RAG-to-TripAgent invocation or approval flow is established by B2.

## Person A invocation

Run from the repository root, or pass an explicit local path:

```python
from tools.policy_search import PolicySearchTool, PolicyRetrievalError

policy_tool = PolicySearchTool(
    document_path="policies/TripPilot_Corporate_Travel_Policy_v2.docx",
    expected_version="2.0",
)

# Person A should add this optional call in their own integration change.
# Keep independently obtained flight/hotel/weather results on B2 failure.
try:
    policy_evidence = policy_tool.search_policy(
        "Singapore hotel maximum nightly rate", top_k=5
    )
except PolicyRetrievalError as error:
    policy_evidence = {
        "status": "error",
        "error": {"code": error.code, "message": str(error)},
    }
```

Initialize once per local baseline snapshot. Initialization can fail as well as retrieval; catch the same error around initialization in an orchestrator. The constructor reads only a local DOCX. It does not call an LLM, embedding server, vector database or external API. Loading a different file does not certify that file as an approved policy. Person A must control which source is authorized.

## Input contract

- `document_path`: non-empty string or `pathlib.Path` to a local `.docx`; default path is relative to the process working directory.
- `expected_version`: version string, default `2.0`; exactly one version metadata row must match it.
- `query`: non-empty string, at most 2,000 characters. Use concrete policy terms, city names and policy identifiers. English lexical retrieval does not promise semantic paraphrase matching.
- `top_k`: integer 1–20, default 5; booleans are rejected.

## Output contract

Every successful call returns a JSON-serializable dictionary:

```text
status: success | no_results
query: original query with outer whitespace removed
source: document basename
policy_version: version extracted from the source
 document_sha256: SHA-256 of the exact loaded DOCX bytes
 data_mode: local_document
 retrieval_method: bm25_lexical
 requires_policy_evaluation: true
 matches: [
   {
     chunk_id: stable within this document snapshot,
     section: heading ancestry,
     section_references: [{body_block, type: heading}],
     kind: metadata | paragraphs | table_row,
     text: extracted source evidence (table rows are labeled with column headers),
     references: [{body_block, type, optional table/row/header_row}],
     context: [{text, references}],
     score: lexical ranking score
   }
 ]
```

The example above is a schema, not a fabricated policy excerpt. Document text and query text can be sensitive; consumers must avoid logging complete results automatically.

References use **1-based top-level Word body block positions**, including paragraphs and tables. Table numbers include the initial metadata table; table rows include the header as row 1. These are XML anchors, not Word page numbers. Locate them in `word/document.xml` inside the DOCX. Cite the document basename, version, SHA-256, section and evidence references together. Chunk IDs alone are insufficient across document revisions.

Each table row carries its headers and all narrative paragraphs in the same exact subsection as contextual evidence. This preserves nearby qualifiers. Context is not included in the BM25 score. Navigation entries from the document's Contents section are excluded. Both substantive sections and illustrative examples can be returned; the section label distinguishes their location but is not an authority ranking.

A positive score indicates term overlap, **not confidence, a complete answer or policy applicability**. `no_results` means no lexical overlap after stop-word removal; it does not prove the source has no applicable rule. Even a `success` response can be irrelevant or insufficient. Person A must preserve this distinction in any generated narrative.

## Person B / B3 boundary

Consume source evidence and provenance alongside traveler/itinerary attributes supplied independently. B2 returns no `compliant` or `approved` flag and performs no exchange-rate conversion, city-tier assignment, supplier verification or threshold interpretation. B3 must evaluate applicability, reconcile rules and request missing facts or human clarification. Unsupported decisions must remain unresolved.

The approved Demo Baseline remains an illustrative sample rather than evidence of an adopted corporate policy. It contains drafting notes, bracketed placeholders and qualifications. Known interpretation issues include exact boundary treatment for journey duration and overlapping approval bands, as well as differing cabin eligibility presentations. Supplier entries are placeholders; there is no verified supplier register. Daily total cap treatment is explicitly qualified. B2 retains the source language and does not settle these issues.

## Error and failure isolation contract

`PolicyRetrievalError` is a `ValueError` with `.code` and a safe message. Codes:

- `invalid_source`, `source_not_found`: missing/unsupported local source.
- `invalid_version`, `version_mismatch`: invalid metadata/configuration or a baseline mismatch.
- `invalid_document`: malformed archive/XML/body/table or size limit exceeded.
- `unsupported_document`: tracked revisions, merged/nested tables, text boxes, automatically numbered headings or unsupported body containers.
- `invalid_query`, `invalid_top_k`: invalid retrieval input.

There is no silent fallback to synthetic policy content. The index is an in-memory snapshot; reconstruct the tool after source changes. A failure must not discard independently obtained C1/C2/C3 results or fabricate a compliance outcome. No existing agent/module has been changed to wire B2 in.

## Tests and local retrieval evaluation

Python 3.12 is the validation baseline. For a small test environment, install only `pytest`, `requests`, `openai` and `python-dotenv`; the latter three support existing C1 imports. B2 itself uses the Python standard library. No API credentials are required.

```bash
python -m pytest -q
python -m compileall -q app.py agents services tools rag scripts tests
python -m scripts.evaluate_policy_retrieval \
  --document policies/TripPilot_Corporate_Travel_Policy_v2.docx \
  --cases policies/b2-evaluation-cases.json
```

Automated tests use synthetic DOCX fixtures, never the local baseline. CI can run without publishing the policy. Local evaluation judgments and reports are also ignored and must not be staged without publication authorization.

Local evaluation format: `{ "document_sha256": "<exact source hash>", "cases": [...] }`. Each case supplies `query` and either `expected: [{body_block, optional row}, ...]` or `no_results: true`. Author judgments from the source, not from retrieval output. The runner requires every expected anchor to appear in the top-k results or attached context, refuses a different source hash, prints only aggregate outcomes/coordinates and exits nonzero on any failed case. Empty or malformed suites fail validation.

Validation on the approved local version 2.0 baseline: **26/26 cases passed at top_k=5**, comprising 24 evidence cases and two no-overlap negative cases. Topics cover accommodation, city tiers, cabin eligibility, expenses, approvals, supplier placeholders, disruptions, personal extensions and AI authority guardrails. This is a small manually authored evidence-retrieval evaluation, not a B3 correctness test, semantic benchmark or proof that arbitrary questions are answerable.

## Limitations and owner actions

- This is the retrieval stage of RAG. Generation and semantic embeddings are not implemented.
- Word body paragraphs and simple rectangular tables are supported; headings use `Heading1`–`Heading6`. Headers, footers, comments, footnotes, images and rendered page layout are outside this loader's evidence contract. Overlong individual paragraphs are retained whole; the 1,800-character paragraph grouping target is not a hard token budget.
- The DOCX and evaluation artifacts stay local. A fresh clone needs an authorized local baseline; B2 initialization fails clearly if it is absent.
- Integrating this branch with C2/C3 is a separate team step. Their feature branches have not been merged here to satisfy B2.
- The pre-existing tracked `env.txt` remains an owner security issue. Do not inspect or publish its credential. Rotate/revoke exposed credentials, review usage, remove unsafe tracking/configuration and address historical exposure. Neither adding ignore rules nor this B2 change remediates earlier public exposure.
