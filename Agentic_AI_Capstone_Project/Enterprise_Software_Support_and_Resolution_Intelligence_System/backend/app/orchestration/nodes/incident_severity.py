"""
app/orchestration/nodes/incident_severity.py

Incident Severity Agent (§3 roster #5). Genuinely conditional — only
invoked when graph.py's `_needs_incident_severity` predicate (router.py)
is true (category in incident/security, or retrieval_mode == "Critical",
§11's SEVCHECK diamond), never on every graph run. Full agent
implementation lives in this one file: the deterministic
`get_active_incidents()` tool call, the `read_diagram_graph()` helper
(below — a single exact-match lookup against DiagramGraphRow, not a
sql_tools whitelist concern: no injection surface, a caller-supplied
literal compared via `==`, never interpolated, and not customer business
data — see Stage 6 plan's own reasoning for why this lives here instead
of sql_tools/queries.py), prompt assembly, the structured-output LLM
call, and the state-update return.

reasoning_effort="medium" per §13: "genuinely benefits from more careful
cross-referencing (active incidents vs. reported symptoms)."
"""

from __future__ import annotations

import json
import logging

from sqlalchemy import select

from app.db.models import DiagramGraphRow
from app.db.session import async_session_maker
from app.llm.structured_output import call_llm_structured
from app.logging.structured_logger import log_event
from app.prompts._shared import flatten_messages
from app.prompts.loader import get_build_prompt
from app.schemas.agent_contracts import IncidentSeverityOutput
from app.schemas.state import SupportGraphState
from app.sql_tools.queries import get_active_incidents

logger = logging.getLogger(__name__)

REASONING_EFFORT = "medium"


async def read_diagram_graph(diagram_type: str) -> dict | None:
    """Single exact-match lookup, not a sql_tools whitelist concern (see
    module docstring): a caller-supplied literal compared via `==`."""
    async with async_session_maker() as db:
        result = await db.execute(select(DiagramGraphRow.graph_json).where(DiagramGraphRow.diagram_type == diagram_type))
        return result.scalar_one_or_none()


def _format_sql_results(sql_results: list[dict] | None) -> str:
    if not sql_results:
        return ""
    cleaned = [{k: v for k, v in row.items() if not k.startswith("_")} for row in sql_results]
    return json.dumps(cleaned, default=str)


def _format_incidents(incidents: list[dict]) -> str:
    if not incidents:
        return ""
    cleaned = [{k: v for k, v in row.items() if not k.startswith("_")} for row in incidents]
    return json.dumps(cleaned, default=str)


async def incident_severity_node(state: SupportGraphState) -> dict:
    """Reads: category, severity_initial, sql_results (already populated
    by account_validation_node — this node only runs after the fan-out
    converges, so it's guaranteed present). Writes: severity_final only
    (severity_reasoning is logged, not persisted — no state.py field
    exists for it, §4's actual contract checked directly)."""
    query = state["query"]
    history = state.get("chat_history") or []
    severity_initial = state.get("severity_initial")
    sql_results = state.get("sql_results") or []

    active_incidents = await get_active_incidents()
    escalation_hierarchy = await read_diagram_graph("escalation_hierarchy")

    build_prompt = get_build_prompt("incident_severity")
    messages = build_prompt(
        static_ctx={},
        dynamic_ctx={
            "query": query,
            "history": history,
            "severity_initial": severity_initial,
            "sql_results": _format_sql_results(sql_results),
            "active_incidents": _format_incidents(active_incidents),
            "escalation_hierarchy": json.dumps(escalation_hierarchy) if escalation_hierarchy else None,
        },
    )
    prompt = flatten_messages(messages)
    output: IncidentSeverityOutput = await call_llm_structured(
        prompt, IncidentSeverityOutput, reasoning_effort=REASONING_EFFORT
    )

    log_event(
        logger,
        "INFO",
        "incident_severity_reasoning",
        severity_final=output.severity_final,
        severity_reasoning=output.severity_reasoning,
    )

    return {"severity_final": output.severity_final}
