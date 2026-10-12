# B2 PR #6 independent review

Reviewed starting HEAD: `d8500c75b50cf419e6e04514a56d87b9d4a039bc`. Line references in the findings below refer to that reviewed commit. The review used targeted synthetic failure probes and a separate source-coverage/citation audit, beyond rerunning the existing tests.

## Findings

| Priority | Reviewed location | Finding and impact | Remediation / disposition |
| --- | --- | --- | --- |
| P1 | `rag/document_loader.py:118–120` | Heading ancestry used list positions as Word heading levels. The actual baseline skips a level before its scenarios; later sibling scenarios incorrectly inherited the first scenario's heading and citation. This mislabels evidence and influences ranking. | Fixed: track actual heading levels and remove headings at the same/deeper level before adding a heading. A synthetic skipped-level regression checks sibling citations and context. |
| P1 | `rag/document_loader.py:60–62` | ASCII byte scanning for DTD/entity declarations was bypassed by UTF-16 XML. A synthetic entity was expanded into retrieved text despite the documented rejection contract. | Fixed: reject DOCTYPE through the XML parser callback, independent of encoding. Tests cover UTF-8 and UTF-16, including both byte orders. No policy text was altered. |
| P1 | `rag/document_loader.py:55–66` | Encrypted, unsupported-compression and damaged ZIP members, plus unsupported XML encodings, can raise exceptions outside `PolicyRetrievalError`. Callers following the advertised failure-isolation contract cannot identify these failures consistently. | Fixed: translate archive-read errors only at that library boundary, and encoding errors only around XML parsing. Regression tests verify safe `invalid_document` errors. |
| P2 | `rag/retriever.py:50–58` | Any positive lexical overlap produces `success`. Mixed unsupported/relevant queries can return hotel evidence while their unsupported terms remain unanswered. Ambiguous or negated queries also retrieve evidence without assessing intent. | Already documented. Person A/B3 must assess sufficiency and applicability; never treat status/score as an answer or a compliance verdict. No semantic classifier was added. |
| P2 | `scripts/evaluate_policy_retrieval.py:39–45`, `docs/b2-integration-handoff.md:112` | The 26-case evaluation measures top-five required-anchor coverage, including context, plus two no-overlap negatives. It does not measure irrelevant-result precision, contradiction handling or compliance correctness. The original cases passed even with the incorrect heading hierarchy. | Added targeted structural regressions and an independent full-source audit. Broader quality evaluation remains a future team task, not a claimed result. |
| P2 | `tools/policy_search.py:8`, `docs/b2-integration-handoff.md:118` | The default baseline is local and absent from Git. A fresh clone cannot initialize the real tool until an authorized document is provisioned. | Deployment dependency: an owner-authorized private team copy or protected runtime file mount, verified against the expected hash. No public document publication or sharing action was performed. |

No P0 finding was established. No P3 changes were proposed or implemented.

## Executed local validation

Python 3.12.14, isolated environment; no external API calls in automated tests.

- Before fixes: `python -m pytest -q` — **122 passed, 0 failed, 0 skipped**.
- After fixes: same command — **133 passed, 0 failed, 0 skipped**, retaining all 122 existing cases and adding 11 focused parser regressions.
- `python -m compileall -q app.py agents services tools rag scripts tests` — passed.
- Actual local DOCX runner with the existing SHA-256-pinned cases — **26/26 passed at top_k=5** before and after fixes. Judgments and reports remain local.
- Independent XML audit: all **97 non-heading/non-Contents paragraphs**, **70 data rows**, **13 tables** and **103 heading chains** matched source text/coordinates. Table headers, nearby qualifiers and exceptions were preserved. Version is 2.0 and the SHA-256 matches the exact source bytes.
- Baseline, evaluation cases/report and two teammate files retain their preflight hashes. None is staged/tracked.
- The public tool signature, output schema, retriever, C1, C2, C3, TripAgent and B1 policy text are unchanged. B2 still returns evidence only; generated answers and compliance decisions remain absent.

Hosted CI must pass on the pushed correction commit before reporting the PR ready. CI uses synthetic DOCX fixtures without the private baseline; the actual-document check is local, not a hosted CI result.

## Policy availability and integration readiness

The current workspace can retrieve the approved Demo Baseline. Availability to other team members is **not yet verified**. Git ignore rules protect against accidental staging, but they are neither access control nor publication authorization. Existing public links in README do not override the user's restriction.

The policy owner should authorize private team distribution, grant access to intended recipients, and provide the exact baseline plus its SHA-256 through an approved channel. Person A should keep it outside Git or at the ignored local path, pass `document_path` explicitly in deployed environments, and verify the hash before deployment. Approval of a source's version label alone does not authenticate its bytes or provenance. No restricted content was copied into tests or this public review.

Person A can integrate the unchanged optional tool, catching initialization and retrieval failures without discarding flight/hotel/weather results. Person B/B3 must resolve source ambiguities, missing supplier details, exact threshold boundaries, currency treatment and rule applicability separately. Successful retrieval is not evidence that these compliance decisions work. No agent integration, approval flow or autonomous booking was added.

The project team describes `env.txt` values as invalid demo placeholders. They were not inspected, published or tested. This review establishes no effective credential blocker; any demonstrated real historical exposure would require separate owner remediation.
