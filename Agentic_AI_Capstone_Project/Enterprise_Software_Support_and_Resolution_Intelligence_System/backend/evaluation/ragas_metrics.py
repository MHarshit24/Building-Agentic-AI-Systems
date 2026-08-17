"""
evaluation/ragas_metrics.py

RAGAS-style Faithfulness / Answer Relevance / Context Precision / Context
Recall (§24.2), scored against golden_queries/golden_50.json + a real
graph run's retrieved_chunks/tables, sql_results, final_answer.

Every LLM-based sub-score below routes through the SAME independent judge
(evaluation/groq_judge_client.py), not just the standalone LLM-as-judge
score (§24's metric #7) — a deliberate design choice: RAGAS's own
standard methodology uses one consistent "critic" model across all its
sub-metrics, and self-grading bias (the exact thing an independent judge
exists to avoid) applies just as much to faithfulness/relevance/precision
judgments as to a standalone correctness score.

Context Recall is a DELIBERATE, NAMED SIMPLIFICATION of canonical RAGAS,
not textbook RAGAS presented as-is — see compute_context_recall()'s own
docstring. Standard RAGAS computes recall via judge-based sentence-level
attribution against the ground-truth answer; this project substitutes
golden_50.json's own `expected_sources` label-matching instead, since the
golden set already carries exactly that label and it avoids yet more
judge calls on an already call-heavy eval pass (§24.2's own call-volume/
rate-limit feasibility analysis — see groq_judge_client.py).

Token-minimization (a load-bearing design requirement, not an
afterthought — see groq_judge_client.py's call-volume analysis): every
judge prompt below sends only the query, the system's final answer, a
TRUNCATED slice of retrieved evidence (not full chunk text), and the
golden ground-truth answer where relevant. Never a full conversation/
state dump.

Every judge call below is deliberately decomposed into small, atomic,
single-decision checks (one claim/fact extracted and verified at a time,
one retrieved item judged at a time) rather than one call asking for a
compound, multi-fact judgment in a single pass. This isn't a style
preference: the judge model (llama-3.3-70b-versatile, see
groq_judge_client.py) has no internal reasoning/thinking phase, so
decomposing the task explicitly is how reasoning quality gets recovered
from a model that has no multi-step reasoning of its own — each call is
sized to be simple enough that getting it right doesn't actually require
reasoning the model doesn't have.

--sample (5-10 queries) is the permanent, intended operating mode against
this judge model/tier — not a temporary workaround pending a "real" full
run later. This was first confirmed against qwen/qwen3.6-27b (the
original judge pick, since replaced — see groq_judge_client.py's own
docstring for that history): a single claim-extraction call used 2,691
tokens (2.7x the original flat 1,000-tokens/call estimate), and a full
50-query run was estimated at ~7x Groq's 200K daily token cap for that
model. Switching to llama-3.3-70b-versatile removes the thinking-mode
cost driver (no hidden reasoning phase, so per-call cost tracks visible
output size, not an unpredictable reasoning preamble) but does NOT
restore full-run feasibility: this model's free-tier daily cap (100K
tokens — see groq_judge_client.py) is actually lower than qwen3.6-27b's
was, and decomposing compute_correctness (below, in calibrate_thresholds.py)
adds calls that partly offset the cheaper per-call cost. Worst-case
per-query cost is now ~17 calls × ~600 tokens/call average ≈ 10,150
tokens (see groq_judge_client.py's ESTIMATED_CALLS_PER_QUERY /
ESTIMATED_TOKENS_PER_CALL) — a full 50-query run (~508K tokens) is still
roughly 5x over the 100K daily cap. --sample-only remains the standing
operating mode, not a stopgap; `--sample 5-8` stays comfortably within
budget, `--sample 10` sits at the edge of a single day's cap. Real
alternatives exist and are named here without picking one (a future
decision, not this stage's): a paid Groq tier, a different judge model,
or a tighter structural cap on judge calls per query — see
compute_faithfulness()'s claim-verification cap below, which is exactly
this kind of mitigation applied to one call site.

--sample now draws a STRATIFIED sample (evaluation/golden_runner.py's
load_golden_queries), not the first N queries in file order — a real,
confirmed bug fix, not a refinement: golden_50.json is block-ordered by
category (Documentation x15 first), so every --sample value in the
5-10 range above used to draw exclusively from that one block, meaning
Context Recall's `expected_sources` label-matching and every other
category-sensitive signal only ever saw Documentation/RAG-mode queries
at the very sample sizes this module treats as the permanent operating
mode. A --sample 5-10 run now includes at least one query from every
category present (SQL, Hybrid, High-Severity, Escalation included),
proportionally weighted toward each category's real size once every
category has its guaranteed minimum slot — see _stratified_sample's own
docstring in golden_runner.py for the exact algorithm.
"""

from __future__ import annotations

import argparse
import asyncio
import math
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.ingestion.embedding_client import embed_text
from app.llm.structured_output import call_llm_structured
from app.prompts._shared import INJECTION_DEFENSE_CLAUSE, JSON_ONLY_CLAUSE
from evaluation import golden_runner
from evaluation.groq_judge_client import RatePacer, preflight_check
from evaluation import groq_judge_client as judge_client_module

_EVIDENCE_TRUNCATE_CHARS = 500
_ANSWER_RELEVANCE_QUESTION_COUNT = 3

_MAX_CLAIMS_TO_VERIFY = 5
# Verification calls scale linearly with extracted claim count, which is
# unbounded — a real extraction call during this stage's build returned
# 12 claims from one moderately detailed RAG answer (see module
# docstring), 3x the ~4-claim average the original call-volume estimate
# assumed. A hard cap turns Faithfulness's per-query cost from "scales
# with answer verbosity" into a predictable, fixed ceiling. 5 is chosen
# as enough claims to give a meaningful supported/total ratio (not just
# 1-2 data points) while keeping worst-case per-query calls close to the
# original ~5-call planning assumption for this sub-metric (1 extract +
# up to 5 verify = 6, vs the original ~5) rather than the 13 calls a
# fully exhaustive check of a 12-claim answer would require.

# Two tiers, not one flat budget — sized to each call shape's real output,
# not a single one-size-fits-all guess. Unprefixed (not module-private)
# because calibrate_thresholds.py's compute_correctness() reuses both for
# its own analogous extraction/verification calls.
#
# EXTRACTION_MAX_TOKENS is for calls that produce a LIST (claim
# extraction here, fact extraction in calibrate_thresholds.py, question
# generation in compute_answer_relevance) — real data point: a claim-
# extraction call against a realistic pipeline prompt used ~250 tokens of
# actual visible output once qwen3.6-27b's hidden-reasoning overhead was
# eliminated by switching models (see groq_judge_client.py's history
# note); 1,500 keeps a comfortable ~6x margin over that observed need
# without reserving so much that Groq's TPM rate limiter (which reserves
# against requested max_tokens, not realized usage — confirmed by a real
# 429 during this stage's build) artificially throttles achievable
# calls/minute.
EXTRACTION_MAX_TOKENS = 1500

# VERIFICATION_MAX_TOKENS is for calls that produce a single boolean
# (claim verification here, fact confirmation in calibrate_thresholds.py,
# per-item relevance in compute_context_precision) — real visible output
# for this shape is tiny (e.g. {"supported": true}, ~10-15 tokens); 300
# is a comfortable margin without reserving TPM headroom the call will
# never use.
VERIFICATION_MAX_TOKENS = 300

_MAX_CLAIMS_TO_VERIFY = 5
# Verification calls scale linearly with extracted claim count, which is
# unbounded — a real extraction call during this stage's build returned
# 12 claims from one moderately detailed RAG answer (see groq_judge_client.py's
# history note), 3x the ~4-claim average the original call-volume estimate
# assumed. A hard cap turns Faithfulness's per-query cost from "scales
# with answer verbosity" into a predictable, fixed ceiling. 5 is chosen
# as enough claims to give a meaningful supported/total ratio (not just
# 1-2 data points) while keeping worst-case per-query calls close to the
# original ~5-call planning assumption for this sub-metric (1 extract +
# up to 5 verify = 6, vs the original ~5) rather than the 13 calls a
# fully exhaustive check of a 12-claim answer would require.


# ---------------------------------------------------------------------------
# Judge-call structured-output schemas — eval-only, deliberately not in
# app/schemas/agent_contracts.py (that file is for production node
# contracts; these never run in the deployed app).
# ---------------------------------------------------------------------------

class _ClaimExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    claims: list[str]


class _ClaimVerification(BaseModel):
    model_config = ConfigDict(extra="forbid")
    supported: bool


class _GeneratedQuestions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    questions: list[str]


class _RelevanceJudgment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    relevant: bool


def _truncate(text: str, limit: int = _EVIDENCE_TRUNCATE_CHARS) -> str:
    return text if len(text) <= limit else text[:limit] + "..."


def _retrieved_items(graph_result: dict) -> list[Any]:
    """Chunks + tables (+ diagrams) actually retrieved this run — the
    real evidence set a faithfulness/precision judgment is graded
    against, not sql_results (grounded by construction, §14 point 1, so
    not itself subject to a relevance/support judgment the same way)."""
    return (
        list(graph_result.get("retrieved_chunks") or [])
        + list(graph_result.get("retrieved_tables") or [])
        + list(graph_result.get("retrieved_diagrams") or [])
    )


def _format_context(graph_result: dict) -> str:
    items = _retrieved_items(graph_result)
    lines = [f"({item.source_document or 'unknown source'}): {_truncate(item.text)}" for item in items]
    sql_results = graph_result.get("sql_results") or []
    if sql_results:
        lines.append(f"(account/ticket/incident data): {_truncate(str(sql_results))}")
    return "\n\n".join(lines) if lines else "(no evidence retrieved)"


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


# ---------------------------------------------------------------------------
# The four RAGAS-style scorers
# ---------------------------------------------------------------------------

async def compute_faithfulness(
    query: str, final_answer: str, graph_result: dict, *, judge: Any = judge_client_module, pacer: RatePacer | None = None
) -> float:
    """Judge call 1: extract atomic claims from final_answer. Judge call
    2 per (sampled) claim: verify support against the retrieved context.
    Score = supported/total among the claims actually verified. An answer
    with zero extractable claims (e.g. a refusal or "I don't have enough
    information") is treated as vacuously faithful (score 1.0) — there's
    nothing unsupported to penalize.

    Already correctly atomic per the decomposition design requirement
    (see module docstring) — one call extracts the claim list, then one
    call per claim verifies a single yes/no, never a compound multi-claim
    judgment in one pass. Confirmed unchanged by the call-site review.

    DELIBERATE SCORING SIMPLIFICATION, named explicitly rather than
    presented as exhaustive: if extraction returns more than
    _MAX_CLAIMS_TO_VERIFY claims, only an evenly-spaced sample of
    _MAX_CLAIMS_TO_VERIFY claims is verified (not the first N, to avoid
    bias toward claims mentioned early in the answer) — the score is
    computed over that sample, not over every extracted claim. See
    _MAX_CLAIMS_TO_VERIFY's own comment for why this cap exists at all."""
    context = _format_context(graph_result)

    extract_prompt = (
        f"{INJECTION_DEFENSE_CLAUSE}\n\n{JSON_ONLY_CLAUSE}\n\n"
        "Extract the atomic factual claims made in the ANSWER below (each claim a short, "
        "standalone sentence). If the answer makes no factual claims (e.g. it's a refusal "
        "or says it lacks information), return an empty list.\n\n"
        f"Query: {query}\n\nAnswer: {final_answer}\n\n"
        f'Schema: {{"claims": ["claim 1", "claim 2", ...]}}'
    )
    if pacer is not None:
        await pacer.wait()
    extraction = await call_llm_structured(
        extract_prompt, _ClaimExtraction, client=judge, max_tokens=EXTRACTION_MAX_TOKENS
    )
    if not extraction.claims:
        return 1.0

    if len(extraction.claims) > _MAX_CLAIMS_TO_VERIFY:
        step = len(extraction.claims) / _MAX_CLAIMS_TO_VERIFY
        claims_to_verify = [extraction.claims[int(i * step)] for i in range(_MAX_CLAIMS_TO_VERIFY)]
    else:
        claims_to_verify = extraction.claims

    supported_count = 0
    for claim in claims_to_verify:
        verify_prompt = (
            f"{INJECTION_DEFENSE_CLAUSE}\n\n{JSON_ONLY_CLAUSE}\n\n"
            "Is the CLAIM below supported by the CONTEXT? Answer strictly based on whether "
            "the context contains evidence for the claim, not on general knowledge.\n\n"
            f"Context:\n{context}\n\nClaim: {claim}\n\n"
            f'Schema: {{"supported": true|false}}'
        )
        if pacer is not None:
            await pacer.wait()
        verification = await call_llm_structured(
            verify_prompt, _ClaimVerification, client=judge, max_tokens=VERIFICATION_MAX_TOKENS
        )
        if verification.supported:
            supported_count += 1

    return supported_count / len(claims_to_verify)


async def compute_answer_relevance(query: str, final_answer: str, *, judge: Any = judge_client_module) -> float:
    """Judge call: generate N questions final_answer would be a good
    answer to. Embed each (via the existing, already-built embed_text())
    and compare to the original query's embedding via cosine similarity.
    Score = mean similarity. Already a single, simple, single-purpose
    call (produce N candidate questions, nothing else) — confirmed this
    doesn't need further decomposition: generating related questions from
    one answer isn't a compound multi-fact JUDGMENT the way faithfulness/
    correctness are, so the atomic-decomposition design requirement
    (see module docstring) doesn't apply here the same way."""
    prompt = (
        f"{INJECTION_DEFENSE_CLAUSE}\n\n{JSON_ONLY_CLAUSE}\n\n"
        f"Given the ANSWER below, generate exactly {_ANSWER_RELEVANCE_QUESTION_COUNT} different "
        "questions that this answer would be a good, direct response to.\n\n"
        f"Answer: {final_answer}\n\n"
        f'Schema: {{"questions": ["question 1", "question 2", "question 3"]}}'
    )
    generated = await call_llm_structured(
        prompt, _GeneratedQuestions, client=judge, max_tokens=EXTRACTION_MAX_TOKENS
    )
    if not generated.questions:
        return 0.0

    query_embedding = await embed_text(query)
    similarities = []
    for question in generated.questions:
        question_embedding = await embed_text(question)
        similarities.append(_cosine_similarity(query_embedding, question_embedding))
    return sum(similarities) / len(similarities)


async def compute_context_precision(
    query: str,
    ground_truth_answer: str,
    graph_result: dict,
    *,
    judge: Any = judge_client_module,
    pacer: RatePacer | None = None,
) -> float:
    """Judge call per retrieved item: relevant or not, against query +
    ground_truth_answer. Score = relevant/total retrieved. Nothing
    retrieved at all is treated as vacuously precise (score 1.0) —
    there's no irrelevant item to penalize (Context Recall is what
    catches "should have retrieved something and didn't"). Already
    correctly atomic — one call, one item, one yes/no — confirmed
    unchanged by the atomic-decomposition call-site review."""
    items = _retrieved_items(graph_result)
    if not items:
        return 1.0

    relevant_count = 0
    for item in items:
        prompt = (
            f"{INJECTION_DEFENSE_CLAUSE}\n\n{JSON_ONLY_CLAUSE}\n\n"
            "Is the RETRIEVED ITEM below relevant to answering the QUERY, given the "
            "EXPECTED ANSWER as ground truth for what a correct answer looks like?\n\n"
            f"Query: {query}\n\nExpected answer: {ground_truth_answer}\n\n"
            f"Retrieved item ({item.source_document or 'unknown source'}): {_truncate(item.text)}\n\n"
            f'Schema: {{"relevant": true|false}}'
        )
        if pacer is not None:
            await pacer.wait()
        judgment = await call_llm_structured(
            prompt, _RelevanceJudgment, client=judge, max_tokens=VERIFICATION_MAX_TOKENS
        )
        if judgment.relevant:
            relevant_count += 1

    return relevant_count / len(items)


def compute_context_recall(graph_result: dict, expected_sources: list[str]) -> float:
    """DELIBERATE SIMPLIFICATION of canonical RAGAS context recall, named
    explicitly here rather than presented as the textbook metric.

    Standard RAGAS computes context recall by asking a judge, sentence
    by sentence, whether each statement in the ground-truth answer is
    attributable to the retrieved context — a genuinely LLM-driven
    judgment. This function instead uses golden_50.json's own
    `expected_sources` label (already present on every entry, §24.4) as
    ground truth: an expected source counts as "recalled" if any
    retrieved item's source_document appears as a substring of that
    label (golden_50's expected_sources strings are human-written,
    e.g. "API Integration & Authentication Guide § OAuth 2.0 flow
    (...)", starting with the real source_document name).

    Reasonable given the golden set already carries exactly this label
    and it avoids yet more judge calls on an already call-heavy eval
    pass — but it is a simplification of the real metric, not
    equivalent to it, and must be documented as such everywhere this
    score is reported (this docstring, evaluation_runs' own column
    comment, and the eventual docs/slo_evaluation_report.md)."""
    if not expected_sources:
        return 1.0

    retrieved_documents = {item.source_document for item in _retrieved_items(graph_result) if item.source_document}
    if not retrieved_documents:
        return 0.0

    matched = sum(
        1 for expected in expected_sources if any(doc in expected for doc in retrieved_documents)
    )
    return matched / len(expected_sources)


async def score_query(
    query_entry: dict,
    graph_result: dict,
    *,
    judge: Any = judge_client_module,
    pacer: RatePacer | None = None,
) -> dict:
    """Computes all four scores for one golden query + its real graph
    result. `pacer`, if given, is threaded through to EVERY individual
    judge call (not just once per sub-score) — real, confirmed bug fix:
    the original "once per sub-score" granularity left up to 6 calls
    inside compute_faithfulness (1 extraction + up to 5 verifications)
    and up to ~4 inside compute_context_precision firing back-to-back
    with zero spacing, which a live Groq console log during this
    project's own real calibration run showed landing as a burst of 9
    requests inside a 2-second window — comfortably enough to blow a
    12,000 token/minute cap in one burst regardless of how long the
    pacer waited BEFORE that burst started. Pacing now happens before
    every real judge-bearing call, no exceptions."""
    final_answer = graph_result.get("final_answer") or ""

    faithfulness = await compute_faithfulness(query_entry["query"], final_answer, graph_result, judge=judge, pacer=pacer)

    if pacer is not None:
        await pacer.wait()
    answer_relevance = await compute_answer_relevance(query_entry["query"], final_answer, judge=judge)

    context_precision = await compute_context_precision(
        query_entry["query"], query_entry.get("ground_truth_answer", ""), graph_result, judge=judge, pacer=pacer
    )

    context_recall = compute_context_recall(graph_result, query_entry.get("expected_sources") or [])

    return {
        "faithfulness": faithfulness,
        "answer_relevance": answer_relevance,
        "context_precision": context_precision,
        "context_recall": context_recall,
    }


async def _run_standalone(sample: int) -> None:
    preflight_check(sample)  # raises CallBudgetExceededError if unsafe, per groq_judge_client.py
    queries = golden_runner.load_golden_queries(sample=sample)
    pacer = RatePacer()
    totals = {"faithfulness": [], "answer_relevance": [], "context_precision": [], "context_recall": []}

    for query_entry in queries:
        graph_result = await golden_runner.run_golden_query_through_graph(query_entry)
        scores = await score_query(query_entry, graph_result, pacer=pacer)
        for key, value in scores.items():
            totals[key].append(value)
        print(f"{query_entry['id']}: {scores}")

    print("\n--- Averages ---")
    for key, values in totals.items():
        avg = sum(values) / len(values) if values else None
        print(f"{key}: {avg}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run RAGAS-style metrics against golden_50.json.")
    parser.add_argument(
        "--sample", type=int, default=5,
        help="Number of golden queries to run (default 5 — a real full 50-query pass risks "
        "exceeding Groq's daily token cap, see groq_judge_client.py's own call-volume analysis).",
    )
    args = parser.parse_args()
    asyncio.run(_run_standalone(args.sample))
