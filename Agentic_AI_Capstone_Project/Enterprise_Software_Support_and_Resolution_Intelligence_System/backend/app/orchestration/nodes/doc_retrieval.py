"""
app/orchestration/nodes/doc_retrieval.py

Documentation Retrieval Agent (§3 roster #3). Runs for every
non-out-of-scope query in Stage 5 (graph.py's provisional single-path
wiring — real RAG/SQL/Hybrid/Critical branching is Stage 6; see
graph.py's own module docstring for that scope decision).

Full agent implementation lives in this one file: calls hybrid_search()
directly (deterministic Python — not LLM tool-calling; see
doc_retrieval_v1.py's own docstring for why), applies §31's Layer-B
scope check, builds the prompt, makes the structured-output LLM call,
marks cited items, and implements the retrieval_retry_count-gated
internal retry (§2.3, §5).

`retrieved_chunks`/`retrieved_tables`/`retrieved_diagrams` are PLAIN
last-write-wins fields in state.py, not accumulators — confirmed by
re-reading that file's own inline comment directly ("On the
reflect→doc_retrieval loop-back doc_retrieval fully *replaces* the
previous result set"), not assumed from the module docstring's general
Annotated[list, operator.add] convention description, which does NOT
apply to these three fields specifically. This node always returns the
complete current result set, never a partial "new items only" delta.

§27 describes product_version also being "extracted from the query if
mentioned, e.g. 'v3.2'" for filtering — see extract_product_version()
below. Deliberately narrow (requires a leading "v", e.g. "v3.5"): the
real ingested corpus (checked directly, production-readiness gap
analysis item B.5) carries exactly one non-null product_version value
today ('v3.5'), always in that vX.Y shape, so a broader "guess whether a
bare number is a version" pattern would be solving for data that doesn't
exist yet — revisit only once the corpus actually needs it.

reasoning_effort="low" per §13.
"""

from __future__ import annotations

import logging
import re

from app.guardrails.scope_guardrail import get_cached_centroid, is_in_scope
from app.ingestion.embedding_client import embed_text
from app.llm.structured_output import call_llm_structured
from app.logging.structured_logger import log_event
from app.observability.tracing import end_child_span, traced_child_span
from app.prompts._shared import flatten_messages
from app.prompts.loader import get_build_prompt
from app.retrieval.hybrid_search import hybrid_search
from app.retrieval.vector_search import SearchResult
from app.schemas.agent_contracts import DocRetrievalOutput, RetrievedChunk, RetrievedDiagram, RetrievedTable
from app.schemas.state import SupportGraphState

logger = logging.getLogger(__name__)

REASONING_EFFORT = "low"
MAX_RETRIEVAL_RETRIES = 1  # §5 hard cap, matches state.py's retrieval_retry_count contract

# §2.3's literal "fused top score < 0.4" assumes a raw-similarity scale.
# hybrid_search's actual returned score (post RRF-fusion, k=60) lives on
# a much smaller scale — best possible is ~0.033 (rank 1 in both legs),
# realistic range ~0.005-0.033. This is the scale-appropriate
# reinterpretation of the same "the top result barely made it" intent,
# not a literal transcription of "0.4" — a starting point pending real
# calibration, same framing as §6's own 0.70.
FUSION_RETRY_THRESHOLD = 0.02

_VERSION_PATTERN = re.compile(r"\bv(\d+(?:\.\d+){0,2})\b", re.IGNORECASE)


def extract_product_version(query: str) -> str | None:
    """Extracts a "vX[.Y[.Z]]" style product version mention from query
    text (e.g. "v3.5", "V3", "v3.5.1"), matching the exact shape actually
    observed in the real ingested corpus's own document text (see this
    module's docstring). Returns None if no such mention is present —
    deliberately does not attempt to parse a bare number with no leading
    "v" (see docstring: that ambiguity — version vs. dollar amount vs.
    ticket number — is real, and this design sidesteps it rather than
    guessing)."""
    match = _VERSION_PATTERN.search(query)
    if not match:
        return None
    return f"v{match.group(1)}"


def _build_result_map(results: list[SearchResult]) -> dict:
    """Assigns each result a stable id (e.g. "chunk_42") for citation
    purposes and maps it into the matching agent_contracts Pydantic
    type. Drops any asset_type="image" hits (state.py has no
    retrieved_images slot, and the real corpus has zero images today —
    logged, not silently discarded; see this module's docstring)."""
    chunks: list[RetrievedChunk] = []
    tables: list[RetrievedTable] = []
    diagrams: list[RetrievedDiagram] = []
    by_id: dict[str, tuple[str, object]] = {}

    for result in results:
        item_id = f"{result.asset_type}_{result.asset_row_id}"
        common = dict(
            asset_id=result.asset_row_id,
            text=result.text,
            source_document=result.source_document,
            section_header=result.section_header,
            page_number=result.page_number,
            product_version=result.product_version,
            category=result.category,
            score=result.score,
        )
        if result.asset_type == "chunk":
            item: object = RetrievedChunk(**common)
            chunks.append(item)
        elif result.asset_type == "table":
            item = RetrievedTable(**common)
            tables.append(item)
        elif result.asset_type == "diagram":
            item = RetrievedDiagram(**common)
            diagrams.append(item)
        else:
            log_event(logger, "DEBUG", "doc_retrieval_dropped_image_result", asset_id=result.asset_row_id)
            continue
        by_id[item_id] = (result.asset_type, item)

    return {"chunks": chunks, "tables": tables, "diagrams": diagrams, "by_id": by_id}


def _format_evidence(mapped: dict) -> str:
    lines = []
    for item_id, (asset_type, item) in mapped["by_id"].items():
        location = item.source_document or "unknown source"
        if item.section_header:
            location += f" § {item.section_header}"
        snippet = item.text[:800]
        lines.append(f"[{item_id}] ({asset_type}, {location})\n{snippet}")
    return "\n\n".join(lines) if lines else "(no evidence retrieved)"


async def _run_one_attempt(
    query: str, history: list[dict], scope_note: str, account_context: str | None = None
) -> tuple[DocRetrievalOutput, dict]:
    filters: dict = {}
    # category is DELIBERATELY NOT applied as a retrieval filter here —
    # a real, evidence-based deviation from §27's original documented
    # rationale ("pre-filter to the same category the classifier already
    # assigned"), not an oversight. Real findings from this project's own
    # full-50-query golden eval + a targeted follow-up investigation
    # (kept here since this is the one call site that decides what gets
    # requested, not vector_search.py/keyword_search.py's own filter
    # mechanics, which are unchanged and still support an explicit
    # category filter if a future caller wants one):
    #   - classify_node's category (the QUERY's own topic) and a
    #     document's stored category (the ANSWER's topic) are related
    #     but independent axes — a "usage" question can correctly be
    #     answered by an "incident"-tagged document (confirmed directly:
    #     "What is the difference between MTTR and MTTA in incident
    #     metrics?" was classified "usage" but its correct answer lives
    #     in "incident"-tagged chunks).
    #   - Measured directly against the full golden set: 26/50 queries
    #     actually reach this filter; for 11 of those 26 (42%), the
    #     hard filter changes the top-1 retrieved result relative to no
    #     filter at all — and in every case checked, the UNFILTERED
    #     result was the correct one. Zero cases were found where the
    #     hard filter produced a better result than no filter.
    #   - "billing" (a real classify_node category, reachable via
    #     Critical-severity override even though route_by_category never
    #     sends it to Hybrid) is structurally unmatchable: the ingested
    #     corpus's real category values are only {incident, integration,
    #     security, usage} — no document is ever tagged "billing" — so a
    #     billing-classified query used to get ZERO retrieval candidates
    #     every time, guaranteed, regardless of true relevance.
    # product_version stays a hard filter below, unchanged — a genuinely
    # different concern (avoiding cross-version-contaminated answers,
    # §27's "conflicting documentation guidance across versions"
    # high-risk scenario) where exclusion is actually the correct
    # behavior, not an assumption that happens to be wrong.
    extracted_version = extract_product_version(query)
    if extracted_version:
        filters["product_version"] = extracted_version
    filters = filters or None
    # Nested child span (§15: "hybrid_search" — a function called inside
    # doc_retrieval_node, not its own graph node) — nests automatically
    # under doc_retrieval's own active span via OTel context propagation.
    cm, span = traced_child_span("hybrid_search", input={"query": query, "filters": filters})
    results = await hybrid_search(query, filters=filters)
    end_child_span(
        cm, span,
        output={"result_count": len(results), "asset_ids": [r.asset_row_id for r in results]},
    )
    mapped = _build_result_map(results)
    evidence = _format_evidence(mapped)
    if scope_note:
        evidence = f"{scope_note}\n\n{evidence}"

    build_prompt = get_build_prompt("doc_retrieval")
    messages = build_prompt(
        static_ctx={},
        dynamic_ctx={"query": query, "history": history, "evidence": evidence, "account_context": account_context},
    )
    prompt = flatten_messages(messages)
    output = await call_llm_structured(prompt, DocRetrievalOutput, reasoning_effort=REASONING_EFFORT)
    return output, mapped


async def doc_retrieval_node(state: SupportGraphState) -> dict:
    """Reads: query, retrieval_retry_count, reflection_loopback_count.
    Writes: retrieved_chunks/tables/diagrams (full replacement, not a delta —
    see module docstring), retrieval_retry_count, reflection_loopback_count,
    final_answer (§4).

    reflection_loopback_count mechanics (resolved here, not left to
    graph.py's conditional edge, since LangGraph conditional-edge
    functions can only choose the next node — they cannot return a
    state update; only nodes can): this node is both the fresh-entry
    point AND the reflect→doc_retrieval loop-back TARGET, so it's the
    one place that can tell those two cases apart. `confidence_score`
    is set by reflect_node and by nothing else — its presence in
    incoming state is an unambiguous "this is a loop-back re-entry,
    not the first pass" signal, independent of whether evidence
    happened to be empty on the first pass. reflect_node itself never
    touches reflection_loopback_count (see reflect.py) — graph.py's
    conditional edge reads whatever value is already in state at the
    time it runs, which this node is solely responsible for keeping
    correct.
    """
    query = state["query"]
    history = state.get("chat_history") or []
    retry_count = state.get("retrieval_retry_count", 0)
    loopback_count = state.get("reflection_loopback_count", 0)
    is_loopback_reentry = state.get("confidence_score") is not None
    if is_loopback_reentry:
        loopback_count += 1

    # Real bug fix, found via manual QA: retrieval_mode is set once by
    # router_node right after classify_node and never touched again
    # anywhere else in the graph — so a "SQL" query whose first (SQL-alone)
    # answer reflect_node judges ungrounded, and which therefore loops back
    # to THIS node (the only way doc_retrieval_node ever runs for an
    # originally-SQL-routed query), kept displaying a stale "Route: SQL"
    # badge even though real documentation evidence was now also being
    # fetched and cited. Promoting to "Hybrid" here — the one place that
    # can tell "this is a SQL-origin loopback re-entry" apart from every
    # other case (see is_loopback_reentry above) — makes the badge reflect
    # what actually ran. A no-op for every other original mode: RAG re-runs
    # doc_retrieval_node on itself (already RAG), Hybrid/Critical already
    # include doc_retrieval_node in their initial fan-out so a loopback
    # re-entry there is just a same-mode retry, not a mode change.
    retrieval_mode_update: dict = {}
    if is_loopback_reentry and state.get("retrieval_mode") == "SQL":
        retrieval_mode_update["retrieval_mode"] = "Hybrid"

    # §31 Layer B — independent, non-LLM sanity check. Doesn't hard-block
    # (Layer A/classify_node already gated out_of_scope before this node
    # ever ran) — instead feeds a skepticism note into the SAME prompt,
    # letting §14's existing grounded-refusal mechanism do the actual
    # refusing if the evidence really doesn't support an answer. Logged
    # as a visible signal either way (§16.1's established pattern for
    # guardrail-adjacent events), not a silent pass-through.
    scope_note = ""
    try:
        query_embedding = await embed_text(query)
        centroid = await get_cached_centroid()
        if not is_in_scope(query_embedding, centroid):
            scope_note = (
                "NOTE: this query's topical similarity to the support corpus is unusually low. "
                "If the retrieved evidence below doesn't clearly relate to enterprise software "
                "support, treat it as out of scope and say so rather than answering from general "
                "knowledge."
            )
            log_event(logger, "WARNING", "scope_guardrail_layer_b_flagged", query=query)
    except ValueError:
        # No embedded corpus yet (e.g. a fresh/unseeded DB) — Layer B
        # can't run without one; fail open rather than blocking every
        # query on an ingestion precondition unrelated to this request.
        log_event(logger, "WARNING", "scope_guardrail_layer_b_unavailable")

    account_context = state.get("account_narrative")
    output, mapped = await _run_one_attempt(query, history, scope_note, account_context)

    all_scores = [r.score for r in (mapped["chunks"] + mapped["tables"] + mapped["diagrams"])]
    top_score = max(all_scores, default=0.0)
    should_retry = (
        not output.evidence_sufficient
        and top_score < FUSION_RETRY_THRESHOLD
        and retry_count < MAX_RETRIEVAL_RETRIES
        and output.rewritten_query
    )
    if should_retry:
        retry_count += 1
        output, mapped = await _run_one_attempt(output.rewritten_query, history, scope_note, account_context)

    cited_ids = set(output.cited_source_ids)
    for item_id, (_, item) in mapped["by_id"].items():
        if item_id in cited_ids:
            item.cited = True

    return {
        "retrieved_chunks": mapped["chunks"],
        "retrieved_tables": mapped["tables"],
        "retrieved_diagrams": mapped["diagrams"],
        "retrieval_retry_count": retry_count,
        "reflection_loopback_count": loopback_count,
        "final_answer": output.draft_answer,
        "doc_evidence_sufficient": output.evidence_sufficient,
        **retrieval_mode_update,
    }
