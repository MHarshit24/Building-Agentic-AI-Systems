"""
app/orchestration/nodes/respond.py

Response Formatter (§3 roster #8 / §2.3). Pure deterministic Python —
no LLM call, no prompt file (see this project's own Stage 5 plan,
"Architecture confirmations" #2, for why this file has no _v1.py
counterpart).

final_answer is already set by doc_retrieval_node/account_validation_node
(whichever ran as the sole content-producing agent — Stage 5's
draft_answer precedent, Stage 6's Deviation K for the SQL-alone case) —
this node never touches it. The real work here is exactly what §2.3 says
needs "zero LLM reasoning" but still needs doing: filtering the three
retrieved-item lists for the `cited` flag doc_retrieval_node set on them,
mapping the survivors into SourceRef objects, and (Stage 6) adding one
`sql`-type SourceRef per sql_results row — unconditionally, no `cited`
filter, since §14 point 1 already establishes SQL facts as grounded by
construction (no hallucination-verification need the way RAG chunks
have).
"""

from __future__ import annotations

from app.orchestration.nodes.router import decide_action, resolve_effective_severity
from app.schemas.agent_contracts import SourceRef
from app.schemas.state import SupportGraphState


def _sources_from(items: list, type_label: str) -> list[SourceRef]:
    return [
        SourceRef(
            type=type_label,
            source_document=item.source_document,
            section_header=item.section_header,
            page_number=item.page_number,
        )
        for item in items
        if item.cited
    ]


def _sql_sources_from(sql_results: list[dict]) -> list[SourceRef]:
    """Filtered by `cited`, same as chunks/tables/diagrams — account_
    validation_node marks this per-row from its own cited_record_ids
    output (see that module's own docstring for why "every fetched row
    unconditionally" was real citation noise in practice, especially for
    get_incidents()'s region-wide, not account-specific, results).
    `_source_table`/`_record_id` are the deterministic bookkeeping keys
    sql_tools/queries.py tags every returned dict with, never LLM-derived —
    only the `cited` flag itself comes from the LLM's own judgment."""
    return [
        SourceRef(type="sql", table=row["_source_table"], record_id=row["_record_id"])
        for row in sql_results
        if row.get("cited")
    ]


async def respond_node(state: SupportGraphState) -> dict:
    """Reads: retrieved_chunks/tables/diagrams (filtered for cited=True),
    sql_results (unconditionally — no cited filter), severity_final/
    severity_initial, confidence_tier. Writes: sources,
    flagged_for_review — final_answer is left untouched (already set by
    doc_retrieval_node).

    flagged_for_review is recomputed here (not just read) because §6.1's
    matrix has a "respond, but flag for QA" outcome (Medium confidence or
    High severity) that graph.py's post-reflect conditional edge only used
    to pick the *next node*, never to write state — conditional-edge
    functions can't. Whichever terminal node actually runs (this one, or
    escalate_node) is responsible for recomputing decide_action itself
    and persisting the result."""
    severity = resolve_effective_severity(state.get("severity_final"), state.get("severity_initial"))
    _, flagged_for_review = decide_action(severity, state.get("confidence_tier"))

    sources = (
        _sources_from(state.get("retrieved_chunks") or [], "chunk")
        + _sources_from(state.get("retrieved_tables") or [], "table")
        + _sources_from(state.get("retrieved_diagrams") or [], "diagram")
        + _sql_sources_from(state.get("sql_results") or [])
    )
    return {"sources": sources, "flagged_for_review": flagged_for_review}
