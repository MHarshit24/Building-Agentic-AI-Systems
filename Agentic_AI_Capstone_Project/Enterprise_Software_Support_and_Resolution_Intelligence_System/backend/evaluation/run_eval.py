"""
evaluation/run_eval.py

Stage 9's L4 harness (§19, §25) — orchestrates the full golden-eval SLO
measurement pass. Reuses evaluation/calibrate_thresholds.py's
evaluate_golden_query() (the one shared per-query pipeline: real graph
run, judge correctness, RAGAS scoring, Langfuse score attachment) rather
than re-running any real call a second time, and that module's
aggregate_calibration_metrics() (threshold search, routing/risk/
escalation/critical/SQL accuracy) rather than duplicating that
bookkeeping — see calibrate_thresholds.py's own docstring for why that
split exists (a real circular-import constraint ruled out a third shared
module; this file imports both functions directly).

What this adds beyond calibrate_thresholds.py, confirmed as real,
previously-missing gaps during Stage 9 planning:

  1. Per-query LATENCY, measured directly (wall-clock around
     evaluate_golden_query()) against evaluation/slo_targets.py's real,
     named per-retrieval_mode targets (§24.1's decision — ≤2s for
     RAG/SQL/Hybrid, ≤3.5s for Critical — wired into an actual importable
     constant for the first time; confirmed nothing like it existed
     anywhere in the codebase before this). Nothing in calibrate_
     thresholds.py times a query at all.
  2. SOURCE ATTRIBUTION RATE (§24 metric #10) — graph_result["sources"]
     and ["groundedness_flag"] both already exist (confirmed by reading
     app/orchestration/nodes/respond.py directly); nobody was computing
     this ratio anywhere before now.
  3. The raw ACCURACY / LLM-AS-JUDGE mean (§24 metrics #5 and #7) —
     confirmed these are the SAME real signal under two names (§24.2's
     own text: "Accuracy... scored per §24.2" points at the identical
     independent-judge mechanism §24.2 describes for #7; no second
     correctness mechanism exists anywhere), distinct from TSR's
     threshold-gated derivative. The un-gated mean of `correct` across
     all evaluated queries was computed internally by calibrate_
     thresholds.py's threshold search but never itself surfaced as a
     reported number — it is here, under one key covering both names.
  4. PROMPT-VERSION COMPARISON (§32.4) — run the same golden sample
     against two values of active_prompt_version and report both results
     side by side, now possible since app/prompts/loader.py's dynamic
     per-agent version resolution exists. Two full real passes, not one
     — the caller's --sample choice should account for double the real
     call cost (preflight_check below is called against sample*2 when
     comparing, not sample).

--sample is the same permanent, disclosed-in-the-report operating mode
already established for calibrate_thresholds.py/ragas_metrics.py — a
full 50-query pass stays impractical on the current judge tier
regardless of how much Stage 9 tuning time passes (see groq_judge_
client.py's own real call-volume analysis). Every number this module
reports must be read alongside its real sample size — docs/
slo_evaluation_report.md's generation step is expected to state this
explicitly per metric, not just once in a preamble.

Output is a JSON report file (evaluation/results/run_eval_report.json),
not a second app.db.models.EvaluationRun row — this module's new metrics
(latency_by_mode, source_attribution_rate, accuracy_llm_judge) have no
columns in that table, and extending its schema wasn't asked for as part
of this build; a disclosed, deliberate scope choice, not an oversight.
docs/slo_evaluation_report.md's own generation step is expected to read
this file.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path
from typing import Any

from app.config import get_settings
from evaluation import golden_runner
from evaluation import groq_judge_client as judge_client_module
from evaluation.calibrate_thresholds import aggregate_calibration_metrics, evaluate_golden_query
from evaluation.groq_judge_client import RatePacer, preflight_check
from evaluation.slo_targets import LATENCY_TARGET_SECONDS, SLO_TARGETS, meets_target

_RESULTS_PATH = Path(__file__).resolve().parent / "results" / "run_eval_report.json"


async def _timed_evaluate(query_entry: dict, *, judge: Any, pacer: RatePacer | None) -> dict:
    """evaluate_golden_query() plus wall-clock latency and Source
    Attribution Rate — the two additions calibrate_thresholds.py's own
    per-query loop has no reason to compute (they're SLO-report concerns,
    not calibration concerns)."""
    start = time.monotonic()
    result = await evaluate_golden_query(query_entry, judge=judge, pacer=pacer)
    elapsed = time.monotonic() - start

    graph_result = result["graph_result"]
    retrieval_mode = graph_result.get("retrieval_mode") or "RAG"
    target = LATENCY_TARGET_SECONDS.get(retrieval_mode, LATENCY_TARGET_SECONDS["RAG"])

    sources = graph_result.get("sources") or []
    source_attribution_ok = bool(sources) and bool(graph_result.get("groundedness_flag"))

    return {
        **result,
        "latency_seconds": elapsed,
        "retrieval_mode": retrieval_mode,
        "latency_target_seconds": target,
        "latency_met_target": elapsed <= target,
        "source_attribution_ok": source_attribution_ok,
    }


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    k = (len(ordered) - 1) * pct
    lower = int(k)
    upper = min(lower + 1, len(ordered) - 1)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (k - lower)


def _latency_summary(per_query_results: list[dict]) -> dict:
    """P50/P95 broken down PER retrieval_mode, never one blended number
    — RAG/SQL/Hybrid/Critical carry genuinely different targets (§24.1),
    so a single overall percentile would hide exactly the path (Critical)
    §24.1's own text says needs the closest watching."""
    by_mode: dict[str, list[float]] = {}
    for r in per_query_results:
        by_mode.setdefault(r["retrieval_mode"], []).append(r["latency_seconds"])

    summary = {}
    for mode, values in by_mode.items():
        target = LATENCY_TARGET_SECONDS.get(mode, LATENCY_TARGET_SECONDS["RAG"])
        p95 = _percentile(values, 0.95)
        summary[mode] = {
            "n": len(values),
            "p50_seconds": _percentile(values, 0.50),
            "p95_seconds": p95,
            "target_seconds": target,
            "p95_meets_target": (p95 <= target) if p95 is not None else None,
        }
    return summary


async def run_eval(sample: int, *, judge: Any = judge_client_module, prompt_version: str | None = None) -> dict:
    """The full Stage 9 SLO measurement pass over `sample` golden
    queries. If prompt_version is given, temporarily overrides
    active_prompt_version for the duration (§32.4 comparison mode) —
    restored afterward regardless of outcome, via try/finally, so a
    failed pass can never leave the process running a different prompt
    version than it started with."""
    settings = get_settings()
    original_version = None
    if prompt_version is not None:
        original_version = settings.active_prompt_version
        settings.active_prompt_version = prompt_version

    try:
        queries = golden_runner.load_golden_queries(sample=sample)
        pacer = RatePacer()
        per_query_results = [await _timed_evaluate(q, judge=judge, pacer=pacer) for q in queries]
    finally:
        if prompt_version is not None:
            settings.active_prompt_version = original_version

    calibration_metrics = aggregate_calibration_metrics(queries, per_query_results)

    n = len(per_query_results)
    accuracy_llm_judge = (sum(1.0 if r["correct"] else 0.0 for r in per_query_results) / n) if n else None
    source_attribution_rate = (
        (sum(1.0 if r["source_attribution_ok"] else 0.0 for r in per_query_results) / n) if n else None
    )

    metrics = {
        **calibration_metrics,
        "accuracy_llm_judge": accuracy_llm_judge,
        "source_attribution_rate": source_attribution_rate,
        "latency_by_mode": _latency_summary(per_query_results),
        "sample_size": n,
        "prompt_version": prompt_version or settings.active_prompt_version,
    }
    metrics["slo_status"] = {name: meets_target(name, metrics.get(name)) for name in SLO_TARGETS if name in metrics}
    return metrics


async def compare_prompt_versions(
    sample: int, version_a: str, version_b: str, *, judge: Any = judge_client_module
) -> dict:
    """§32.4's actual comparison workflow: the SAME golden sample against
    two prompt versions, side by side — TWO full real passes, twice the
    real judge/graph-call cost of a single run_eval() call. The caller
    (see _main's preflight_check call below) must account for this;
    it is not free just because it reuses evaluate_golden_query()."""
    result_a = await run_eval(sample, judge=judge, prompt_version=version_a)
    result_b = await run_eval(sample, judge=judge, prompt_version=version_b)
    return {"version_a": version_a, "version_b": version_b, "results_a": result_a, "results_b": result_b}


def write_report(result: dict) -> None:
    _RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    _RESULTS_PATH.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")


async def _main(sample: int, *, force: bool, compare: tuple[str, str] | None) -> None:
    preflight_check(sample * (2 if compare else 1), force=force)
    result = await compare_prompt_versions(sample, compare[0], compare[1]) if compare else await run_eval(sample)
    write_report(result)
    print(json.dumps(result, indent=2, default=str))
    print(f"\nWrote {_RESULTS_PATH}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the full Stage 9 SLO evaluation pass against golden_50.json.")
    parser.add_argument(
        "--sample", type=int, default=10,
        help="Number of golden queries to run (default 10 — see groq_judge_client.py's own "
        "call-volume analysis for why a full 50-query pass isn't practically feasible).",
    )
    parser.add_argument(
        "--compare", nargs=2, metavar=("VERSION_A", "VERSION_B"),
        help="Compare two prompt versions side by side (§32.4), e.g. --compare v1 v2. "
        "Runs the full sample TWICE — real call cost doubles.",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Skip the preflight call-count safety ceiling (deliberate override, never a default).",
    )
    args = parser.parse_args()
    asyncio.run(_main(args.sample, force=args.force, compare=tuple(args.compare) if args.compare else None))
