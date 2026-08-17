"""
evaluation/run_full_calibration.py

Resumable, checkpointed driver for a genuine full 50-query pass over
golden_queries/golden_50.json — a real, explicit request to complete the
whole golden set, not just a --sample subset.

Why this exists alongside calibrate_thresholds.py rather than just
passing it a bigger --sample: that script's run_calibration() is
deliberately all-or-nothing (see its own docstring) — it only persists
anything (the evaluation_runs row, calibrated_thresholds.json) once
EVERY query in the batch has been scored. Real, measured cost from this
project's own build: a single 10-query pass against llama-3.3-70b-
versatile consumed ~99,800 of a fresh account's 100,000 token/day
free-tier budget — so a genuine 50-query pass needs roughly 5x one
account's daily allowance. Without checkpointing, a run that dies
partway (which it will) loses ALL work, including the queries that DID
complete, every single time.

This script adds exactly the one thing missing: per-query checkpointing
to evaluation/results/full_calibration_checkpoint.json, written after
EVERY query (not per-batch), so a crash mid-run — expected, not a bug,
whenever the current Groq key's daily budget runs out — loses at most
the one query in flight. Re-running this script (after swapping in a
fresh GROQ_API_KEY) skips every query_id already checkpointed and
continues with whatever's left, until all 50 are done.

The checkpoint stores a MINIMAL, JSON-safe projection of each query's
evaluate_golden_query() result — only the fields calibrate_thresholds.
aggregate_calibration_metrics() actually reads (confidence_score,
retrieval_mode, escalation_flag, correct, effective_severity,
ragas_scores), not the full graph_result (which holds Pydantic
RetrievedChunk/RetrievedTable/RetrievedDiagram objects and isn't
directly JSON-serializable). Once all 50 ids are checkpointed, this
calls aggregate_calibration_metrics() itself (reused, not reimplemented,
so threshold-search/accuracy logic lives in exactly one place) and
writes ONE real, final EvaluationRun row (sample_size=50) plus
evaluation/results/calibrated_thresholds.json reflecting the true
full-corpus result.

Azure graph calls (golden_runner.run_golden_query_through_graph) are
NOT gated by any of this — they're a separate quota (Azure OpenAI, not
Groq) untouched by the Groq daily cap this script works around.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict
from pathlib import Path

from evaluation import golden_runner
from evaluation.calibrate_thresholds import (
    _MIN_CALIBRATION_SAMPLE_SIZE,
    aggregate_calibration_metrics,
    evaluate_golden_query,
    write_calibrated_thresholds,
    write_evaluation_run,
)
from evaluation import groq_judge_client as judge_client_module
from evaluation.groq_judge_client import RatePacer

_CHECKPOINT_PATH = Path(__file__).resolve().parent / "results" / "full_calibration_checkpoint.json"


def _load_checkpoint() -> dict:
    if _CHECKPOINT_PATH.exists():
        return json.loads(_CHECKPOINT_PATH.read_text(encoding="utf-8"))
    return {}


def _save_checkpoint(checkpoint: dict) -> None:
    _CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CHECKPOINT_PATH.write_text(json.dumps(checkpoint, indent=2), encoding="utf-8")


def _minimal_record(result: dict) -> dict:
    """Projects a real evaluate_golden_query() result down to exactly
    the fields aggregate_calibration_metrics() reads, PLUS the full
    correctness audit trail (correctness_audit's extracted facts and
    per-fact verdicts) — aggregation itself never reads the audit trail,
    but a real, confirmed gap this closes: an earlier version of this
    checkpoint kept only the final correct bool, so a later investigation
    into a surprising "incorrect" verdict had no way to see what was
    actually extracted/checked without spending a fresh, real judge call
    to reproduce it — 13 of 19 such cases in this project's own history
    were left un-auditable this way. Kept here specifically so that
    doesn't happen again."""
    graph_result = result["graph_result"]
    audit = result.get("correctness_audit")
    return {
        "confidence_score": graph_result.get("confidence_score"),
        "retrieval_mode": graph_result.get("retrieval_mode"),
        "escalation_flag": graph_result.get("escalation_flag"),
        "correct": result["correct"],
        "effective_severity": result["effective_severity"],
        "ragas_scores": result["ragas_scores"],
        "correctness_audit": asdict(audit) if audit is not None else None,
    }


def _expand_record(record: dict) -> dict:
    """Inverse of _minimal_record() — rebuilds just enough of the shape
    aggregate_calibration_metrics() expects (a "graph_result" dict with
    the 3 keys it actually calls .get() on)."""
    return {
        "graph_result": {
            "confidence_score": record["confidence_score"],
            "retrieval_mode": record["retrieval_mode"],
            "escalation_flag": record["escalation_flag"],
        },
        "correct": record["correct"],
        "effective_severity": record["effective_severity"],
        "ragas_scores": record["ragas_scores"],
    }


def _print_status(checkpoint: dict, all_queries: list[dict]) -> None:
    done = len(checkpoint)
    total = len(all_queries)
    remaining = [q["id"] for q in all_queries if q["id"] not in checkpoint]
    print(f"{done}/{total} golden queries checkpointed.")
    if remaining:
        print(f"Remaining ({len(remaining)}): {', '.join(remaining)}")
    else:
        print("All queries checkpointed — re-run without --status to write the final aggregate.")


async def _run(*, status_only: bool) -> None:
    all_queries = golden_runner.load_golden_queries()  # full 50, file order
    checkpoint = _load_checkpoint()

    if status_only:
        _print_status(checkpoint, all_queries)
        return

    remaining = [q for q in all_queries if q["id"] not in checkpoint]
    if not remaining:
        print("All 50 golden queries already checkpointed — writing final aggregate.")
    else:
        print(f"{len(checkpoint)}/{len(all_queries)} already done. Resuming with {len(remaining)} remaining.")
        pacer = RatePacer()
        for query_entry in remaining:
            try:
                result = await evaluate_golden_query(query_entry, judge=judge_client_module, pacer=pacer)
            except Exception as exc:
                print(
                    f"\nStopped at {query_entry['id']} after {len(checkpoint)}/{len(all_queries)} "
                    f"queries this run: {exc}\n"
                    "Progress is saved. Swap in a fresh GROQ_API_KEY and re-run this script to continue."
                )
                return
            checkpoint[query_entry["id"]] = _minimal_record(result)
            _save_checkpoint(checkpoint)
            print(f"  done: {query_entry['id']} ({len(checkpoint)}/{len(all_queries)})")

    # Only reached once every query_entry has a checkpoint entry.
    per_query_results = [_expand_record(checkpoint[q["id"]]) for q in all_queries]
    metrics = aggregate_calibration_metrics(all_queries, per_query_results)
    await write_evaluation_run(len(all_queries), metrics)
    print(json.dumps(metrics, indent=2))

    if len(all_queries) < _MIN_CALIBRATION_SAMPLE_SIZE:
        print(f"\nNOT writing calibrated_thresholds.json: below the minimum sample size.")
        return
    write_calibrated_thresholds(metrics["calibrated_high_threshold"], metrics["calibrated_medium_threshold"])
    print("\nWrote a full, real 50-query evaluation_runs row and calibrated_thresholds.json.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Resumable full 50-query golden-eval pass, checkpointed across multiple Groq API keys."
    )
    parser.add_argument(
        "--status", action="store_true", help="Report checkpoint progress without making any real calls."
    )
    args = parser.parse_args()
    asyncio.run(_run(status_only=args.status))
