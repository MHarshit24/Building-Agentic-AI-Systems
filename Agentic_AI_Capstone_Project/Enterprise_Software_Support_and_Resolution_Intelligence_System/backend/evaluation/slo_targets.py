"""
evaluation/slo_targets.py

§24's SLO table, wired into real code for the first time — every target
number was previously a decision recorded only in planning discussion
(this project's own Blueprint.md, §24/§24.1), never an actual importable
constant. Confirmed directly before writing this: no LATENCY_TARGET (or
equivalent) existed anywhere in app/ or evaluation/ — the §24.1 decision
(≤2s for RAG/SQL/Hybrid, ≤3.5s carved out for Critical) was real and
approved but nowhere in the codebase. evaluation/run_eval.py and
tests/load/locustfile.py both need the SAME numbers; this module is the
one place either reads them from, so neither can silently drift out of
sync with a second hardcoded copy.

LATENCY_TARGET_SECONDS is keyed by `retrieval_mode` (§4's own enum:
"RAG"/"SQL"/"Hybrid"/"Critical") since that's the real field every graph
result already carries — no new classification needed to look up which
target applies to a given query.

The rest mirror §24's table directly, one constant per numbered metric
(kept as a flat dict, SLO_TARGETS, rather than one variable per metric,
so evaluation/run_eval.py's real-vs-target comparison and docs/
slo_evaluation_report.md's generation can both iterate it uniformly
instead of hand-listing every metric name twice).
"""

from __future__ import annotations

LATENCY_TARGET_SECONDS: dict[str, float] = {
    "RAG": 2.0,
    "SQL": 2.0,
    "Hybrid": 2.0,
    "Critical": 3.5,
}

# §24's numbered metrics, target value, and direction ("min" = target is a
# floor to clear, "max" = target is a ceiling not to exceed). Metric #4
# (Latency) and #7 (Cost per ticket) are deliberately NOT here — latency
# is keyed by retrieval_mode above (a single number wouldn't mean
# anything across four different path types), and cost/ticket is a
# production Langfuse-aggregate concern (GET /metrics), not something a
# golden-eval pass measures.
SLO_TARGETS: dict[str, dict] = {
    "faithfulness": {"target": 0.80, "direction": "min", "slo_number": 1},
    "answer_relevance": {"target": 0.75, "direction": "min", "slo_number": 2},
    "context_precision": {"target": 0.70, "direction": "min", "slo_number": 3},
    # #5 Accuracy and #7 LLM-as-judge — confirmed, not assumed, to be the
    # SAME real signal under two names (§24.2's own text: "Accuracy...
    # scored per §24.2" points at the identical independent-judge
    # mechanism §24.2 describes for #7; no second correctness mechanism
    # exists anywhere). One computed value, reported against both names;
    # the effective bar is the stricter of the two targets (0.85).
    "accuracy_llm_judge": {"target": 0.85, "direction": "min", "slo_number": "5/7"},
    "context_recall": {"target": 0.75, "direction": "min", "slo_number": 6},
    "task_success_rate": {"target": 0.90, "direction": "min", "slo_number": 8},
    "sql_correctness": {"target": 0.95, "direction": "min", "slo_number": 9},
    "source_attribution_rate": {"target": 1.00, "direction": "min", "slo_number": 10},
    "critical_misclassification_rate": {"target": 0.03, "direction": "max", "slo_number": 11},
    "escalation_recall": {"target": 1.00, "direction": "min", "slo_number": 12},
    "query_routing_accuracy": {"target": 0.95, "direction": "min", "slo_number": 15},
    "risk_classification_accuracy": {"target": 0.95, "direction": "min", "slo_number": 16},
}


def meets_target(metric_name: str, value: float | None) -> bool | None:
    """None if the metric is unknown or value is None (can't judge pass/
    fail on a metric that wasn't measured — e.g. sql_correctness when a
    sample had zero SQL-type queries), not a silent False."""
    if value is None or metric_name not in SLO_TARGETS:
        return None
    spec = SLO_TARGETS[metric_name]
    return value >= spec["target"] if spec["direction"] == "min" else value <= spec["target"]
