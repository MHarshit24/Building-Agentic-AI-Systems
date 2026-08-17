"""
evaluation/calibrate_thresholds.py

§6 / §25: recalibrates the confidence-tier High/Medium cutoffs from real
golden-eval results, rather than trusting the starting 0.85/0.70 values
forever. Re-runnable anytime new golden data arrives (§25's own explicit
requirement) — a plain script, safe to run again and again, matching
§22's "fully dynamic system, no one-time scripts" framing the same way
scripts/seed_synthetic_data.py already is.

The "full pass" driver: runs golden_50.json through the real graph ONCE
per query (via evaluation/golden_runner.py) and feeds the same results to
BOTH its own threshold search AND evaluation/ragas_metrics.py's scorer
functions, so the expensive real graph run only happens once per
evaluation pass, not twice across two separate scripts. Writes a single
combined app.db.models.EvaluationRun row plus evaluation/results/
calibrated_thresholds.json (config.py's own override mechanism — see
that file's _apply_calibrated_thresholds()), never a .env rewrite or a
source-code edit.

_MIN_CALIBRATION_SAMPLE_SIZE (below) gates the SECOND of those writes,
not the first: a real --sample 1 run (confirmed directly — the first
real run against llama-3.3-70b-versatile) completed the mechanics
end-to-end and wrote a genuine evaluation_runs row, but its search result
({"high": 0.95, "medium": 0.55}) reflected a single query with no
incorrect example to weigh against — not a real calibration signal, and
not something that should silently become the live production threshold
override on the next process restart. Below the minimum, the script
still runs and still records the evaluation_runs row, but does not touch
calibrated_thresholds.json unless --allow-small-sample is passed
explicitly.

Threshold search — how it actually works: confidence-tier cutoffs only
affect ONE thing structurally (app/orchestration/nodes/router.py's
decide_action(), §6.1) — whether a non-Critical-severity query
auto-responds or escalates on confidence alone. Critical severity always
escalates regardless of confidence (decide_action's own first check), so
critical-misclassification (a SEVERITY-classification concern, unrelated
to confidence tier) is computed once as an informational sanity check,
not searched over — no candidate threshold pair can change it. Task
Success Rate IS threshold-sensitive, so it's what the grid search
actually optimizes: for each candidate (high, medium) pair, a Low-tier
(or Critical-severity) query is treated as a safe outcome (escalating is
never "wrong"); a High/Medium-tier query counts as a success only if the
independent judge scored its answer correct. The pair with the highest
resulting TSR wins; ties prefer higher thresholds (less over-escalation,
per §6's own "without over-escalating" framing).

--sample (5-10 queries) is the permanent, intended operating mode for
this script too, not a temporary workaround — this driver's own
compute_correctness() calls count against the exact same daily token
budget as evaluation/ragas_metrics.py's scorers (see that module's
docstring for the full real-call evidence and the current judge model,
llama-3.3-70b-versatile — a full 50-query run is still not practically
feasible on this tier, ~5x over its 100K daily token cap even after
switching away from the original, more expensive judge model). Real
alternatives (a paid tier, a different judge model, or a hard per-query
judge-call cap) are named there, not decided here.

compute_correctness() below is DECOMPOSED, not a single holistic call —
same reasoning as evaluation/ragas_metrics.py's compute_faithfulness():
the judge model has no internal reasoning/thinking phase, so asking it
to hold an entire ground_truth_answer and final_answer in mind and reach
one holistic "correct or not" verdict in a single pass is exactly the
kind of compound, multi-fact judgment a non-reasoning model can get
partly wrong (confirm one fact, silently miss another, still assert
"correct" overall). See compute_correctness()'s own docstring for the
full argument and the aggregation rule chosen.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.config import get_settings
from app.db.models import EvaluationRun
from app.db.session import async_session_maker
from app.llm.structured_output import call_llm_structured
from app.observability import tracing
from app.orchestration.nodes.router import resolve_effective_severity
from app.prompts._shared import INJECTION_DEFENSE_CLAUSE, JSON_ONLY_CLAUSE
from evaluation import golden_runner, ragas_metrics
from evaluation.groq_judge_client import RatePacer, preflight_check
from evaluation import groq_judge_client as judge_client_module
from evaluation.ragas_metrics import EXTRACTION_MAX_TOKENS, VERIFICATION_MAX_TOKENS

_RESULTS_PATH = Path(__file__).resolve().parent / "results" / "calibrated_thresholds.json"

_MIN_CALIBRATION_SAMPLE_SIZE = 10
# Real, confirmed problem this guards against: a run with too few queries
# can trivially "succeed" without measuring anything. Concretely
# demonstrated by tests/unit/test_threshold_tiers.py's own
# test_all_correct_prefers_highest_threshold_pair_on_tie -- when every
# record is correct (or, symmetrically, all incorrect), EVERY candidate
# (high, medium) pair ties at the same TSR, and the result degenerates to
# whichever threshold the tie-break rule happens to favor rather than a
# genuine signal from the data. A real calibration run needs both correct
# AND incorrect examples actually represented to produce a search result
# that means anything. 10 is chosen as the upper end of the --sample
# 5-10 range already established as comfortably affordable against
# Groq's real daily token cap (see groq_judge_client.py) -- the largest
# sample size this judge model's free tier can sustain routinely, not an
# arbitrary round number.
#
# A SEPARATE limitation this guard alone would not have fixed, now fixed
# at its actual source instead: golden_queries/golden_50.json is strictly
# block-ordered by category (Documentation x15, then SQL x10, Hybrid x10,
# High-Severity x10, Escalation x5), and golden_runner.load_golden_queries
# used to take the first N entries in file order -- meaning any --sample
# <= 15, this guard's own minimum included, drew exclusively from the
# Documentation block, where incident_severity_node never runs (§3:
# conditional on incident/security/Critical), so severity_final was None
# for every record and risk_classification_accuracy/query_routing_accuracy
# never saw SQL/Hybrid/Critical/Escalation coverage at any realistic
# --sample size. Fixed in golden_runner.py itself (_stratified_sample) --
# load_golden_queries(sample=N) now draws proportionally across every
# category present, so this guard's own job stays narrowly scoped to what
# it was always meant to guard: the threshold search's correct/incorrect
# representation, not category coverage (that's golden_runner.py's job
# now, not this constant's).
#
# Below this minimum, _main() still runs the full calibration end-to-end
# (proving the mechanics work — e.g. --sample 1 smoke-testing) and still
# writes an evaluation_runs row (a real, if small-sample, historical
# record), but does NOT write calibrated_thresholds.json — the one file
# get_settings() applies as a genuine production override — unless
# --allow-small-sample is passed explicitly (never a default).

# A small grid, not an exhaustive search — coarse enough to be fast and
# cheap on judge calls (the search itself makes zero extra judge calls;
# it only re-buckets already-collected (confidence_score, correct) pairs
# under each candidate), fine enough to meaningfully move the cutoffs.
_HIGH_CANDIDATES = [0.75, 0.80, 0.85, 0.90, 0.95]
_MEDIUM_CANDIDATES = [0.55, 0.60, 0.65, 0.70, 0.75]

_MAX_FACTS_TO_VERIFY = 5
# Same rationale as evaluation/ragas_metrics.py's _MAX_CLAIMS_TO_VERIFY —
# bounds this decomposed judgment's cost regardless of how many facts a
# ground_truth_answer happens to bundle together. Kept as its own,
# separately-tunable constant (not imported from ragas_metrics) since the
# two caps apply to conceptually distinct extractions (final_answer's
# claims vs. ground_truth_answer's facts) that happen to share a value
# today, not a coupled one.


class _FactExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    facts: list[str]


class _FactConfirmation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirmed: bool


@dataclass
class CorrectnessAudit:
    """Full audit trail for one compute_correctness() call — not just the
    final bool. Real, confirmed gap this closes: the original full-50-
    query run's checkpoint only ever persisted the final `correct` bool,
    so investigating a surprising "incorrect" verdict later required a
    brand-new, real judge call just to see what was actually extracted
    and checked — 13 of 19 such cases in this project's own history
    couldn't be audited at all without spending fresh Groq quota on a
    call that had already been made once and thrown away. This struct is
    threaded through evaluate_golden_query()'s own return dict and
    persisted verbatim in evaluation/run_full_calibration.py's
    checkpoint, so a future investigation reads real historical data
    instead of needing to reproduce the call."""

    correct: bool
    extracted_facts: list[str]
    fact_verdicts: list[dict]  # [{"fact": str, "confirmed": bool}, ...] — one entry per fact actually checked


async def compute_correctness(
    query: str, ground_truth_answer: str, final_answer: str, *, judge: Any, pacer: RatePacer | None = None
) -> CorrectnessAudit:
    """Reused both for Task Success Rate's per-query outcome and, filtered
    to query_type=="SQL" entries, as this run's SQL Correctness figure.

    DECOMPOSED, not a single holistic call — the judge model
    (llama-3.3-70b-versatile) has no internal reasoning/thinking phase,
    so a single "is this correct?" call asking it to implicitly compare
    every fact in ground_truth_answer against final_answer in one pass is
    exactly the kind of compound judgment a non-reasoning model can
    silently get partly wrong (confirm one fact, miss another, still
    assert an overall verdict). Instead: extract the atomic facts
    asserted in ground_truth_answer (reversed direction from
    ragas_metrics.compute_faithfulness(), which extracts from
    final_answer instead), then verify each fact individually against
    final_answer — one call, one fact, one yes/no, same atomic-
    decomposition shape as every other judge call in this project.

    Aggregation is deterministic in code, not a further model judgment:
    correct=True iff ALL extracted facts are confirmed (unanimous, not
    majority) — a deliberate, named threshold choice. golden_50.json's
    ground_truth_answer entries are already concise/canonical (1-3 core
    facts, no padding), so requiring every one of them to be present is a
    reasonably strict bar, not an arbitrarily harsh one; a majority
    threshold would also be defensible, unanimous is what's implemented.
    If ground_truth_answer yields no extractable facts (degenerate case),
    treated as vacuously correct (True) — mirrors compute_faithfulness's
    same-shaped vacuous case. Same evenly-spaced sampling as
    compute_faithfulness if extraction returns more than
    _MAX_FACTS_TO_VERIFY facts, for the same reason: avoid bias toward
    facts mentioned early in the ground-truth answer.

    Extraction is scoped to the query, not the whole ground_truth_answer —
    a real, confirmed bug fixed here, not a precaution: golden_50.json's
    ground_truth_answer entries sometimes bundle extra context beyond
    what the query literally asked (e.g. gq_013 asks only "What
    PostgreSQL and Redis versions are required" but its ground truth
    also names required Node.js/Python versions as surrounding context).
    The original prompt extracted every factual claim in the ground
    truth regardless of relevance, so a fully correct, well-scoped real
    answer that correctly omitted the tangential facts still failed the
    unanimous-confirmation check on those facts alone — confirmed
    directly against real answers for gq_007/gq_013, both of which
    scored faithfulness=1.0 (nothing hallucinated) yet correct=False
    under the old prompt. The extraction prompt below now explicitly
    scopes extraction to facts that are part of the direct answer to the
    query, not everything the ground truth happens to mention.

    No short-circuit on the first unconfirmed fact (a deliberate change
    from an earlier version of this function): every fact in
    facts_to_check is now verified, and CorrectnessAudit.fact_verdicts
    records all of them, not just however many were checked before an
    early exit. Costs marginally more judge calls in the case where an
    early fact fails (up to _MAX_FACTS_TO_VERIFY regardless), but a
    partial audit trail defeats the entire point of persisting one —
    the real problem the missing-audit-trail gap caused (13 of 19
    "unexplained" low-correctness queries in this project's own history
    being un-auditable without spending fresh judge quota) is worse than
    a few extra calls.

    Disjunctive ground-truth claims are extracted as ONE fact, not split
    per alternative — a second real, confirmed bug fixed here, found via
    the audit trail the fix above enables: gq_013's ground truth states
    "PostgreSQL 14.x or 15.x" (either version satisfies the requirement).
    The original prompt split this into two independent facts ("14.x is
    required" and "15.x is required"), and a real answer that correctly
    stated the full "14.x or 15.x" alternative still failed the unanimous
    check, because the verification call for "15.x is required" (asked
    in isolation) correctly says no — the answer doesn't claim 15.x is
    *the* requirement, only that it's *a* valid option. Zero-cost scan of
    golden_50.json found this is a systemic pattern, not a one-off: ~4-8
    of 50 ground_truth_answer entries state alternative-satisfies-one-
    requirement claims of this shape. The extraction prompt now
    explicitly keeps a stated alternative as one atomic fact (preserving
    the "A or B" wording), so verification checks whether the answer
    states the full alternative, not whether it independently asserts
    each option as its own separate requirement."""
    extract_prompt = (
        f"{INJECTION_DEFENSE_CLAUSE}\n\n{JSON_ONLY_CLAUSE}\n\n"
        "Extract the atomic factual claims made in the EXPECTED ANSWER below that are PART "
        "OF THE DIRECT ANSWER TO THE QUERY (each fact a short, standalone sentence). The "
        "expected answer may include extra context or tangential details beyond what the "
        "query itself asked for — do NOT extract those; only extract facts that a correct, "
        "well-scoped answer to the query would need to state.\n\n"
        "If the expected answer states that EITHER of two or more alternatives satisfies "
        "the same requirement (e.g. \"version 14 or 15 is required\", \"any of X, Y, or Z "
        "qualifies\"), extract that as ONE SINGLE fact preserving the full alternative "
        "(e.g. \"version 14 or 15 is required\"), not as separate facts for each option — "
        "an answer that correctly states the full alternative should not be penalized for "
        "not separately re-asserting each option as independently, individually required.\n\n"
        "If it makes no such facts, return an empty list.\n\n"
        f"Query: {query}\n\nExpected answer: {ground_truth_answer}\n\n"
        f'Schema: {{"facts": ["fact 1", "fact 2", ...]}}'
    )
    if pacer is not None:
        await pacer.wait()
    extraction = await call_llm_structured(
        extract_prompt, _FactExtraction, client=judge, max_tokens=EXTRACTION_MAX_TOKENS
    )
    if not extraction.facts:
        return CorrectnessAudit(correct=True, extracted_facts=[], fact_verdicts=[])

    if len(extraction.facts) > _MAX_FACTS_TO_VERIFY:
        step = len(extraction.facts) / _MAX_FACTS_TO_VERIFY
        facts_to_check = [extraction.facts[int(i * step)] for i in range(_MAX_FACTS_TO_VERIFY)]
    else:
        facts_to_check = extraction.facts

    fact_verdicts: list[dict] = []
    for fact in facts_to_check:
        confirm_prompt = (
            f"{INJECTION_DEFENSE_CLAUSE}\n\n{JSON_ONLY_CLAUSE}\n\n"
            "Is the FACT below confirmed by the SYSTEM ANSWER? Answer strictly based on "
            "whether the system answer states or clearly implies this fact, not on general "
            "knowledge.\n\n"
            f"System answer: {final_answer}\n\nFact: {fact}\n\n"
            f'Schema: {{"confirmed": true|false}}'
        )
        if pacer is not None:
            await pacer.wait()
        confirmation = await call_llm_structured(
            confirm_prompt, _FactConfirmation, client=judge, max_tokens=VERIFICATION_MAX_TOKENS
        )
        fact_verdicts.append({"fact": fact, "confirmed": confirmation.confirmed})

    correct = all(v["confirmed"] for v in fact_verdicts)
    return CorrectnessAudit(correct=correct, extracted_facts=extraction.facts, fact_verdicts=fact_verdicts)


async def evaluate_golden_query(query_entry: dict, *, judge: Any, pacer: RatePacer | None = None) -> dict:
    """The one real per-query evaluation pipeline step, shared between
    this module's own run_calibration() and evaluation/run_eval.py
    (Stage 9): run one golden query through the real graph, judge it for
    correctness, score it via RAGAS, and attach all six real Langfuse
    scores — exactly once, here, so neither caller can silently drift
    out of sync with the tracing wiring the way duplicating this loop
    in run_eval.py would risk.

    Deliberately NOT moved into evaluation/golden_runner.py: ragas_
    metrics.py already imports golden_runner.py (for its own standalone
    --sample CLI mode), so golden_runner.py importing ragas_metrics.py
    back to call score_query() here would create exactly the circular
    import golden_runner.py's own docstring says it was built to avoid.
    Living in calibrate_thresholds.py instead — which already owns
    compute_correctness() and already imports both golden_runner and
    ragas_metrics — avoids a new module and a new cycle; run_eval.py
    imports this one function from here, a clean one-directional
    dependency.

    Returns {graph_result, final_answer, correct, correctness_audit,
    effective_severity, ragas_scores} — everything either caller needs
    for its own, different aggregation on top (this module's threshold
    search; run_eval.py's latency/source-attribution/prompt-version-
    comparison bookkeeping). correctness_audit (a CorrectnessAudit) is
    additive — existing consumers that only read `correct` are
    unaffected; run_full_calibration.py's checkpoint persists it so a
    future investigation into a surprising verdict doesn't need a fresh
    judge call just to see what was extracted/checked."""
    graph_result = await golden_runner.run_golden_query_through_graph(query_entry)
    final_answer = graph_result.get("final_answer") or ""

    correctness_audit = await compute_correctness(
        query_entry["query"], query_entry.get("ground_truth_answer", ""), final_answer, judge=judge, pacer=pacer
    )
    correct = correctness_audit.correct
    # Real bug, confirmed and fixed: raw severity_final is None whenever
    # incident_severity_node correctly didn't run (§3 — conditional on
    # incident/security category or Critical mode), which is the
    # MAJORITY of any real run, not an edge case. Every other place in
    # this codebase that needs "the system's actual severity assessment"
    # resolves through app.orchestration.nodes.router.
    # resolve_effective_severity() (graph.py's post-reflect edge,
    # escalate_node, respond_node's flagged_for_review) instead of
    # reading severity_final raw — this eval pipeline now matches that
    # same fallback rather than silently diverging from how production
    # actually behaves.
    effective_severity = resolve_effective_severity(
        graph_result.get("severity_final"), graph_result.get("severity_initial")
    )

    ragas_scores = await ragas_metrics.score_query(query_entry, graph_result, judge=judge, pacer=pacer)

    # §15's own convention ("langfuse.create_score() attaches
    # task_success + confidence_score post-eval") — real, confirmed gap
    # closed here: safe_create_score() has existed since the original
    # Stage 8 tracing work but was never actually called from an eval
    # harness until now. Extended beyond the two named in §15 to all
    # four RAGAS scores too, since score_query() above already computed
    # them for this exact query at real judge-call cost — attaching them
    # is free at this point, not a new call, and it's what lets
    # Langfuse's own dashboard filter/sort real traces by "which queries
    # had low faithfulness" instead of only ever seeing one averaged
    # number in the evaluation_runs row. trace_id is real and already
    # available (golden_runner.py sets it once per query and no node in
    # the graph ever overwrites it) — confirmed by reading every node
    # file before wiring this in. safe_create_score() is already
    # defensively wrapped (never raises, logs and returns on failure),
    # so a Langfuse outage here degrades to "this run's scores don't
    # appear in Langfuse," never to a broken eval pass — same philosophy
    # as every other safe_* wrapper in this project.
    trace_id = graph_result.get("trace_id")
    if trace_id:
        tracing.safe_create_score(trace_id=trace_id, name="task_success", value=float(correct))
        tracing.safe_create_score(
            trace_id=trace_id, name="confidence_score", value=graph_result.get("confidence_score") or 0.0
        )
        for score_name, score_value in ragas_scores.items():
            tracing.safe_create_score(trace_id=trace_id, name=score_name, value=score_value)

    return {
        "graph_result": graph_result,
        "final_answer": final_answer,
        "correct": correct,
        "correctness_audit": correctness_audit,
        "effective_severity": effective_severity,
        "ragas_scores": ragas_scores,
    }


def _tier_for_threshold(score: float, high: float, medium: float) -> str:
    if score >= high:
        return "High"
    if score >= medium:
        return "Medium"
    return "Low"


def search_thresholds(records: list[dict]) -> dict:
    """records: [{confidence_score, correct, is_critical_severity}, ...].
    Returns {"high": ..., "medium": ..., "tsr": ...} for the best
    candidate pair found."""
    best: dict | None = None
    for high in _HIGH_CANDIDATES:
        for medium in _MEDIUM_CANDIDATES:
            if medium >= high:
                continue
            successes = 0
            for r in records:
                if r["is_critical_severity"]:
                    successes += 1
                    continue
                tier = _tier_for_threshold(r["confidence_score"], high, medium)
                if tier == "Low":
                    successes += 1
                elif r["correct"]:
                    successes += 1
            tsr = successes / len(records) if records else 0.0
            if best is None or tsr > best["tsr"] or (tsr == best["tsr"] and high > best["high"]):
                best = {"high": high, "medium": medium, "tsr": tsr}
    if best is not None:
        return best
    settings = get_settings()
    return {"high": settings.confidence_high_threshold, "medium": settings.confidence_medium_threshold, "tsr": 0.0}


def write_calibrated_thresholds(high: float, medium: float) -> None:
    _RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    _RESULTS_PATH.write_text(
        json.dumps({"confidence_high_threshold": high, "confidence_medium_threshold": medium}, indent=2),
        encoding="utf-8",
    )


async def write_evaluation_run(sample_size: int, metrics: dict) -> None:
    async with async_session_maker() as db:
        db.add(EvaluationRun(sample_size=sample_size, **metrics))
        await db.commit()


def _avg(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def aggregate_calibration_metrics(query_entries: list[dict], per_query_results: list[dict]) -> dict:
    """Pure aggregation over already-computed evaluate_golden_query()
    results — extracted from run_calibration() so evaluation/run_eval.py
    (Stage 9) can reuse this exact bookkeeping (threshold search, routing/
    risk/escalation/critical/SQL accuracy) without re-running any real
    graph/judge calls: run_eval.py builds its own per_query_results list
    (via its own single loop over evaluate_golden_query(), timing latency
    around each call) and hands it here, rather than calling
    run_calibration() itself and re-evaluating every query a second time.

    query_entries and per_query_results must be the same length and in
    the same order (one evaluate_golden_query() result per golden entry)."""
    records: list[dict] = []
    ragas_totals = {"faithfulness": [], "answer_relevance": [], "context_precision": [], "context_recall": []}
    routing_correct = 0
    risk_correct = 0
    escalation_expected_yes = 0
    escalation_recalled = 0
    critical_expected = 0
    critical_correctly_classified = 0
    sql_correct = 0
    sql_total = 0

    for query_entry, result in zip(query_entries, per_query_results):
        graph_result = result["graph_result"]
        correct = result["correct"]
        effective_severity = result["effective_severity"]
        ragas_scores = result["ragas_scores"]

        records.append(
            {
                "confidence_score": graph_result.get("confidence_score") or 0.0,
                "correct": correct,
                "is_critical_severity": effective_severity == "Critical",
            }
        )
        for key, value in ragas_scores.items():
            ragas_totals[key].append(value)

        if graph_result.get("retrieval_mode") == query_entry.get("expected_retrieval_mode"):
            routing_correct += 1
        if effective_severity == query_entry.get("risk_level"):
            risk_correct += 1
        if query_entry.get("expected_escalation") == "Yes":
            escalation_expected_yes += 1
            if graph_result.get("escalation_flag"):
                escalation_recalled += 1
        if query_entry.get("risk_level") == "Critical":
            critical_expected += 1
            if effective_severity == "Critical":
                critical_correctly_classified += 1
        if query_entry.get("query_type") == "SQL":
            sql_total += 1
            if correct:
                sql_correct += 1

    threshold_result = search_thresholds(records)
    n = len(query_entries)
    critical_misclassification_rate = (
        1 - (critical_correctly_classified / critical_expected) if critical_expected else 0.0
    )

    return {
        "task_success_rate": threshold_result["tsr"],
        "sql_correctness": (sql_correct / sql_total) if sql_total else None,
        "query_routing_accuracy": routing_correct / n if n else None,
        "risk_classification_accuracy": risk_correct / n if n else None,
        "escalation_recall": (escalation_recalled / escalation_expected_yes) if escalation_expected_yes else None,
        "faithfulness": _avg(ragas_totals["faithfulness"]),
        "answer_relevance": _avg(ragas_totals["answer_relevance"]),
        "context_precision": _avg(ragas_totals["context_precision"]),
        "context_recall": _avg(ragas_totals["context_recall"]),
        "calibrated_high_threshold": threshold_result["high"],
        "calibrated_medium_threshold": threshold_result["medium"],
        "notes": (
            f"critical_misclassification_rate={critical_misclassification_rate:.3f} "
            f"(informational — not threshold-sensitive, see module docstring)"
        ),
    }


async def run_calibration(sample: int, *, judge: Any = judge_client_module) -> dict:
    queries = golden_runner.load_golden_queries(sample=sample)
    pacer = RatePacer()

    per_query_results = [await evaluate_golden_query(q, judge=judge, pacer=pacer) for q in queries]
    return aggregate_calibration_metrics(queries, per_query_results)


async def _main(sample: int, *, force: bool, allow_small_sample: bool) -> None:
    preflight_check(sample, force=force)
    metrics = await run_calibration(sample)
    await write_evaluation_run(sample, metrics)
    print(json.dumps(metrics, indent=2))

    if sample < _MIN_CALIBRATION_SAMPLE_SIZE and not allow_small_sample:
        print(
            f"\nNOT writing {_RESULTS_PATH}: --sample {sample} is below the minimum "
            f"({_MIN_CALIBRATION_SAMPLE_SIZE}) for a statistically meaningful calibration — see "
            f"_MIN_CALIBRATION_SAMPLE_SIZE's own comment for why. The mechanics ran end-to-end and "
            f"the metrics above (and a new evaluation_runs row) are real, but this result is NOT "
            f"being applied as a production threshold override. Re-run with --sample "
            f"{_MIN_CALIBRATION_SAMPLE_SIZE} or higher for a real calibration, or pass "
            f"--allow-small-sample to write anyway (not recommended)."
        )
        return

    write_calibrated_thresholds(metrics["calibrated_high_threshold"], metrics["calibrated_medium_threshold"])
    print(f"\nWrote {_RESULTS_PATH} and a new evaluation_runs row.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Recalibrate confidence-tier thresholds against golden_50.json.")
    parser.add_argument(
        "--sample", type=int, default=5,
        help="Number of golden queries to run (default 5 — a real full 50-query pass risks "
        "exceeding Groq's daily token cap, see groq_judge_client.py's own call-volume analysis).",
    )
    parser.add_argument(
        "--allow-small-sample", action="store_true",
        help=(
            f"Write calibrated_thresholds.json even if --sample is below "
            f"{_MIN_CALIBRATION_SAMPLE_SIZE} (deliberate override, never a default — "
            f"see _MIN_CALIBRATION_SAMPLE_SIZE's own comment for why this is unsafe)."
        ),
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Skip the preflight call-count safety ceiling (deliberate override, never a default).",
    )
    args = parser.parse_args()
    asyncio.run(_main(args.sample, force=args.force, allow_small_sample=args.allow_small_sample))
