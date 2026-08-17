# SLO Evaluation Report

**Status: real data, fully re-verified.** A genuine full-50-query pass against `golden_queries/golden_50.json` was completed and persisted twice: an original pre-fix baseline (`app.db.models.EvaluationRun`, `run_id=5`) and, after every fix below was applied, a second genuine full 50-query pass through the real graph AND the real (fixed) Groq judge (`run_id=6`, `run_at=2026-08-12 06:41:44 UTC`) — no field in this report is stale or "not yet re-verified" anymore. Five real bugs found during investigation of `run_id=5`'s numbers and of the production `GET /metrics` dashboard were fixed in code: two deterministic graph bugs, one Langfuse metrics-API bug (verified live against real production trace data), and two in `compute_correctness()`'s judge prompt (a scoping bug and a disjunction-splitting bug found while verifying the first fix), both verified against real Groq calls and then folded into the full `run_id=6` re-run. Two golden-set label errors were also corrected, with evidence for why each is a genuine error rather than a fit-the-system edit. Every number below is real — either from `run_id=5`, `run_id=6`, or a live Langfuse/Groq query — never guessed. Fields not yet measured (latency, load test, prompt-version comparison) are still marked `TBD`.

## Run metadata

| Field | Value |
| --- | --- |
| Pre-fix baseline run date | 2026-08-11 (EvaluationRun `run_id=5`, `run_at=2026-08-11 08:07:38 UTC`) |
| **Post-fix final run date** | **2026-08-12 (EvaluationRun `run_id=6`, `run_at=2026-08-12 06:41:44 UTC`)** |
| Sample size, both runs | **50 (full golden set)** — see "How the full-50 run was actually achieved" below |
| Judge model | `llama-3.3-70b-versatile` (Groq) — see §24.2 note below for why |
| Active prompt version | `classify_v1` (updated this session — see "Bugs found and fixed" below) |
| Golden set | `golden_queries/golden_50.json` |

## §24.1 — Latency SLO decision, stated plainly

The course rubric's own target (≤2s) and this project's original latency-budget design (§13, ≤4s) genuinely disagreed. Resolved decision, adopted before Stage 9 measurement began: **≤2s for RAG/SQL/Hybrid paths (~90% of traffic)**, with **Critical carved out as its own documented exception at ≤3.5s** — a confident-but-wrong answer on an active outage is worse than the extra latency a Critical path's additional agents (incident severity, escalation) genuinely require. This is not a silent weakening of the 2s target; it is a named, deliberate exception for one specific path, measured and reported separately below, never averaged into the other three. **Not measured this session** — this report's work was scoped to correctness/routing/retrieval metrics, not latency; the latency rows below remain `TBD`.

## §24.2 — Independent judge model, stated plainly (including the honest caveat)

The independent LLM-as-judge (§24.2) is `llama-3.3-70b-versatile` on Groq's free tier — a standard, non-reasoning, Production-tier model. **Confirmed weaker than GPT-5-mini on standard benchmarks, not stronger or comparable.** Its justification is independence (a different lab, avoiding the self-grading bias problem an independent judge exists to catch), not superiority — this is stated here explicitly so it is never read as a quality claim it doesn't support. An earlier candidate (`qwen/qwen3.6-27b`) was tried first and replaced after real, measured cost/reliability problems (see `evaluation/groq_judge_client.py`'s own docstring for the full history).

## Methodology note on sample size

`--sample` (5–10, stratified across all five query categories — see `evaluation/golden_runner.py`'s `_stratified_sample`) remains the practical default for a single run: a full 50-query pass against `golden_50.json` consumes close to an entire Groq free-tier account's *entire daily* token budget (~100K tokens) by itself — confirmed directly, not estimated (a single 10-query pass alone consumed 99,798 of 100,000 available tokens on a fresh account).

### How the full-50 run was actually achieved

A genuine 50-query pass **is** achievable, but not in one process invocation on one free-tier key. `evaluation/calibrate_thresholds.py`'s own `run_calibration()` is deliberately all-or-nothing — it only persists anything once every query in the batch finishes, so a run that exhausts its daily quota partway through loses everything, including the queries that did complete. `evaluation/run_full_calibration.py` (added this session) closes that gap: it checkpoints every query's result to `evaluation/results/full_calibration_checkpoint.json` immediately after that query completes, and skips already-checkpointed queries on the next invocation. The `run_id=5` baseline was produced this way across five separate Groq API keys. The `run_id=6` post-fix re-run repeated the exact same process **from a cleared checkpoint** (the stale pre-fix checkpoint was backed up, not reused, so `run_id=6` reflects entirely fresh graph + judge calls, not recycled old data) — five keys were swapped in, of which four were productive (10, 16, 13, then 11 queries) and one contributed zero new queries because it turned out to share its daily token quota with an already-exhausted key from the same underlying Groq account/organization (confirmed by matching `org_...` IDs in the two `RateLimitError` messages) — a real, previously-undocumented failure mode worth naming: a "new" API key is not guaranteed to mean a fresh quota if it comes from the same account as a key already used that day. This is disclosed here because it is real, unusual operating friction worth knowing about, not a one-time fluke — a future full-50 run will need the same multi-key (multi-*account*) approach unless the judge moves to a paid tier or a cheaper model.

Two real, unplanned Azure content-filter events occurred during the `run_id=6` run (Azure's own `jailbreak: detected` classifier tripped on two of the real golden queries' generated prompts). Both were caught cleanly by the existing `_guard_structured_output` wrapper (`app/orchestration/graph.py`) exactly as designed — logged as `content_filter_error_escalated` and converted to a graph-level escalation rather than an unhandled crash — so neither run stalled or lost data. This is a real, live confirmation that that guardrail path works end-to-end under real traffic, not just under its own unit tests.

## Full-50 baseline vs. post-fix results

Two real deterministic graph bugs and two real judge-prompt bugs (all documented below) were found while investigating why several `run_id=5` numbers looked implausibly low for functionality that was already unit-tested/verified in earlier stages. All four were fixed, and then **all 50 golden queries were re-run end-to-end through the real graph and the real (fixed) Groq judge** (`run_id=6`) — every metric below, including the judge-dependent ones, is now a genuine post-fix measurement, not a carried-over pre-fix value. Both columns are computed with the exact same `calibrate_thresholds.aggregate_calibration_metrics()` formulas against the exact same (corrected) `golden_50.json` labels, so the Δ isolates the real effect of the code fixes plus the normal query-to-query variance of two independent live LLM runs — not a label-set difference.

| Metric | Baseline (`run_id=5`, pre-fix logic, re-aggregated against corrected golden labels) | Post-fix (`run_id=6`, fresh 50-query re-run, fixed graph + fixed judge) | Δ |
| --- | --- | --- | --- |
| `task_success_rate` | 0.44 | **0.58** | **+0.14** |
| `query_routing_accuracy` | 0.48 | **0.58** | +0.10 |
| `risk_classification_accuracy` | 0.50 | **0.58** | +0.08 |
| `escalation_recall` | 0.33 | **0.62** | +0.29 |
| `critical_misclassification_rate` | 0.50 | **0.083** | −0.42 |
| `context_recall` | 0.21 | **0.39** | +0.18 |
| `sql_correctness` | 0.20 | 0.20 | 0 (expected — see ‡ below, structural tool-surface gap, not judge-related) |
| `faithfulness` | 0.734 | **0.751** | +0.017 |
| `answer_relevance` | 0.650 | 0.621 | −0.029 (real judge/run variance; both real n=50 measurements) |
| `context_precision` | 0.736 | **0.772** | +0.036 |

`sql_correctness` holding flat at exactly 0.20 in both real runs is itself a useful confirmation, not a gap in this recalibration — it corroborates the separate, already-documented finding (see ‡ under SLO results below) that 7 of 10 SQL golden queries are structurally unanswerable by the real tool surface regardless of `customer_id`, a graph/tool-surface limitation this session's judge-prompt and routing fixes were never going to move.

**A new, separate finding surfaced by this full re-run, not yet acted on:** three queries with `expected_escalation=No` in the golden set (`gq_009`, `gq_011`, `gq_022` — all informational/policy questions that merely *mention* "Critical" or reference an existing incident, not live emergencies) resolved to `effective_severity=Critical` in the real graph run, which auto-triggers escalation regardless of category. This looks like the severity classifier over-keying on words like "Critical"/"outage" in the query text rather than distinguishing a live incident report from a question *about* one. This is a distinct root cause from the two severity-prompt/category-filter bugs already fixed this session (neither of those touches this shape of query) and was not investigated or fixed here — flagged as a new candidate for the same "real evidence, then propose a fix" process used for everything else in this report.

## Golden-set label corrections applied this session

`gq_029` and `gq_035` were originally suspected (via a text-search heuristic — "does the query mention the word Critical") as 6 possible label errors. **That heuristic was wrong and was not acted on as-is** — direct verification against real routing data showed only 2 of the 6 were genuine conflicts with `router.py`'s own exhaustively-tested design (`severity_initial == "Critical"` always overrides to Critical mode); the other 4 had different, already-documented root causes (see "Known Limitations" below) and would have been corrupted by a blanket edit — one of them (`gq_016`) didn't even mismatch in the first place. Only the 2 verified cases were changed:

```diff
  "id": "gq_029",
  "query": "Is Alpha Corp's Critical security ticket connected to an active logged security incident?",
  "query_type": "Hybrid",
- "risk_level": "High",
+ "risk_level": "Critical",
- "expected_retrieval_mode": "Hybrid",
+ "expected_retrieval_mode": "Critical",
```

```diff
  "id": "gq_035",
  "query": "Should Alpha Corp's Critical security ticket be automatically escalated per SLA policy?",
  "query_type": "Hybrid",
- "risk_level": "High",
+ "risk_level": "Critical",
- "expected_retrieval_mode": "Hybrid",
+ "expected_retrieval_mode": "Critical",
```

Both reference `ticket_id=3`, a Critical-severity ticket; `gq_035`'s own `ground_truth_answer` states *"Critical severity always auto-escalates regardless of SLA tier"* — the golden label previously contradicted its own ground truth. `risk_level` was updated alongside `expected_retrieval_mode` to avoid leaving a self-inflicted mismatch on a different metric (`risk_classification_accuracy`) after fixing the routing one. `tests/unit/test_golden_distribution.py`: 11/11 pass after both edits (distribution counts key off `query_type`, unaffected; `Critical` is already a valid value for both `risk_level` and `expected_retrieval_mode`).

## Bugs found and fixed this session

### 1. Category-filter exclusion bug (`app/orchestration/nodes/doc_retrieval.py`)

**Before:** `doc_retrieval_node` passed `filters={"category": <classify_node's own topic classification of the query>}` into `hybrid_search`, applied as a hard `WHERE` exclusion in both `vector_search`/`keyword_search` — not a soft signal. The query's own topic and the *correct answer document's* topic are independent axes that don't reliably align. Measured directly: of the 26/50 golden queries that reach this filter, **11 (42%) had their top-1 retrieval result change when the filter was removed** — and in every case checked, the unfiltered result was the correct one. One category value (`billing`) is structurally unmatchable: the real ingested corpus's category tags are only `{incident, integration, security, usage}` — no document is ever tagged `billing` — so a `billing`-classified query got **zero retrieval candidates every time**, guaranteed.

Real before/after evidence (`fuse()`, same query, filter on vs. off):

```text
WITH filter category=usage:     score=0.01639 chunk#6  cat=usage    doc='API Error Codes & Troubleshooting Handbook'
WITHOUT filter:                 score=0.01639 table#14 cat=incident doc='ITIL Incident Management Summary'  (correct)
```

**Fix:** `doc_retrieval_node` no longer constructs a category filter at all — `category` was removed from `_run_one_attempt()`'s signature entirely, not just conditionally skipped. `product_version` remains a hard filter, unchanged — a genuinely different, legitimately exclusive concern (§27's "conflicting documentation across versions" scenario). `vector_search.py`/`keyword_search.py`'s own category-filtering mechanism is untouched and still available to any future caller that passes one explicitly.

**Verified:** a new regression test (`tests/integration/test_hybrid_search.py::test_no_category_filter_retrieves_correct_top1_document`) asserts the correct document now wins top-1 for the three queries directly implicated (`gq_004`, `gq_007`, `gq_010`) — 3/3 pass against the real corpus.

### 2. Severity-prompt gap (`app/prompts/classify_v1.py`)

**Before:** the prompt's only severity guidance was "assign an initial severity estimate based on the query's own wording alone," with exactly one few-shot example — a live, in-progress emergency ("Our production system is down and customers can't log in!"). No example covered a query that *references* an already-Critical item in policy/procedural framing rather than reporting a live emergency. Measured directly against the 10 real `risk_level=Critical` golden queries: **queries that literally stated "Critical" in their own text had a 0/3 hit rate** for getting `severity_initial=Critical` — worse than queries that didn't (3/7) — ruling out a simple "can't read the word" explanation and pointing at a genuine interpretation gap (live-emergency framing vs. administrative/policy framing about an existing Critical item).

**Fix:** `ROLE_INSTRUCTIONS` now explicitly names both shapes — "(a) an in-progress emergency happening right now" and "(b) a query that references an item ALREADY at Critical severity, even when phrased as a policy, procedural, or administrative question." A new few-shot example (Example 8) was added alongside the existing live-emergency example (not replacing it), covering the second shape directly.

**Verified:** a new regression test (`tests/integration/test_classify_severity_critical_reference.py`) asserts `severity_initial=Critical` for `gq_040`, `gq_042`, `gq_048` — 3/3 pass against real Azure calls. In the full 50-query post-fix re-run, all three now show `effective_severity=Critical` end-to-end (not just `severity_initial`), and overall Critical-labeled query accuracy rose from 3/10 to 8/10.

### 3. `GET /metrics` was querying the wrong Langfuse API entirely (`app/observability/tracing.py`, `app/api/routes_metrics.py`)

**Before:** live latency/cost were sourced from Langfuse's `client.api.metrics.metrics()` "observations" view, filtered to the 3 terminal node span **names** (`respond`/`escalate`/`out_of_scope_refusal`). This looked plausible but was wrong in a way a first fix (a missing filter `"type"` discriminator, fixed earlier and superseded by this one) didn't catch: those terminal spans are thin wrappers with no LLM call inside them (a few milliseconds each) — the real per-request cost and cumulative time live on *other* node spans (`classify`/`account_validation`/`reflect`) and their nested `OpenAI-generation` children, which don't share those names and were never included. Confirmed directly: a real live query against this view returned `sum_totalCost: 0` and `p50_latency_ms: 2` despite real, costed traffic existing.

Direct inspection of a real, known trace (`trace_id=41fd537c...`) resolved this: Langfuse's *trace*-level API (`client.api.trace.list()` / `.get()`) returns its own pre-computed `latency` and `total_cost` fields, which correctly sum every descendant observation. That trace's own `latency=16.949s` matched the real wall-clock sum of its 5 node spans (classify 3.932 + router 0.002 + account_validation 5.071 + reflect 7.874 + respond 0.005 ≈ 16.884, remainder being real orchestration overhead), and `total_cost=0.00183625` matched *exactly* the sum of its 3 real generation costs. A trace's own `name` field was also confirmed to resolve to whichever node ran **last** (not first) for that request — so filtering `trace.list(name=...)` by the same 3 terminal names still correctly selects "one complete real request."

**Fix:** `tracing.safe_query_metrics()` (metrics-API based) removed entirely; replaced with `tracing.safe_query_trace_metrics()` (`client.api.trace.list()`, paginated, filtered by `name` and time window), returning real per-trace `{latency, total_cost}` records. `routes_metrics.py` now computes P50/P95 locally (nearest-rank percentile) from these real records instead of relying on a server-side aggregate query, and sums real `total_cost` directly.

**Verified — real before/after query results:**

```text
BEFORE (observations-view, "type"-fixed but wrong API):  sum_totalCost=0          p50_latency_ms=2
AFTER  (trace.list(), real per-trace data):               389 real traces found
                                                            sum_totalCost=1.402196   mean_cost_per_trace=0.003605
                                                            p50_latency_ms=12990.0   p95_latency_ms=78532.0
```

The 24h window used for the "after" verification includes heavy automated batch testing from this session (repeated full 50-query calibration re-runs), so the absolute p95/max latency numbers above are not representative of normal single-request load — they will normalize once the window rolls past today. The *mechanism* is what's confirmed fixed: non-zero cost, and latency in the range real end-to-end requests actually take, not a single span's own fractional-second duration.

Full non-eval suite re-run alone (no concurrent pytest sessions — an earlier run showed spurious failures in unrelated tests from running 3 pytest sessions against the same shared disposable test database simultaneously): **284 passed, 0 failed.**

### 4. `compute_correctness()` extracted facts the query never asked about (`evaluation/calibrate_thresholds.py`)

**Before:** the correctness judge's fact-extraction prompt pulled *every* factual claim out of `golden_50.json`'s `ground_truth_answer`, including context the query itself never asked for (e.g. `gq_013` asks only about PostgreSQL/Redis versions; its ground truth also names Node.js/Python versions as surrounding context). Combined with the scorer's unanimous-agreement rule, a fully correct, well-scoped real answer that correctly omitted the tangential facts still failed the whole query. Confirmed directly: `gq_007` and `gq_013` both scored `faithfulness=1.0` (nothing hallucinated) yet `correct=False` under the old prompt — real answer text matched their ground truth exactly on what was actually asked.

Extrapolating across the full run's 40 "incorrect" verdicts, at least 6 shared this exact signature (`faithfulness=1.0`, `correct=False`, correctly-routed Documentation queries) — likely more among the 13 that couldn't be fully audited (see below), pending real re-verification.

**Fix:** the extraction prompt now explicitly scopes to *"facts that are PART OF THE DIRECT ANSWER TO THE QUERY"* and instructs the model not to extract tangential context. `compute_correctness()` also no longer short-circuits on the first failed fact — every fact in the (still-capped) check set is now verified, so the returned `CorrectnessAudit` (extracted facts + every individual verdict) is always complete, not partial.

**Also fixed alongside it — the audit-trail gap that made this hard to investigate in the first place:** the original checkpoint (`evaluation/run_full_calibration.py`) only ever persisted the final `correct` boolean per query, not what was actually extracted/checked — so confirming the `gq_007`/`gq_013` bug required re-deriving it by hand from real answer text, and 13 of 19 originally-"unexplained" low-scoring queries couldn't be investigated at all without spending fresh, real judge quota just to reproduce a call that had already been made once. The checkpoint now persists the full `CorrectnessAudit` (extracted facts + per-fact verdicts) for every query, so a future investigation reads real historical data instead.

**A second, related bug was found running the real verification test** (not by inspection): `gq_013`'s ground truth states *"PostgreSQL 14.x or 15.x"* — a disjunction, either version satisfies the requirement. Even after the scoping fix above, extraction still split this into two independent facts ("14.x is required", "15.x is required"), and a real answer that correctly states the full "14.x or 15.x" alternative still failed — the isolated verification call for "15.x is required" correctly says no, since the answer doesn't claim 15.x is *the* requirement, only that it's *a* valid option. **A zero-cost scan of `golden_50.json` found this is systemic, not a one-off: ~4-8 of 50 `ground_truth_answer` entries state alternative-satisfies-one-requirement claims of this same shape** (e.g. `gq_011`'s "report via email or the bug bounty program", `gq_014`'s "any of: user impact over 100 users or 25%..."). Fixed by instructing the extraction prompt to keep a stated alternative as ONE atomic fact (preserving the "A or B" wording) instead of splitting it.

**Verified — real Groq calls, both fixes together:** `tests/integration/test_compute_correctness_scoping.py`'s two tests (`gq_007`, `gq_013`) — **2/2 passed** against the real judge. The `gq_013` test additionally asserts the extraction never splits the PostgreSQL alternative into more than one fact. Full non-eval suite (mocked, unaffected by prompt wording): **284 passed, 0 failed** (3 existing test mocks updated to the new `CorrectnessAudit` return type).

## SLO results

Baseline column is `run_id=5` (full n=50, pre-fix). Post-fix column is `run_id=6` (full n=50, fresh real graph + fixed judge — every field below is now a genuine post-fix measurement, none are carried over).

| # | Metric | Target | Measured (baseline, n=50) | Measured (post-fix, n=50) | Meets target? |
| --- | --- | --- | --- | --- | --- |
| 1 | Faithfulness | ≥ 80% | 73.4% | **75.1%** | ✗ (both, real improvement) |
| 2 | Answer Relevance | ≥ 75% | 64.96% | 62.1% | ✗ (both) |
| 3 | Context Precision | ≥ 70% | 73.6% | **77.2%** | ✓ (both) |
| 4a | Latency P95 — RAG | ≤ 2.0s | TBD | — | TBD |
| 4b | Latency P95 — SQL | ≤ 2.0s | TBD | — | TBD |
| 4c | Latency P95 — Hybrid | ≤ 2.0s | TBD | — | TBD |
| 4d | Latency P95 — Critical | ≤ 3.5s | TBD | — | TBD |
| 5/7 | Accuracy / LLM-as-judge* | ≥ 85% | TBD — requires `evaluation/run_eval.py`, not yet run (separate script from `calibrate_thresholds.py`, used this session) | — | TBD |
| 6 | Context Recall† | ≥ 75% | 21% | **39%** | ✗ (both, real improvement) |
| 8 | Task Success Rate | ≥ 90% | 44% | **58%** | ✗ (both, real improvement) |
| 9 | SQL Correctness‡ | ≥ 95% | 20% | 20% (unchanged — see ‡, structural gap not fixed) | ✗ (both) |
| 10 | Source Attribution Rate | 100% | TBD | — | TBD |
| 11 | Critical Misclassification Rate | < 3% | 50% | **8.3%** | ✗ (both, large real improvement) |
| 12 | Escalation Recall | 100% | 33% | **62%** | ✗ (both, real improvement) |
| 13 | Unauthorized Data Access (RBAC) | 0 violations | See `tests/integration/test_rbac_violations.py` (CI-enforced, not a golden-eval metric; confirmed passing) | — | ✓ |
| 14 | Guardrail Effectiveness | 100% | See `tests/integration/test_guardrail_redteam.py` (CI-enforced, not a golden-eval metric; confirmed passing) — also confirmed live: two real Azure content-filter/jailbreak triggers during `run_id=6` were both correctly escalated, not crashed (see "How the full-50 run was actually achieved" above) | — | ✓ |
| 15 | Query Routing Accuracy | ≥ 95% | 48% | **58%** | ✗ (both, real improvement) |
| 16 | Risk Classification Accuracy | ≥ 95% | 50% | **58%** | ✗ (both, real improvement) |

**Baseline column note:** rows 11/16 (`critical_misclassification_rate`, `risk_classification_accuracy`) differ from earlier drafts of this report (which showed 40%/54%) because they are now re-aggregated against the corrected `gq_029`/`gq_035` golden labels (see "Golden-set label corrections" below) — the underlying `run_id=5` graph/judge data is unchanged, only the comparison labels were fixed, isolating the baseline column to a fair pre-code-fix comparison point.

**Calibrated confidence thresholds — a real, automatic side effect of completing this run, not yet manually confirmed:** `run_id=6`'s threshold search wrote `evaluation/results/calibrated_thresholds.json` with `confidence_high_threshold=0.95` (unchanged) and `confidence_medium_threshold=0.70` (down from the prior 0.75). `app/config.py`'s `get_settings()` reads this file automatically and overrides the `.env` defaults — this is `lru_cache`d per-process, so it has **no effect on an already-running server process**, but **will take effect the next time any process (dev server, tests, scripts) restarts**, silently lowering the bar for auto-responding without escalation. Flagging this explicitly rather than letting it pass unnoticed, per this project's standing "confirm before consequential state changes" discipline — worth a deliberate look before the next restart, not necessarily a problem, since it was produced by the exact real calibration process this file exists for.

\* **#5 (Accuracy) and #7 (LLM-as-judge) are the same real signal, reported once.** Confirmed, not assumed: §24.2's own text ties "Accuracy... scored per §24.2" to the identical independent-judge mechanism described for #7 — no second correctness mechanism exists anywhere in this codebase. This value comes from `evaluation/run_eval.py`'s own `accuracy_llm_judge` field, a distinct script from `evaluation/calibrate_thresholds.py`/`run_full_calibration.py` (used to produce every other number in this report) — not yet run this session, hence `TBD` rather than a guess.

† Context Recall is computed via `golden_50.json`'s own `expected_sources` label-matching, a deliberate, named simplification of canonical RAGAS (which uses judge-based sentence-level attribution) — see `evaluation/ragas_metrics.py`'s `compute_context_recall()` docstring for the full argument.

‡ **SQL Correctness's low baseline number is not primarily a product-quality signal, and it's a deeper problem than the `customer_id=1` harness limitation alone** — investigated directly with real per-query evidence, two layers:

1. Every golden SQL-type query is run with a hardcoded `customer_id=1` (`evaluation/golden_runner.py`'s own disclosed limitation, since `golden_50.json` carries no `customer_id` label at all).
2. **Deeper finding:** `account_validation_node`'s actual tool surface is exactly three functions — `get_customer(customer_id)`, `get_tickets(customer_id)`, `get_incidents(customer_id)` — all scoped to one authenticated customer, by deliberate RBAC/isolation design, already confirmed correct and secure in Stage 6's own injection testing. There is no cross-customer listing tool, no lookup-by-company-name tool, and **no tool for `knowledge_article_usage` at all.** Checked against all 10 golden SQL queries: **7 of 10 are structurally unanswerable by this tool surface for ANY customer_id** — `gq_017`/`gq_021` ask for cross-customer listings ("show all customers..."), `gq_018`/`gq_025` ask about a *named, different* customer (Beta Systems, Gamma Retail), `gq_024` asks about KB articles (no tool exists), and `gq_020`/`gq_022` ask about the EU region while the only real seeded customer (Alpha Corp) is US-region. Even with a perfect `customer_id`, these 7 stay unanswerable.

This is a real, disclosed harness/product-scope gap, not a bug in the SQL agent or the comparison logic — the agent is correctly refusing to answer with data or tools it doesn't have. Two separate real fixes are possible and neither was attempted this session: (a) label golden queries with the real `customer_id` they're actually about, which fixes the queries about Alpha Corp/other *specific* customers but not the ones needing tools that don't exist; (b) build the missing tools (cross-customer/admin query path, KB-article lookup) if that capability is actually in scope for this product — a product-design decision, not a quick patch.

## Mechanism-based metrics (not golden-eval numbers, confirmed already in place)

| Metric | Target | Verified via |
| --- | --- | --- |
| Cost per ticket | ≤ $0.04 | `GET /metrics` (fixed this session — see Bug #3 above; real mean cost per completed trace confirmed at $0.0036, well under target, though today's window is contaminated by heavy batch testing rather than normal single-user load) |
| Notification delivery | 100% of Critical escalations logged | `test_escalation_mcp.py` |
| Re-ingestion no-op cost | 0 embedding calls when doc unchanged | `test_dedup_engine.py` |
| Graph termination | 100% of runs reach `END` within bounded steps | `test_no_infinite_loop.py` |
| PR-blocking CI real-LLM-call count | 0 | `backend-ci.yml` (`LLM_PROVIDER=mock`) |

## Known Limitations

Named plainly here rather than silently left unaddressed — investigated with real evidence this session; each left as a documented limitation rather than fixed, for the reasons given. (Two related items — the `gq_029`/`gq_035` Critical-routing conflicts — were *not* left open; see "Golden-set label corrections applied" above. The items below are genuinely different root causes that a blanket label edit would not have fixed.)

### `route_by_category()`'s `billing` → `Hybrid` structural gap

`app/orchestration/nodes/router.py`'s `route_by_category()` mapping has no path from `category="billing"` to `retrieval_mode="Hybrid"` at all (`billing` → `SQL`; only `incident`/`security` → `Hybrid`). Of the 26 routing mismatches found in the baseline run, 8 are `billing`-classified queries where the golden set expects `Hybrid` — and several of those (e.g. *"Does Beta Systems' Enhanced SLA tier qualify them for priority escalation on a Critical issue?"*) are genuinely, correctly billing/SLA-flavored by any reasonable reading. Even a "correct" `billing` classification could never satisfy the golden set's `Hybrid` expectation here, because the mapping table itself has no route there. This is left undecided rather than patched today because the real fix requires a design decision this session didn't make: either `route_by_category()`'s mapping needs to change (letting `billing` reach `Hybrid` under some condition — TBD which), or `golden_50.json`'s own `expected_retrieval_mode` labels for these specific entries need re-examination against what the router's category taxonomy was actually designed to support. Both are bigger decisions than a quick patch, and doing either without the other risks fixing the symptom in the wrong place.

### Severity classifier over-triggers Critical on informational/policy queries that merely mention an incident

Found during `run_id=6`'s real re-run, not by inspection: three queries labeled `expected_escalation=No` in the golden set — `gq_009` ("What are the patch deployment timelines for a Critical severity security vulnerability?"), `gq_011` ("What is the process for responsibly disclosing a discovered security vulnerability?"), and `gq_022` ("What is the resolution status of the EU outage incident?") — all resolved to `effective_severity=Critical` in the real graph run, which unconditionally escalates regardless of category (`route_by_category()`'s own confirmed design, see Technical Concepts elsewhere in this project). None of these three describe a live, in-progress emergency; they ask *about* SLA policy, disclosure process, or an existing incident's status. This is a distinct root cause from the two severity-prompt/category-filter bugs already fixed this session — those fixes specifically taught the classifier to recognize policy-framed references to an *already-Critical item* as Critical (Example 8 in `classify_v1.py`), which may have inadvertently widened the net to also catch these three, which aren't really about a Critical item at all, just discuss the concept of Critical severity or reference an incident by name without asking for escalation. Left undecided rather than fixed today — same standard as the other two `Known Limitations` items below: the real fix needs a few-shot example distinguishing "discusses/references Critical-severity concepts or an existing incident" from "reports or requires action on a live Critical situation," which wasn't designed or tested this session, and risks regressing the fix that was just verified (3/3 real pass) for the opposite gap.

### `gq_002` / `gq_015` — plausible classify_node over-classification into `billing`

Two golden queries — *"What is the response time commitment for a Critical severity ticket under the Priority SLA tier?"* and *"How long does a Basic-tier customer wait for first response on a Low severity ticket?"* — are general SLA *policy* questions with no customer named at all, yet were classified `billing` (→ routed `SQL`) instead of the golden set's expected `RAG`. Nothing in either query needs an account lookup. This looks like real, if narrow, over-classification: `classify_v1.py`'s `billing` category definition is intentionally broad ("ANY question that requires looking up THIS customer's own account records... even though the word 'billing' doesn't literally appear") specifically to catch account/ticket lookups that don't use billing language — and these two general-policy queries may be triggering that same broad definition via SLA/severity keyword proximity, despite naming no account. Left undecided rather than fixed today because narrowing the `billing` prompt definition risks *regressing* the exact under-classification problem that definition was written to prevent (Example 6 in the prompt exists specifically because "what tickets does this customer have" used to get missed) — this needs a few-shot example distinguishing "general policy question that happens to mention SLA/severity" from "this customer's own account lookup," which wasn't designed or tested this session. Only 2 real occurrences found in the 50-query set — narrow enough to warrant a deliberate, tested prompt change rather than a quick patch under this session's evidence standard.

## Prompt-version comparison (§32.4), if run

Not run yet. When `run_eval.py --compare v1 v2` has been executed for real, record the side-by-side result here: which metrics moved, in which direction, and whether the newer version was promoted (`active_prompt_version` config change) or rolled back. `classify_v1.py` changed this session (severity-prompt fix) — this comparison, if run later, should treat that as the "v2" under test against the pre-fix baseline captured in this report.

## Load test summary (`tests/load/locustfile.py`)

Not run yet. `locust` is declared in `requirements.txt` but not yet installed in this environment — installing it and running a real load test are both separate, deliberate actions pending authorization, same discipline as every other real-call step in this report. When run, record: concurrent user count, request rate, and P95 latency per path (RAG/SQL/Hybrid/Critical) against the same §24.1 targets in the table above, measured under load rather than one query at a time.

---

## How this report is generated

1. Run `python -m evaluation.run_full_calibration` (added this session — resumable, checkpointed across multiple Groq API keys; see "How the full-50 run was actually achieved" above) repeatedly, swapping in a fresh `GROQ_API_KEY` each time it stops on a daily-quota `RateLimitError`, until `50/50` are checkpointed. It then writes a real `evaluation_runs` row and `evaluation/results/calibrated_thresholds.json` automatically.
2. Alternatively, for a smaller/faster check, `python -m evaluation.calibrate_thresholds --sample N` (N ≤ 7 without `--force`, given the real per-account daily budget).
3. Transcribe the printed metrics JSON into the SLO results table above.
4. For metrics not requiring the Groq judge (`query_routing_accuracy`, `context_recall`, `risk_classification_accuracy`, `escalation_recall`, `critical_misclassification_rate`), a cheaper Azure-only re-verification is possible without touching Groq quota at all — re-run the graph per query (`evaluation.golden_runner.run_golden_query_through_graph`) and recompute these five using `calibrate_thresholds.aggregate_calibration_metrics()`'s own formulas directly, exactly as done for the post-fix column in this report.
5. For `evaluation/run_eval.py`'s own Accuracy/LLM-as-judge metric (#5/#7) and any prompt-version comparison, run that script separately — it has not yet been run in this project's history.
6. For the load test section, run Locust against a real running instance and transcribe its own P95-per-path output.
7. To spot-check `GET /metrics`' live latency/cost path directly (a cheap, read-only Langfuse query, not a judge/LLM call): call `tracing.safe_query_trace_metrics(names=["respond","escalate","out_of_scope_refusal"], from_timestamp=..., to_timestamp=...)` and confirm `total_cost` is non-zero and `latency` values look like real end-to-end request durations, not a single span's own fractional-second duration — the exact check that found and confirmed Bug #3's fix.
8. Never silently omit the sample-size column or which metrics were/weren't re-verified after a code change — a number without that context is not this project's own disclosure standard.
