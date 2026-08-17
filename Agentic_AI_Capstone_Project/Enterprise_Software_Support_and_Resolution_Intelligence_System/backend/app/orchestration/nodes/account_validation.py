"""
app/orchestration/nodes/account_validation.py

Account Validation Agent (§3 roster #4). Runs for SQL/Hybrid/Critical
(Stage 6 plan, Gap 1's resolution — SQL alone via a single graph edge,
Hybrid/Critical via genuine concurrent Send fan-out alongside
doc_retrieval_node). Full agent implementation lives in this one file:
deterministic tool calls (get_customer/get_tickets/get_incidents — never
LLM-invoked, same "pre-fetched, not tool-called" shape doc_retrieval.py
already established), prompt assembly, the structured-output LLM call,
PII redaction, and the state-update return.

reasoning_effort="minimal" per §13: "narrates structured query results,
doesn't need deliberation."
"""

from __future__ import annotations

import json
import logging

from app.guardrails.pii import redact_pii
from app.llm.structured_output import call_llm_structured
from app.prompts._shared import flatten_messages
from app.prompts.loader import get_build_prompt
from app.schemas.agent_contracts import AccountValidationOutput
from app.schemas.state import SupportGraphState
from app.sql_tools.queries import get_customer, get_incidents, get_tickets

logger = logging.getLogger(__name__)

REASONING_EFFORT = "minimal"


def _format_evidence(rows: list[dict] | dict | None) -> str:
    """Labels each row with a [table_id] citation tag (e.g. [customers_5],
    [incident_logs_7]) built from the `_source_table`/`_record_id`
    bookkeeping keys — same [id] labeling technique doc_retrieval.py
    already uses for chunks/tables/diagrams, so the LLM can cite specific
    records in cited_record_ids instead of every fetched row becoming a
    source unconditionally (see agent_contracts.py's SourceRef docstring
    for why that used to be a real citation-noise problem, especially for
    get_incidents()'s region-wide, not account-specific, results). The
    bookkeeping keys themselves are still stripped from the JSON body —
    the LLM only needs the [id] label, not the raw _source_table/
    _record_id fields duplicated inside the object too."""
    if not rows:
        return ""
    items = rows if isinstance(rows, list) else [rows]
    lines = []
    for row in items:
        record_id = f"{row['_source_table']}_{row['_record_id']}"
        cleaned = {k: v for k, v in row.items() if not k.startswith("_")}
        lines.append(f"[{record_id}] {json.dumps(cleaned, default=str)}")
    return "\n".join(lines)


async def account_validation_node(state: SupportGraphState) -> dict:
    """Reads: query, customer_id, retrieval_mode (to decide whether this
    node owns final_answer this turn — Stage 6 Deviation K). Writes:
    sql_results (always), account_narrative (always — frontend integration
    pass bugfix, see state.py's own field docstring for why this exists
    separately), final_answer (only when retrieval_mode=="SQL", the
    sole-responder case — never directly in Hybrid/Critical, where
    doc_retrieval_node already owns that key and both nodes writing it
    would be a concurrent-write conflict on the same LangGraph superstep;
    reflect_node folds account_narrative in afterward instead)."""
    query = state["query"]
    customer_id = state.get("customer_id")
    history = state.get("chat_history") or []
    retrieval_mode = state.get("retrieval_mode")

    customer = await get_customer(customer_id) if customer_id is not None else None
    tickets = await get_tickets(customer_id) if customer_id is not None else []
    incidents = await get_incidents(customer_id) if customer_id is not None else []

    sql_results: list[dict] = ([customer] if customer else []) + tickets + incidents

    build_prompt = get_build_prompt("account_validation")
    messages = build_prompt(
        static_ctx={},
        dynamic_ctx={
            "query": query,
            "history": history,
            "customer": _format_evidence(customer),
            "tickets": _format_evidence(tickets),
            "incidents": _format_evidence(incidents),
        },
    )
    prompt = flatten_messages(messages)
    output: AccountValidationOutput = await call_llm_structured(
        prompt, AccountValidationOutput, reasoning_effort=REASONING_EFFORT
    )

    narrative = await redact_pii(output.narrative)

    # Same cited-marking technique doc_retrieval_node uses for chunks/
    # tables/diagrams — respond_node's _sql_sources_from() now filters on
    # this instead of surfacing every fetched row unconditionally.
    cited_ids = set(output.cited_record_ids)
    for row in sql_results:
        row["cited"] = f"{row['_source_table']}_{row['_record_id']}" in cited_ids

    result: dict = {
        "sql_results": sql_results,
        "account_narrative": narrative,
        "account_evidence_sufficient": output.evidence_sufficient,
    }
    if retrieval_mode == "SQL":
        result["final_answer"] = narrative
    return result
