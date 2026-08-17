# Frontend QA & Test Coverage Report

**Status: real data.** Every bug below was found via manual, real-account frontend testing (not synthetic/golden-query eval) and confirmed via direct code reading before any fix was proposed. Every fix was verified against real Azure/Groq calls (never Mailtrap — that channel stayed off-limits throughout this pass) and against the full mocked suite. Coverage numbers below are from a real `pytest-cov` run, not estimated.

## Test coverage

**Tooling:** `pytest-cov` was not previously installed or configured in this project (`pip list` confirmed no `coverage`/`pytest-cov` package present, `requirements.txt` had no entry). Installed via `pip install "pytest-cov>=5.0.0"`, confirmed safe first via `pip install --dry-run` — it added only itself and `coverage`, upgrading or downgrading nothing already installed (`pytest`, `pluggy`, `colorama`, `iniconfig`, `packaging`, `pygments` were all already satisfied). Added to `requirements.txt`. Config lives in a new `.coveragerc`.

**Scope decision:** `source = app, mcp_servers, evaluation` — not just `app/`. `mcp_servers/notification_mcp/server.py`'s own core logic (`_send_escalation_email_impl`, `_log_notification_impl`, `_tool_call_succeeded`) is exercised by direct in-process calls in `tests/integration/test_escalation_mcp.py`, not only by the one real-subprocess eval test, so it's real, testable application code and belongs in scope. `evaluation/` is the golden-eval/calibration tooling, also real code with its own test coverage. `scripts/` (one-time seed script) and `alembic/` (migrations) are excluded — infra, not application logic.

### Final result: 301 passed, 0 failed, 72% coverage (mocked suite only)

```
TOTAL  3994 stmts, 1101 missed, 72%
```

An earlier combined run (mocked + all real-call `eval` tests together, run once) showed 74% and surfaced 3 real test failures — see "Bugs found while preparing this report" below. All three are now fixed and reverified; the number above is the clean, final, mocked-only run after those fixes.

**Well covered (94-100%):** all `app/orchestration/nodes/*` (the actual graph logic — `classify`, `router`, `account_validation`, `incident_severity`, `reflect`, `respond` all 100%, `doc_retrieval` 89%), auth, RBAC, middleware, schemas, SQL tools, customers/documents/metrics routes.

**Real, named gaps — not silently omitted:**
| Area | Coverage | Why |
| --- | --- | --- |
| `app/ingestion/extract_tables.py`, `extract_text.py`, `pipeline.py`, `extract_diagrams.py`, `extract_images.py` | 18-37% | The weakest area by far. Likely under-covered by the mocked suite; may have more real coverage via `@pytest.mark.vcr` cassette tests not selected in this run — worth checking as a separate pass, not yet done. |
| `evaluation/run_full_calibration.py` | 0% | Expected — this is the manual recalibration script invoked by hand (`python -m evaluation.run_full_calibration`) during this project's SLO recalibration work, never called by pytest. |
| `app/win_loop.py` | 0% | Expected — only invoked by uvicorn's own `--loop` flag at real server startup; structurally unreachable from any test process. |
| `evaluation/ragas_metrics.py` | 32% | RAGAS-style scorers, real judge-call-dependent code; only lightly exercised outside real `eval` runs. |
| `mcp_servers/notification_mcp/mailtrap_client.py` | 38% | The real SMTP send path — only exercised by the one real-subprocess eval test, which is expensive/deliberately rare to run. |

**Honest caveat, stated plainly:** line coverage is not correctness coverage. Every real bug found and fixed this session (below) lived in code that already had *some* test presence — the bugs were in prompt behavior and cross-node merge logic, which a coverage percentage cannot see. A high number here should not be read as "the app is correct," only as "these lines execute during some test."

## Bugs found while preparing this report

Running the full suite (mocked + all real-call `eval` tests) in one combined pass, for the first time, surfaced 3 real failures — none caused by this session's earlier fixes, all pre-existing gaps this exercise happened to expose.

### 1. `test_hybrid_mode_branches_run_concurrently_not_sequentially` — real, structural flakiness, now fixed

This test proves `doc_retrieval_node` and `account_validation_node` genuinely run concurrently (LangGraph `Send` fan-out) by checking their real LLM-call timestamp intervals overlap. Its own docstring already *named* the root cause — `doc_retrieval_node`'s §31 Layer B scope check calls the real `embed_text()` (a genuine Azure embedding network call) before its own timed LLM call even starts, and this test's mocks never intercepted it — but the actual fix (mocking that one call) was never built. Confirmed directly: **3/3 repeated real runs failed consistently**, not intermittently.

**Fix:** added a `patch_embed_text_fast` fixture mocking just that one call, leaving every other real behavior in the test untouched. Since every other call in this test was already the fake LLM client (never real Azure), this removes the *only* genuinely real, uncontrolled call — the test is now fully deterministic and was **moved out of `eval` into the normal PR-blocking suite**, where a real concurrency-correctness property belongs.

**Verified:** 3/3 repeated runs pass, no longer `eval`-marked.

### 2. `test_chat_trace_lands_in_langfuse_with_real_observations` — real bug in the test's own polling logic

The real request completed successfully (36s, HTTP 200), then polling for the trace via Langfuse's REST API returned a non-empty `observations` list and stopped — but that list was a partial, early snapshot (`classify`, `router`, `doc_retrieval`, `hybrid_search`, `reflect` — no terminal node), not the complete trace. Langfuse's ingestion is eventually consistent; "any observations exist" is too weak a stopping condition for "the trace is done."

**Fix:** `_poll_for_trace()` now checks specifically for a terminal span name (`respond`/`escalate`/`out_of_scope_refusal`) as its actual convergence condition, matching the test's own stated "prove convergence, don't guess a sleep" principle. Also raised the polling budget (6 attempts/1.0s initial → 8 attempts/1.5s initial, ~21s → ~90s total) since the real failing run's own request already took 36s before polling even started.

**Verified:** 1/1 real Azure + Langfuse call passes.

### 3. `test_generic_or_status_query_does_not_over_trigger_critical[gq_009]` — classify severity carve-out (i) reliability

This was a known, already-partially-addressed issue (see "Prior fixes" below) — carve-out (ii) (status/lookup questions) had been strengthened and verified, but carve-out (i) (generic policy questions about the Critical tier as a concept) hadn't been stress-tested the same way. This run caught it failing for real on gq_009's exact query.

**Fix:** added a mechanical test to carve-out (i) ("would the answer be exactly the same regardless of whether any real Critical ticket/incident currently exists?") plus an explicit note that grammar (indefinite vs. definite article) isn't the real signal, and a new few-shot example (`Example 12`) using gq_009's own domain (security vulnerability policy, distinct from the existing SLA-policy example) to help the model generalize across domains, not just pattern-match one sentence.

**Verified:** 3/3 repeated real Azure calls pass.

## Prior fixes this session (frontend manual QA, before the coverage pass)

Full context for anyone reading this later — all found via real, logged-in frontend testing against real seeded customers (Alpha Corp, Beta Systems, Gamma Retail), not synthetic eval data:

1. **Customer picker discoverability** — the chat composer's customer picker capped its dropdown at 20 entries; with ~124 seeded customers sorted alphabetically, some (e.g. "Gamma Retail") never appeared without already knowing to search for them. Raised the cap to 150 and added a dedicated, agent-visible **Customers** page for actually browsing the roster.
2. **Stale "Route" badge** — `retrieval_mode` is set once by `router_node` and never updated, even when `reflect_node`'s retry loop causes `doc_retrieval_node` to run for a query originally routed SQL-only. Fixed by promoting the badge to "Hybrid" specifically on that fallback path.
3. **Self-contradictory final answers, sequential case** — a query originally routed SQL-only, retried into `doc_retrieval_node`, could show a stale account-context-blind denial glued next to the real SQL answer. Fixed by passing account-context awareness into `doc_retrieval_node`'s own prompt for that specific retry path.
4. **Self-contradictory final answers, concurrent case** — the same symptom recurred for genuine Hybrid-mode queries, where `doc_retrieval_node`/`account_validation_node` run truly concurrently and can't see each other's verdict. Fixed at the real merge point (`reflect.py`'s `_merge_final_answer()`) using each node's own `evidence_sufficient` signal (newly persisted to state) to prefer whichever side actually has something to say, instead of naively concatenating a denial next to a real answer.
5. **Incident severity over-triggering, real root cause** — `incident_severity_node` cross-references every incident/security query against a system-wide, region-*unscoped* active-incidents list (~52 seeded incidents). Its own prompt taught a flawed pattern: any active Critical incident existing *anywhere* was enough to raise severity, with no requirement it actually relate to the query. Fixed by requiring genuine relevance (a specific incident's type/region/description must actually correspond to what the query describes), not mere co-occurrence.
6. **Classify severity carve-outs** — two narrower shapes (generic policy questions about the Critical tier; plain status/information lookups) were also over-triggering Critical. Both addressed with mechanical tests and contrastive few-shot examples in `classify_v1.py`.
7. **Kitchen-sink narrative verbosity** — `account_validation_node`'s narrative padded narrow queries (e.g. "what's the account status?") with unrelated ticket/incident summaries, most persistently for incidents (present for almost any customer with a region on file). Strengthened `account_validation_v1.py`'s scoping instructions specifically for this case.

All of the above (1-7) were verified with real Azure/Groq calls at the time and are covered by dedicated regression tests (`test_doc_retrieval_node.py`, `test_reflect_merge_final_answer.py`, `test_incident_severity_relevance.py`, `test_classify_severity_not_over_triggered.py`, `test_account_validation_narrative_scoping.py`).

## Known, still-open item

`_merge_final_answer()`'s concatenation, when **both** sides have real, substantive, but *overlapping* content (not one side being empty), still just glues them together — this can produce a redundant, roughly-doubled answer rather than a synthesized one. Confirmed live (a "data breach response protocol" query got two independently-complete 5-7 step answers back to back). Not a contradiction (both fixed above), just verbosity — deliberately left open, not yet fixed.
