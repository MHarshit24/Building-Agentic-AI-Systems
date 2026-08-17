"""
app/api/routes_chat.py

POST /chat — §17, §29. Authenticated (support_agent|admin), rate-limited
20/minute per user (§16.1). Runs the full LangGraph state machine
end-to-end for the first time in this project.

Conversation history (§29): if `conversation_id` is supplied, prior
`Message` rows for it are loaded (same query `routes_conversations.py`
already uses) and mapped into `chat_history` before the graph runs; if
omitted, a new UUID is generated and this becomes the first turn of a
new `Conversation`. Both the user's turn and the assistant's turn are
persisted after the graph completes — not before, since the assistant
`Message` row needs the graph's own output (trace_id, confidence_tier,
sources, escalation_flag) to be complete.

trace_id (§15, Stage 8): a real langfuse.create_trace_id() value (falls
back to Stage 5's plain UUID scheme internally if that call itself fails
— see app/observability/tracing.py's safe_create_trace_id()).
bind_trace_id() is still called with it so structured logging correlation
keeps working exactly as before. Also used as the checkpointer's
thread_id (§40 — "keyed by trace_id") once a real graph.ainvoke() runs.

Escalation notification (§7, §12, Stage 7): when the graph returns
escalation_flag=True, an EscalationLog row is inserted and
notify_human() is scheduled via FastAPI BackgroundTasks — never
awaited inline — so it runs strictly AFTER this handler returns and the
response has been sent, matching §12's sequence diagram exactly
(escalate_node only drafts; this is the only place notify_human() is
ever called). `background_tasks: BackgroundTasks` mirrors
routes_ingest.py's existing pattern for the same primitive.

POST /chat/stream (A6, frontend integration pass) — SSE endpoint for the
frontend's live workflow diagram. Everything from "the graph has produced
its final state" onward (severity resolution, persistence, escalation
handling, ChatResponse construction) is identical to POST /chat by
construction, not convention: both call the same _persist_and_finalize()
helper, extracted from what used to be inline in chat() below. Verified
behaviorally identical via tests/integration/test_graph_e2e.py's full
suite, run before and after this refactor with no diff in results.

_persist_and_finalize() itself never calls .ainvoke()/.astream() — it
receives the graph's already-final merged state dict either way, so it
has no idea (and doesn't need to) whether it was reached via the unary
or the streaming path.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from collections.abc import AsyncGenerator

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Conversation, ConversationStatus, EscalationLog, Message
from app.db.session import get_db
from app.logging.structured_logger import bind_trace_id, log_event
from app.mcp_client.notification_client import notify_human
from app.middleware.rate_limit import limiter
from app.middleware.rbac_check import require_support_or_admin
from app.observability import tracing
from app.orchestration.graph import GRAPH_RECURSION_LIMIT, graph as _fallback_graph
from app.orchestration.nodes.escalate import build_ticket_context
from app.orchestration.nodes.router import resolve_effective_severity
from app.schemas.chat import ChatRequest, ChatResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

# Fields worth putting in each SSE "node" frame — a curated subset, not the
# entire accumulated state, so frames stay small and frontend-relevant
# (matches blueprint §35's "curated reasoning trace, never raw logs" spirit).
_STREAM_STATE_FIELDS = (
    "category",
    "retrieval_mode",
    "severity_initial",
    "severity_final",
    "confidence_score",
    "confidence_tier",
    "escalation_flag",
    "retrieval_retry_count",
    "reflection_loopback_count",
)


# Safety net, not just a prompt hope: doc_retrieval_v1.py's and account_
# validation_v1.py's prompts both instruct the LLM to cite exclusively via
# a separate structured field, never inline — but LLM prompt-following
# isn't 100% reliable (confirmed in practice: an answer came back with
# "...resolve it [table_11][chunk_15]." embedded in the prose). sources[]
# (built by respond_node from cited_source_ids/cited_record_ids, rendered
# by the frontend as citation badges) is the correct, already-structured
# channel for this — raw [id] tags belong in logs/traces only, never in
# user-facing text, regardless of what the model actually did this time.
#
# Matches any [word(s)_digits] shape generically — not hardcoded to
# chunk/table/diagram/sql — so it also covers account_validation's
# [customers_5]/[support_tickets_42]/[incident_logs_7] tags without
# needing every table name enumerated here individually.
_CITATION_TAG_PATTERN = re.compile(r"\[[a-z][a-z_]*_\d+\]")


def _strip_citation_markers(text: str) -> str:
    if not text:
        return text
    cleaned = _CITATION_TAG_PATTERN.sub("", text)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r" +([.,;:!?])", r"\1", cleaned)
    cleaned = re.sub(r"[ \t]*\n[ \t]*", "\n", cleaned)
    return cleaned.strip()


async def _load_chat_history(db: AsyncSession, conversation_id: str) -> list[dict]:
    # order_by(created_at) ALONE is not a stable sort for same-turn message
    # pairs: _persist_and_finalize() below inserts the user and assistant
    # Message rows in the same transaction, and Message.created_at's
    # server_default=func.now() returns Postgres's transaction timestamp —
    # the SAME value for every statement in that transaction, not a fresh
    # per-row clock read. That real, confirmed tie is why turns
    # intermittently rendered assistant-before-user in the frontend
    # ("only some chats, not all" — exactly what an unresolved sort tie
    # looks like, since Postgres doesn't guarantee tie order across
    # queries). message_id (an autoincrement PK, assigned in insertion
    # order — user always added before assistant, see
    # _persist_and_finalize()) is a real, deterministic secondary sort key.
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc(), Message.message_id.asc())
    )
    return [{"role": m.role, "content": m.content} for m in result.scalars().all()]


def _build_initial_state(
    body: ChatRequest, chat_history: list[dict], user: dict, conversation_id: str, trace_id: str
) -> dict:
    """Shared by both POST /chat and POST /chat/stream — identical starting
    SupportGraphState either way."""
    return {
        "query": body.query,
        "chat_history": chat_history,
        "customer_id": body.customer_id,
        "handled_by_user_id": user["user_id"],
        "category": None,
        "conversation_id": conversation_id,
        "severity_initial": None,
        "severity_final": None,
        "retrieval_mode": None,
        "explicit_human_request": False,
        "retrieved_chunks": [],
        "retrieved_tables": [],
        "retrieved_diagrams": [],
        "sql_results": [],
        "account_narrative": None,
        "doc_evidence_sufficient": None,
        "account_evidence_sufficient": None,
        "confidence_score": None,
        "confidence_tier": None,
        "groundedness_flag": None,
        "retrieval_retry_count": 0,
        "reflection_loopback_count": 0,
        "escalation_flag": False,
        "flagged_for_review": False,
        "notification_sent": False,
        "escalation_reason": None,
        "human_handoff_summary": None,
        "final_answer": None,
        "sources": [],
        "trace_id": trace_id,
    }


async def _persist_and_finalize(
    db: AsyncSession,
    background_tasks: BackgroundTasks,
    *,
    conversation_id: str,
    is_new_conversation: bool,
    body: ChatRequest,
    user: dict,
    trace_id: str,
    result: dict,
) -> ChatResponse:
    """Everything that happens once the graph has produced its final merged
    state, shared verbatim by POST /chat and POST /chat/stream (A6): severity
    resolution, Conversation/Message persistence (full reasoning trace, A3),
    escalation logging + non-blocking notify_human dispatch, and
    ChatResponse construction. One function, not two call sites kept in
    sync by convention — that's the actual guarantee that both endpoints
    stay behaviorally identical.
    """
    severity = resolve_effective_severity(result.get("severity_final"), result.get("severity_initial"))

    raw_answer = result.get("final_answer") or ""
    answer = _strip_citation_markers(raw_answer)
    if answer != raw_answer:
        log_event(logger, "INFO", "citation_markers_stripped_from_answer", trace_id=trace_id, raw_answer=raw_answer)

    if is_new_conversation:
        db.add(
            Conversation(
                conversation_id=conversation_id,
                customer_id=body.customer_id,
                handled_by_user_id=user["user_id"],
                status=ConversationStatus.escalated if result.get("escalation_flag") else ConversationStatus.open,
            )
        )
    else:
        conv_result = await db.execute(select(Conversation).where(Conversation.conversation_id == conversation_id))
        conversation = conv_result.scalar_one_or_none()
        if conversation is not None and result.get("escalation_flag"):
            conversation.status = ConversationStatus.escalated

    db.add(Message(conversation_id=conversation_id, role="user", content=body.query, trace_id=trace_id))
    db.add(
        Message(
            conversation_id=conversation_id,
            role="assistant",
            content=answer,
            trace_id=trace_id,
            confidence_tier=result.get("confidence_tier"),
            escalation_flag=bool(result.get("escalation_flag")),
            sources_json=[s.model_dump() for s in result.get("sources", [])],
            # Frontend integration pass (A3): these were already computed for
            # ChatResponse below but never persisted, so GET /conversations/{id}
            # could only show a stripped-down trace for past turns.
            category=result.get("category"),
            severity=severity,
            retrieval_mode=result.get("retrieval_mode"),
            confidence_score=result.get("confidence_score"),
            flagged_for_review=bool(result.get("flagged_for_review")),
        )
    )

    if result.get("escalation_flag"):
        ticket_context = build_ticket_context(result)
        escalation_row = EscalationLog(
            trace_id=trace_id,
            handled_by_user_id=user["user_id"],
            ticket_context_json=ticket_context,
            reason=result.get("escalation_reason") or "unspecified",
        )
        db.add(escalation_row)
        await db.flush()  # populate escalation_row.escalation_id before it's captured below

        background_tasks.add_task(
            notify_human,
            escalation_id=escalation_row.escalation_id,
            ticket_context=ticket_context,
            reason=result.get("escalation_reason"),
            summary=result.get("human_handoff_summary"),
        )

    await db.commit()

    tracing.safe_flush()  # §15: "Flush | langfuse.flush() at request teardown"

    return ChatResponse(
        answer=answer,
        category=result.get("category"),
        severity=severity,
        retrieval_mode=result.get("retrieval_mode"),
        confidence_score=result.get("confidence_score"),
        confidence_tier=result.get("confidence_tier"),
        sources=result.get("sources", []),
        escalated=bool(result.get("escalation_flag")),
        flagged_for_review=bool(result.get("flagged_for_review")),
        trace_id=trace_id,
        conversation_id=conversation_id,
        retrieval_retry_count=result.get("retrieval_retry_count") or 0,
        reflection_loopback_count=result.get("reflection_loopback_count") or 0,
    )


@router.post("", response_model=ChatResponse)
@limiter.limit("20/minute")
async def chat(
    request: Request,
    background_tasks: BackgroundTasks,
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_support_or_admin),
) -> ChatResponse:
    is_new_conversation = body.conversation_id is None
    conversation_id = body.conversation_id or str(uuid.uuid4())
    trace_id = tracing.safe_create_trace_id()
    bind_trace_id(trace_id)

    chat_history = [] if is_new_conversation else await _load_chat_history(db, conversation_id)
    initial_state = _build_initial_state(body, chat_history, user, conversation_id, trace_id)

    # Prefer the real, checkpointer-backed graph built at FastAPI startup
    # (app/main.py's lifespan, stored on app.state.graph); fall back to
    # the plain module-level singleton for contexts where that lifespan
    # never ran (this project's own test client uses ASGITransport,
    # which doesn't trigger startup events).
    active_graph = getattr(request.app.state, "graph", None) or _fallback_graph
    try:
        result = await active_graph.ainvoke(
            initial_state,
            config={"recursion_limit": GRAPH_RECURSION_LIMIT, "configurable": {"thread_id": trace_id}},
        )
    except Exception as exc:  # noqa: BLE001 — real, disclosed gap this closes (§37): this endpoint
        # used to have no protection at all, unlike /chat/stream's SSE error frame. A real failure
        # here (LLM API outage, rate limit, or any other unhandled graph-execution exception) must
        # not surface as an opaque, undifferentiated FastAPI 500 with a raw traceback — a 503 with a
        # clear message tells the client this was an external-dependency failure, not a client error.
        logger.exception("chat request failed mid-run", extra={"trace_id": trace_id})
        raise HTTPException(
            status_code=503,
            detail="The support assistant is temporarily unavailable — please try again shortly.",
        ) from exc

    return await _persist_and_finalize(
        db,
        background_tasks,
        conversation_id=conversation_id,
        is_new_conversation=is_new_conversation,
        body=body,
        user=user,
        trace_id=trace_id,
        result=result,
    )


def _sse_frame(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def _chat_event_stream(
    request: Request,
    background_tasks: BackgroundTasks,
    body: ChatRequest,
    db: AsyncSession,
    user: dict,
) -> AsyncGenerator[str, None]:
    is_new_conversation = body.conversation_id is None
    conversation_id = body.conversation_id or str(uuid.uuid4())
    trace_id = tracing.safe_create_trace_id()
    bind_trace_id(trace_id)

    chat_history = [] if is_new_conversation else await _load_chat_history(db, conversation_id)
    initial_state = _build_initial_state(body, chat_history, user, conversation_id, trace_id)

    active_graph = getattr(request.app.state, "graph", None) or _fallback_graph

    accumulated: dict = dict(initial_state)
    try:
        async for step in active_graph.astream(
            initial_state,
            config={"recursion_limit": GRAPH_RECURSION_LIMIT, "configurable": {"thread_id": trace_id}},
            stream_mode="updates",
        ):
            # `step` is {node_name: state_delta}. For Hybrid/Critical mode's
            # concurrent Send fan-out (doc_retrieval_node + account_validation_node),
            # this may carry one or two entries depending on LangGraph's own
            # batching of that superstep — confirmed empirically (A6 plan's
            # flagged risk #1) via test_chat_stream.py's Hybrid-mode test,
            # which asserts both node names arrive as SSE "node" events
            # regardless of how many entries land in a single `step`. Iterating
            # step.items() handles both shapes identically, one frame per node.
            for node_name, delta in step.items():
                if not isinstance(delta, dict):
                    continue
                accumulated.update(delta)
                frame_payload = {"node": node_name}
                frame_payload.update({field: delta[field] for field in _STREAM_STATE_FIELDS if field in delta})
                yield _sse_frame("node", frame_payload)
    except Exception as exc:  # noqa: BLE001 — must not leave the client hanging on any failure
        logger.exception("chat stream failed mid-run", extra={"trace_id": trace_id})
        yield _sse_frame("error", {"message": str(exc)})
        return

    response = await _persist_and_finalize(
        db,
        background_tasks,
        conversation_id=conversation_id,
        is_new_conversation=is_new_conversation,
        body=body,
        user=user,
        trace_id=trace_id,
        result=accumulated,
    )
    yield _sse_frame("done", response.model_dump())


@router.post("/stream")
@limiter.limit("20/minute")
async def chat_stream(
    request: Request,
    background_tasks: BackgroundTasks,
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_support_or_admin),
) -> StreamingResponse:
    """SSE, not a plain JSON response — no response_model, since the body is
    a sequence of `event: node` frames terminated by one `event: done` frame
    whose data is the same ChatResponse shape POST /chat returns. Auth uses
    a normal Authorization header (this is a POST, not something browsers'
    native EventSource — GET-only, no custom headers — could drive anyway);
    the frontend reads the streamed body via fetch() and parses SSE frames
    itself (A6 plan's documented reason for not using EventSource here)."""
    return StreamingResponse(
        _chat_event_stream(request, background_tasks, body, db, user),
        media_type="text/event-stream",
    )
