"""
app/orchestration/nodes/reflect.py

Reflection Agent (§3 roster #6). Always runs. Full agent implementation
in this one file: prompt assembly, the LLM self-critique call, the
rule-based citation-overlap check (§14 point 3, non-LLM), blending them
into a final confidence_score/groundedness_flag/confidence_tier, and the
state-update return.

Deliberately does NOT touch reflection_loopback_count — see
doc_retrieval.py's own docstring for why that counter is owned entirely
by doc_retrieval_node (the node both entry paths and the loop-back target
run through), not by this node or by graph.py's conditional-edge
function (which can only select the next node, not update state).

reasoning_effort="medium" per §13: groundedness judgment genuinely
benefits from more careful reasoning than a fixed-enum classification.

Stage 6 fix, found while designing test_graph_parallel_fanout.py, not
shipped silently: this file was built in Stage 5 around RAG evidence
only (retrieved_chunks/tables/diagrams), before sql_results existed as a
possible evidence source. As originally written, a SQL-alone or Hybrid
answer would ALWAYS be judged ungrounded (_citation_overlap_ok only
checked chunk/table/diagram `.cited` flags, which are structurally empty
whenever account_validation_node is the sole or partial responder) and
would ALWAYS get retrieval_quality=0.0 (dragging every SQL-mode
confidence_score down by RETRIEVAL_QUALITY_WEIGHT's full 0.3, regardless
of how good the actual SQL answer was) — silently routing every SQL-only
response toward an incorrect ungrounded loop-back or Low-confidence
escalation. Both `_citation_overlap_ok` and `_retrieval_quality_score`
(and `_format_evidence`, so reflect's own LLM call can actually see
sql_results when judging groundedness) now account for sql_results
directly, per §14 point 1's own principle that SQL facts are grounded by
construction — see each function's docstring below for the specific fix.
"""

from __future__ import annotations

from app.config import get_settings
from app.llm.structured_output import call_llm_structured
from app.prompts._shared import flatten_messages
from app.prompts.loader import get_build_prompt
from app.schemas.agent_contracts import ReflectionOutput
from app.schemas.state import SupportGraphState

REASONING_EFFORT = "medium"

# §6's own tier thresholds, applied here to the FINAL blended score —
# not trusted from the LLM's own self-reported confidence_tier field,
# since that field is only ever computed against the model's OWN raw
# confidence_score, before blending with the retrieval-quality and
# citation-overlap signals below. The blended score is authoritative;
# deriving its tier deterministically in code (rather than asking the
# LLM to also grade the blended result) keeps tier assignment
# consistent and auditable.
#
# Read via get_settings() at call time, not module-level constants
# (Stage 8, §25) — evaluation/calibrate_thresholds.py recalibrates these
# from real golden-eval results and writes evaluation/results/
# calibrated_thresholds.json, which get_settings() applies as an override
# over the project-.env-sourced starting defaults (0.85/0.70). Reading
# fresh via get_settings() (cheap — lru_cache'd) means a recalibration
# takes effect on the next process start, no source-code edit needed.

# Blend weights (§14 point 3: retrieval fusion score + LLM self-critique
# + rule-based citation-overlap check, blended, not any single signal
# alone). Starting weights, not calibrated against real eval data yet —
# same "starting point, not proven" framing as §6's 0.70 threshold.
RETRIEVAL_QUALITY_WEIGHT = 0.3
LLM_SELF_CRITIQUE_WEIGHT = 0.5
CITATION_OVERLAP_WEIGHT = 0.2


def _retrieval_quality_score(state: SupportGraphState) -> float:
    """Normalizes hybrid_search's RRF-fusion-scale top score (see
    doc_retrieval.py's FUSION_RETRY_THRESHOLD comment on that scale)
    into a crude 0-1 "was the evidence itself strong" signal.

    Stage 6 fix: when no RAG evidence exists at all but sql_results does
    (SQL-alone mode — doc_retrieval_node never ran), there is no fusion
    score to normalize, and the pre-fix behavior (defaulting to 0.0)
    unfairly tanked every SQL-only response's confidence regardless of
    answer quality. SQL facts are grounded by construction (§14 point 1)
    — no fusion-score-based uncertainty applies to them the way it does
    to RAG chunks — so this returns 1.0 in that case instead."""
    from app.orchestration.nodes.doc_retrieval import FUSION_RETRY_THRESHOLD

    all_items = (
        (state.get("retrieved_chunks") or [])
        + (state.get("retrieved_tables") or [])
        + (state.get("retrieved_diagrams") or [])
    )
    if all_items:
        top_score = max(item.score for item in all_items)
        return min(top_score / FUSION_RETRY_THRESHOLD, 1.0)
    if state.get("sql_results"):
        return 1.0
    return 0.0


def _citation_overlap_ok(state: SupportGraphState) -> bool:
    """Rule-based, non-LLM half of §14 point 3's dual-check: does the
    draft answer actually rely on at least one retrieved item marked
    `cited=True` by doc_retrieval_node? A claimed answer with zero real
    citations is exactly the case this check exists to catch — an LLM
    that says "groundedness_flag: true" but didn't cite anything real.

    Stage 6 fix: sql_results rows are plain dicts with no `cited` flag at
    all (they're grounded by construction, §14 point 1 — narrated only
    from real parametrized-query output, never invented), so a non-empty
    sql_results also satisfies this check, independent of the
    chunk/table/diagram citation check. Without this, every SQL-alone or
    Hybrid response would be judged uncited (zero cited chunks) even when
    the SQL evidence backing it is fully trustworthy."""
    all_items = (
        (state.get("retrieved_chunks") or [])
        + (state.get("retrieved_tables") or [])
        + (state.get("retrieved_diagrams") or [])
    )
    has_cited_rag_evidence = any(item.cited for item in all_items)
    has_sql_evidence = bool(state.get("sql_results"))
    return has_cited_rag_evidence or has_sql_evidence


def _format_evidence(state: SupportGraphState) -> str:
    """Stage 6 fix: also includes sql_results (previously omitted
    entirely), so reflect's own LLM self-critique call can actually see
    the account/ticket/incident evidence it's judging a SQL-alone or
    Hybrid answer against, instead of being shown "(no evidence
    retrieved)" for an answer that's actually grounded in real SQL data."""
    all_items = (
        (state.get("retrieved_chunks") or [])
        + (state.get("retrieved_tables") or [])
        + (state.get("retrieved_diagrams") or [])
    )
    lines = []
    for item in all_items:
        location = item.source_document or "unknown source"
        if item.section_header:
            location += f" § {item.section_header}"
        marker = " [CITED]" if item.cited else ""
        lines.append(f"({location}){marker}\n{item.text[:800]}")

    sql_results = state.get("sql_results") or []
    if sql_results:
        cleaned = [{k: v for k, v in row.items() if not k.startswith("_")} for row in sql_results]
        lines.append(f"(account/ticket/incident data, grounded by construction)\n{cleaned}")

    return "\n\n".join(lines) if lines else "(no evidence retrieved)"


def _merge_final_answer(state: SupportGraphState) -> str | None:
    """Frontend integration pass bugfix, found via manual QA: a real Hybrid-
    mode query ("what tickets does this customer have?") came back with
    "I don't have enough information" — because doc_retrieval_node's
    RAG-only draft_answer unconditionally owns final_answer (Stage 6
    Deviation K, to avoid a concurrent-write conflict with
    account_validation_node on the same LangGraph superstep), so the
    account_validation_node narrative that actually HAD the answer (real
    ticket data, via account_narrative — see state.py) was computed by a
    real LLM call and then silently discarded every time both branches ran.

    reflect_node is the guaranteed convergence point for every non-guard-
    failure path (both branches always route here, whether or not
    incident_severity_node ran in between), and runs BEFORE this node's own
    groundedness/confidence judgment — so merging here fixes both the
    text the user ultimately sees AND the evidence reflect's own LLM
    self-critique call is judging, not just the display text.

    RAG-alone/SQL-alone (only one of the two ran): unchanged, no merge
    needed — final_answer already holds the sole responder's text (SQL-
    alone still writes it directly too; the "already contains" check below
    is what keeps that case from being naively duplicated).

    Second real bug fix, found via live manual QA after the first one:
    doc_retrieval_node and account_validation_node run CONCURRENTLY in
    genuine Hybrid/Critical mode (the same LangGraph superstep, via Send)
    — neither can see the other's own evidence_sufficient verdict while
    drafting its own text, since neither has finished yet. One side can
    correctly, honestly draft "I don't have enough information to answer
    that" from its own narrow view (e.g. doc_retrieval has no account
    context; or account_validation found nothing matching) while the OTHER
    side genuinely has a real answer — naively concatenating both used to
    produce "I don't have enough information... [real answer anyway]" in
    one response, a real self-contradiction confirmed against live traces
    (not just the SQL-alone-then-retry case the first fix above covers).
    Each side's own evidence_sufficient (state.py's doc_evidence_sufficient/
    account_evidence_sufficient, persisted by each node from its own
    structured output) is the real, non-heuristic signal for this — prefer
    whichever side actually has something to say over the one that
    genuinely doesn't, rather than gluing a denial next to a real answer.
    """
    doc_or_direct_answer = state.get("final_answer")
    account_narrative = state.get("account_narrative")
    if not account_narrative:
        return doc_or_direct_answer
    if not doc_or_direct_answer:
        return account_narrative
    if account_narrative in doc_or_direct_answer:
        return doc_or_direct_answer  # SQL-alone mode already wrote this exact text directly

    doc_evidence_sufficient = state.get("doc_evidence_sufficient")
    account_evidence_sufficient = state.get("account_evidence_sufficient")
    if doc_evidence_sufficient is False and account_evidence_sufficient is not False:
        return account_narrative
    if account_evidence_sufficient is False and doc_evidence_sufficient is not False:
        return doc_or_direct_answer

    return f"{doc_or_direct_answer}\n\n{account_narrative}"


def _tier_for(score: float) -> str:
    settings = get_settings()
    if score >= settings.confidence_high_threshold:
        return "High"
    if score >= settings.confidence_medium_threshold:
        return "Medium"
    return "Low"


async def reflect_node(state: SupportGraphState) -> dict:
    """Reads: full state (query, retrieved_chunks/tables/diagrams,
    final_answer, account_narrative). Writes: confidence_score,
    groundedness_flag, confidence_tier (§4), AND final_answer — the one
    exception to "final_answer is set once by whichever node ran and never
    touched again downstream": see _merge_final_answer()'s own docstring
    for why the Hybrid/Critical merge has to happen here, before this
    node's own judgment call reads it. NOT reflection_loopback_count."""
    merged_answer = _merge_final_answer(state)

    build_prompt = get_build_prompt("reflect")
    messages = build_prompt(
        static_ctx={},
        dynamic_ctx={
            "query": state["query"],
            "history": state.get("chat_history") or [],
            "draft_answer": merged_answer,
            "evidence": _format_evidence(state),
        },
    )
    prompt = flatten_messages(messages)
    llm_output: ReflectionOutput = await call_llm_structured(prompt, ReflectionOutput, reasoning_effort=REASONING_EFFORT)

    citation_ok = _citation_overlap_ok(state)
    groundedness_flag = llm_output.groundedness_flag and citation_ok

    retrieval_quality = _retrieval_quality_score(state)
    confidence_score = (
        RETRIEVAL_QUALITY_WEIGHT * retrieval_quality
        + LLM_SELF_CRITIQUE_WEIGHT * llm_output.confidence_score
        + CITATION_OVERLAP_WEIGHT * (1.0 if groundedness_flag else 0.0)
    )
    confidence_tier = _tier_for(confidence_score)

    return {
        "final_answer": merged_answer,
        "confidence_score": confidence_score,
        "groundedness_flag": groundedness_flag,
        "confidence_tier": confidence_tier,
    }
