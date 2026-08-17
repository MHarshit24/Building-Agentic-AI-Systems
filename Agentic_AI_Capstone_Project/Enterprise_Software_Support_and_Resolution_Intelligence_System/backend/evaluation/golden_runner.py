"""
evaluation/golden_runner.py

Shared helper for evaluation/ragas_metrics.py and evaluation/
calibrate_thresholds.py — both need to run golden_queries/golden_50.json
through the real graph (real LLM_PROVIDER=azure, real hybrid_search) and
would otherwise duplicate the same initial_state construction and
graph.ainvoke() call. Lives in its own module (not inside either script)
specifically so neither script has to import the other — calibrate_
thresholds.py separately imports ragas_metrics.py's scorer functions, so
a circular import would result if the graph-running logic lived in
either of them instead of here.

customer_id assumption, disclosed rather than silently guessed:
golden_50.json's schema (confirmed, §24.4) has no customer_id label at
all, and several SQL-category golden queries reference a customer by
name or ask an aggregate question ("List all Critical severity support
tickets") that app/sql_tools/queries.py's actual customer_id-scoped
functions don't support querying that way. This runner defaults every
query to customer_id=1 (the course dataset's first seeded customer) —
a reasonable, simple choice for exercising the graph end-to-end, but a
real, disclosed limitation: some golden SQL queries may not grade
meaningfully against this graph's current customer_id-scoped SQL tool
design regardless of which customer_id is chosen. Out of scope to fix
here — that's a product-design question for the SQL agent/golden set
alignment, not this stage's job.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from app.observability import tracing
from app.orchestration.graph import GRAPH_RECURSION_LIMIT, graph

_GOLDEN_PATH = Path(__file__).resolve().parents[1] / "golden_queries" / "golden_50.json"

DEFAULT_CUSTOMER_ID = 1


def _stratified_sample(queries: list[dict], sample: int) -> list[dict]:
    """Draws `sample` entries spread across every query_type category
    present, rather than the first `sample` entries in file order.

    Real bug this fixes, confirmed by reading golden_50.json directly:
    the file is strictly block-ordered (Documentation x15, then SQL x10,
    Hybrid x10, High-Severity x10, Escalation x5) — a plain queries[:N]
    slice draws EXCLUSIVELY from the Documentation block for any N <= 15,
    which includes every --sample value this project's own feasibility
    analysis has established as affordable (5-10, see groq_judge_client.py)
    and the calibration minimum (10, see calibrate_thresholds.py's
    _MIN_CALIBRATION_SAMPLE_SIZE). incident_severity_node never runs for
    a Documentation-category query, so risk_classification_accuracy/
    query_routing_accuracy's SQL/Hybrid/Critical/Escalation coverage was
    structurally absent at every realistic --sample size, not just an
    edge case.

    Algorithm: every category present gets at least 1 slot (if `sample`
    is large enough to cover them all); remaining slots are distributed
    proportionally to each category's real size using the largest-
    remainder method (so a 50-query set's 15/10/10/10/5 split is
    approximated, not ignored, once every category has its guaranteed
    minimum). If `sample` is smaller than the number of categories, one
    slot goes to as many categories as fit, in the golden set's own fixed
    block order — `sample=1` still returns exactly the first Documentation
    entry (gq_001), unchanged from the old behavior, since that's the
    query this project's first real judge-model test already ran against.
    Within a category, the first N entries (file order) are taken —
    deterministic and consistent with how this function always sampled,
    just scoped per-category now instead of globally."""
    if sample >= len(queries):
        return queries

    category_order: list[str] = []
    by_category: dict[str, list[dict]] = {}
    for q in queries:
        cat = q["query_type"]
        if cat not in by_category:
            by_category[cat] = []
            category_order.append(cat)
        by_category[cat].append(q)

    num_categories = len(category_order)
    counts = {c: 0 for c in category_order}

    if sample <= num_categories:
        for c in category_order[:sample]:
            counts[c] = 1
    else:
        for c in category_order:
            counts[c] = 1
        remaining_slots = sample - num_categories
        remaining_sizes = {c: len(by_category[c]) - 1 for c in category_order}
        total_remaining_size = sum(remaining_sizes.values())

        if total_remaining_size > 0 and remaining_slots > 0:
            ideal = {c: remaining_slots * remaining_sizes[c] / total_remaining_size for c in category_order}
            extra = {c: min(int(ideal[c]), remaining_sizes[c]) for c in category_order}
            leftover = remaining_slots - sum(extra.values())

            by_remainder = sorted(category_order, key=lambda c: ideal[c] - int(ideal[c]), reverse=True)
            for c in by_remainder:
                if leftover <= 0:
                    break
                if extra[c] < remaining_sizes[c]:
                    extra[c] += 1
                    leftover -= 1

            for c in category_order:
                counts[c] += extra[c]

    selected: list[dict] = []
    taken = {c: 0 for c in category_order}
    for q in queries:
        cat = q["query_type"]
        if taken[cat] < counts[cat]:
            selected.append(q)
            taken[cat] += 1
    return selected


def load_golden_queries(sample: int | None = None) -> list[dict]:
    """Loads golden_50.json's `queries` list. `sample=N` returns a
    STRATIFIED sample of N entries spread across every query_type
    category present (see _stratified_sample's own docstring for why
    file-order slicing was a real bug, not a style choice) — the
    --sample safety mechanism (see groq_judge_client.py's call-volume/
    rate-limit feasibility analysis): a full 50-query pass risks
    exceeding Groq's real daily token cap for the independent judge, so
    proving the mechanics work against a representative handful of
    queries first is a real, required step, not just convenient."""
    with open(_GOLDEN_PATH, encoding="utf-8") as f:
        data = json.load(f)
    queries = data["queries"]
    if sample is not None:
        return _stratified_sample(queries, sample)
    return queries


async def run_golden_query_through_graph(query_entry: dict, *, customer_id: int = DEFAULT_CUSTOMER_ID) -> dict:
    """Runs one golden_50 entry through the real, compiled graph
    end-to-end and returns the full result dict (retrieved_chunks/
    tables/diagrams, sql_results, final_answer, category, severity_final,
    retrieval_mode, confidence_score/tier, escalation_flag, ...) — the
    same shape routes_chat.py builds a ChatResponse from, just returned
    raw here since eval code needs the full state, not the trimmed
    public API response shape.

    Uses the module-level `graph` singleton (no checkpointer) — eval runs
    are one-shot, standalone script invocations with no need for
    mid-request crash recovery (§40's checkpointer exists for the real
    request-serving app, not this)."""
    trace_id = tracing.safe_create_trace_id()
    initial_state = {
        "query": query_entry["query"],
        "chat_history": [],
        "customer_id": customer_id,
        "handled_by_user_id": 1,
        "category": None,
        "conversation_id": str(uuid.uuid4()),
        "severity_initial": None,
        "severity_final": None,
        "retrieval_mode": None,
        "explicit_human_request": False,
        "retrieved_chunks": [],
        "retrieved_tables": [],
        "retrieved_diagrams": [],
        "sql_results": [],
        "confidence_score": None,
        "confidence_tier": None,
        "groundedness_flag": None,
        "retrieval_retry_count": 0,
        "reflection_loopback_count": 0,
        "escalation_flag": False,
        "flagged_for_review": False,
        "notification_sent": False,
        "escalation_reason": None,
        "human_handoff_summary": None,
        "final_answer": None,
        "sources": [],
        "trace_id": trace_id,
    }
    result = await graph.ainvoke(
        initial_state,
        config={"recursion_limit": GRAPH_RECURSION_LIMIT, "configurable": {"thread_id": trace_id}},
    )
    tracing.safe_flush()
    return result
