"""
app/orchestration/nodes/escalate.py

Escalation Manager (§3 roster #7) — Stage 7 upgrades this from Stage 5's
deliberately minimal, non-LLM formatter (Deviation A) into the real
§39.3 LLM agent: a genuine call_llm_structured() call drafting
escalation_reason/human_handoff_summary, per §13's reasoning_effort="low"
assignment ("drafting a handoff summary, not solving a hard problem")
which only makes sense for a real LLM call.

Two audiences, kept explicitly separate (see prompts/escalate_v1.py's own
docstring too): escalation_reason is an internal/audit string
(-> escalation_log.reason, §21); human_handoff_summary is written for the
human agent picking up the ticket (-> the notification email body /
ticket_context_json). Neither is customer-facing. The customer-facing
final_answer stays Stage 5's fixed/templated text, deliberately NOT
replaced by this LLM's prose — a real decision, not an oversight: nothing
in the blueprint asks for customer-facing text to change this stage, and
Stage 5's existing text already correctly distinguishes the
explicit-human-request framing from the generic one.

This node does NOT call notify_human() or touch the MCP server — per
§12's sequence diagram, that dispatch happens in routes_chat.py, via
FastAPI BackgroundTasks, only AFTER the graph has returned and the
response has been persisted. Calling it here would block the response,
directly violating §7's "email delivery latency never counts against
P95." escalate_node has no DB access and never imports the MCP client.

Deliberately NOT wrapped in graph.py's generic _guard_structured_output,
unlike every other LLM node — this node catches its own
StructuredOutputError internally instead. escalate_node is the graph's
last line of defense (terminal, straight to END, no downstream
conditional edge to retry through), so its own robustness can't depend
on the same generic mechanism whose failure path routes THROUGH
escalate_node; that generic guard's fallback also only sets
escalation_flag, never final_answer, which would return an empty answer
to the user if reached via re-entry here with nothing else set.
"""

from __future__ import annotations

import logging

import openai

from app.llm.structured_output import StructuredOutputError, call_llm_structured, is_content_filter_error
from app.logging.structured_logger import log_event
from app.orchestration.nodes.router import decide_action, resolve_effective_severity
from app.prompts._shared import flatten_messages
from app.prompts.loader import get_build_prompt
from app.schemas.agent_contracts import EscalationOutput
from app.schemas.state import SupportGraphState

logger = logging.getLogger(__name__)

REASONING_EFFORT = "low"

_FALLBACK_ESCALATION_REASON = "Escalation triggered; the system could not generate a detailed escalation summary."
_FALLBACK_HANDOFF_SUMMARY = (
    "Automated summary generation failed for this escalation. Please review the conversation "
    "history and query directly."
)


def _customer_facing_answer(state: SupportGraphState) -> str:
    """Unchanged from Stage 5 — see module docstring for why this stays
    fixed/templated rather than using the LLM's own prose."""
    if state.get("explicit_human_request"):
        return (
            "You've been connected with a human support specialist, as requested — "
            "they'll follow up with you shortly."
        )
    return (
        "This request has been escalated to a human support specialist and will be "
        "addressed shortly. No automated answer could be confidently generated."
    )


def build_ticket_context(result: dict) -> dict:
    """Deterministic, non-LLM — README's "full context transfer" requirement,
    mapped onto real SupportGraphState fields (Stage 7 plan's own explicit
    mapping table), nothing invented. Called by routes_chat.py AFTER
    graph.ainvoke() returns, since it draws from the full result dict, not
    just this node's own contribution — the same reason ChatResponse is
    already assembled at the API layer, not inside any single node.

    Mapping:
      ticket history            -> query + chat_history
      retrieved documentation   -> retrieved_chunks/tables/diagrams
      structured account data   -> sql_results (already _source_table/
                                    _record_id-tagged since Stage 6)
      incident logs             -> also sql_results — Stage 6 already
                                    unified get_incidents/get_active_incidents
                                    rows into this one field; no separate
                                    field needed
      agent reasoning trace     -> category/severity/retrieval_mode/
                                    confidence/groundedness/retry-and-
                                    loopback counts/escalation_reason
    """

    def _evidence_item(item) -> dict:
        return {
            "source_document": item.source_document,
            "section_header": item.section_header,
            "page_number": item.page_number,
            "cited": item.cited,
            "text": item.text[:500],
        }

    retrieved_documentation = [
        _evidence_item(item)
        for item in (
            (result.get("retrieved_chunks") or [])
            + (result.get("retrieved_tables") or [])
            + (result.get("retrieved_diagrams") or [])
        )
    ]

    return {
        "query": result.get("query"),
        "chat_history": result.get("chat_history") or [],
        "customer_id": result.get("customer_id"),
        "conversation_id": result.get("conversation_id"),
        "trace_id": result.get("trace_id"),
        "handled_by_user_id": result.get("handled_by_user_id"),
        "category": result.get("category"),
        "severity_initial": result.get("severity_initial"),
        "severity_final": result.get("severity_final"),
        "retrieval_mode": result.get("retrieval_mode"),
        "explicit_human_request": result.get("explicit_human_request"),
        "confidence_score": result.get("confidence_score"),
        "confidence_tier": result.get("confidence_tier"),
        "groundedness_flag": result.get("groundedness_flag"),
        "retrieval_retry_count": result.get("retrieval_retry_count"),
        "reflection_loopback_count": result.get("reflection_loopback_count"),
        "retrieved_documentation": retrieved_documentation,
        "structured_account_data": result.get("sql_results") or [],
        "final_answer_draft": result.get("final_answer"),
        "escalation_reason": result.get("escalation_reason"),
        "human_handoff_summary": result.get("human_handoff_summary"),
    }


async def escalate_node(state: SupportGraphState) -> dict:
    """Reads: full state — category, severity_initial/severity_final,
    confidence_score/confidence_tier, groundedness_flag, retrieval_mode,
    query, chat_history, final_answer, explicit_human_request,
    retrieval_retry_count, reflection_loopback_count (§3 roster row 7:
    "Reads: full state, confidence_score, severity_final").
    Writes: escalation_flag, flagged_for_review, notification_sent
    (stays False — the real outcome is only knowable after routes_chat.py's
    BackgroundTask runs, well past graph completion), final_answer,
    escalation_reason, human_handoff_summary."""
    severity = resolve_effective_severity(state.get("severity_final"), state.get("severity_initial"))
    confidence_tier = state.get("confidence_tier")
    _, flagged_for_review = decide_action(severity, confidence_tier)

    build_prompt = get_build_prompt("escalate")
    messages = build_prompt(
        static_ctx={},
        dynamic_ctx={
            "query": state["query"],
            "history": state.get("chat_history") or [],
            "category": state.get("category"),
            "severity": severity,
            "confidence_tier": confidence_tier,
            "confidence_score": state.get("confidence_score"),
            "groundedness_flag": state.get("groundedness_flag"),
            "retrieval_mode": state.get("retrieval_mode"),
            "explicit_human_request": state.get("explicit_human_request", False),
            "draft_answer": state.get("final_answer"),
            "retrieval_retry_count": state.get("retrieval_retry_count", 0),
            "reflection_loopback_count": state.get("reflection_loopback_count", 0),
        },
    )
    prompt = flatten_messages(messages)

    try:
        output: EscalationOutput = await call_llm_structured(
            prompt, EscalationOutput, reasoning_effort=REASONING_EFFORT
        )
        escalation_reason = output.escalation_reason
        human_handoff_summary = output.human_handoff_summary
    except StructuredOutputError as exc:
        log_event(logger, "ERROR", "escalate_structured_output_failed", error=str(exc))
        escalation_reason = _FALLBACK_ESCALATION_REASON
        human_handoff_summary = _FALLBACK_HANDOFF_SUMMARY
    except openai.BadRequestError as exc:
        # Same real, confirmed gap as graph.py's _guard_structured_output
        # (see is_content_filter_error()'s own docstring) — escalate_node
        # is the graph's own last line of defense and embeds the raw
        # query in its own prompt too, so it can hit Azure's content
        # filter independently of whichever earlier node triggered the
        # escalation in the first place. Falls back to the same fixed
        # summary text as a StructuredOutputError failure here, per this
        # node's own established fallback pattern — a non-content-filter
        # BadRequestError still propagates (a real bug, not a refusal).
        if not is_content_filter_error(exc):
            raise
        log_event(logger, "ERROR", "escalate_content_filter_error", error=str(exc))
        escalation_reason = _FALLBACK_ESCALATION_REASON
        human_handoff_summary = _FALLBACK_HANDOFF_SUMMARY

    final_answer = state.get("final_answer") or _customer_facing_answer(state)

    return {
        "escalation_flag": True,
        "flagged_for_review": flagged_for_review,
        "notification_sent": False,
        "final_answer": final_answer,
        "escalation_reason": escalation_reason,
        "human_handoff_summary": human_handoff_summary,
    }
