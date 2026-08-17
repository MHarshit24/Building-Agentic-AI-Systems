"""
app/observability/tracing.py

Real Langfuse tracing (§15), built defensively from the start: this
project's own past experience is that Langfuse's v4 SDK has a real,
documented history of failing silently. Every single Langfuse call —
create_trace_id(), start_as_current_observation(), span.update(), the
context-manager's own __enter__/__exit__, create_score(), flush() — is
individually wrapped so a failure is caught, logged via log_event() at
the exact call site (never a bare `except: pass`), and never allowed to
break the real chat/ingestion work it's observing. Same philosophy §36
already established for MCP/Redis: tracing is an optimization, not a
dependency.

v4 API shape confirmed by direct introspection of the installed
langfuse==4.5.0 package, not assumed from docs:
  - Langfuse.create_trace_id() is a staticmethod.
  - client.start_as_current_observation(trace_context={"trace_id": ...},
    name=..., as_type="span", metadata=...) returns an OpenTelemetry
    context manager; entering it both returns the span object AND
    activates it as the current OTel span, so anything created inside
    (including auto-instrumented LLM calls via langfuse.openai, wired in
    app/llm/azure_client.py) nests as its child automatically.
  - There is NO dedicated call in this SDK version for trace-level
    metadata (langfuse._client.attributes.create_trace_attributes() only
    ever sets input/output/public — nothing in the installed package
    writes the langfuse.trace.metadata OTel attribute). §15's "trace
    metadata" is therefore attached as span-level metadata instead: once
    on classify_node's span (the first span of every chat_request trace)
    and again on whichever node is the trace's terminal span
    (respond_node / escalate_node / out_of_scope_refusal_node), so the
    final escalation_flag value is captured too.

Real, confirmed gap found and fixed here (not a precaution): every span
this module ever created only ever set `metadata=` — never Langfuse's
own dedicated `input=`/`output=` parameters, which is what the UI's
Preview tab actually displays prominently (confirmed directly against
the installed package: both start_as_current_observation() and
LangfuseSpan.update() accept input=/output= as genuine, independent
parameters, separate from metadata=, contrary to what the trace-level-
metadata finding above might suggest). Every span/trace showed "Input:
null" / "Output: undefined" in the real Langfuse UI as a result — not a
Langfuse limitation, a real gap in how this module called it. Fixed by
threading real input=/output= through traced()/traced_root_span()/
traced_child_span()/end_child_span(), alongside the existing metadata=
(kept, unchanged — request-context fields like request_id/session_id
are genuinely metadata, not input/output).
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Awaitable, Callable

from langfuse import Langfuse, get_client

from app.ingestion.hashing import hash_text
from app.logging.structured_logger import get_request_context, log_event
from app.schemas.state import SupportGraphState

logger = logging.getLogger(__name__)

NodeFn = Callable[[SupportGraphState], Awaitable[dict]]

# Node spans that are the terminal node of some path through the graph —
# the only spans that re-attach the full trace-metadata set (see module
# docstring: no dedicated trace-level metadata call exists in this SDK).
_TERMINAL_SPANS = {"respond", "escalate", "out_of_scope_refusal"}


def _safe_client() -> Langfuse | None:
    try:
        return get_client()
    except Exception as exc:
        log_event(logger, "WARNING", "langfuse_get_client_failed", error=str(exc))
        return None


def safe_create_trace_id(seed: str | None = None) -> str:
    """§15's real trace_id, replacing Stage 5's plain UUID placeholder
    (Deviation G). Falls back to the same UUID scheme on failure — every
    caller downstream (bind_trace_id, Message.trace_id, EscalationLog.
    trace_id, ChatResponse.trace_id, thread_id) sees a string either way."""
    try:
        return Langfuse.create_trace_id(seed=seed)
    except Exception as exc:
        log_event(logger, "WARNING", "langfuse_create_trace_id_failed", error=str(exc))
        return f"trace_{uuid.uuid4()}"


def _trace_metadata_fields(state: dict) -> dict[str, Any]:
    """§15's trace-metadata field list, built from SupportGraphState +
    the request-context contextvars (request_id/endpoint aren't part of
    graph state — see app/logging/structured_logger.py's get_request_context)."""
    ctx = get_request_context()
    customer_id = state.get("customer_id")
    return {
        "request_id": ctx.get("request_id"),
        "session_id": state.get("conversation_id"),
        "customer_id_hashed": hash_text(str(customer_id)) if customer_id is not None else None,
        "handled_by_user_id": state.get("handled_by_user_id"),
        "endpoint": ctx.get("endpoint"),
    }


def _span_input_metadata(span_name: str, state: dict) -> dict[str, Any] | None:
    if span_name == "classify":
        return _trace_metadata_fields(state)
    return None


def _span_result_metadata(span_name: str, state: dict, result: dict) -> dict[str, Any] | None:
    """Built from the merged post-node state (state + this node's own
    partial return) so a field the node itself didn't write this step
    (e.g. confidence_score before reflect_node ever runs) still reads
    from whatever's already in state, matching what LangGraph itself
    would present as "current state" to the next node."""
    merged = {**state, **result}
    metadata: dict[str, Any] = {}

    if span_name == "classify":
        metadata.update(
            category=merged.get("category"),
            confidence_score=merged.get("confidence_score"),
            confidence_tier=merged.get("confidence_tier"),
        )
    elif span_name == "router":
        metadata.update(retrieval_mode=merged.get("retrieval_mode"))
    elif span_name == "doc_retrieval":
        metadata.update(
            retrieval_mode=merged.get("retrieval_mode"),
            confidence_score=merged.get("confidence_score"),
            confidence_tier=merged.get("confidence_tier"),
            retry_count=merged.get("retrieval_retry_count"),
        )
    elif span_name == "account_validation":
        metadata.update(category=merged.get("category"), retrieval_mode=merged.get("retrieval_mode"))
    elif span_name == "incident_severity":
        metadata.update(
            category=merged.get("category"),
            severity_initial=merged.get("severity_initial"),
            severity_final=merged.get("severity_final"),
        )
    elif span_name == "reflect":
        metadata.update(
            confidence_score=merged.get("confidence_score"),
            confidence_tier=merged.get("confidence_tier"),
            retry_count=merged.get("reflection_loopback_count"),
        )
    elif span_name == "escalate":
        metadata.update(severity=merged.get("severity_final"), confidence_tier=merged.get("confidence_tier"))
    elif span_name == "respond":
        metadata.update(confidence_score=merged.get("confidence_score"), confidence_tier=merged.get("confidence_tier"))

    if span_name in _TERMINAL_SPANS:
        metadata.update(_trace_metadata_fields(merged))
        metadata["escalation_flag"] = bool(merged.get("escalation_flag", False))

    return metadata or None


def traced(node_fn: NodeFn, span_name: str) -> NodeFn:
    """Wraps a graph node so its execution becomes a Langfuse span.
    node_fn's own call is NEVER inside a try/except here — a real node
    exception (including whatever _guard_structured_output already turned
    into a normal {"escalation_flag": True} return, for the 5 nodes that
    have it) always propagates untouched. Only the Langfuse calls around
    it are individually guarded."""

    async def wrapper(state: SupportGraphState) -> dict:
        client = _safe_client()
        trace_id = state.get("trace_id")
        cm = span = None
        if client is not None and trace_id:
            try:
                cm = client.start_as_current_observation(
                    trace_context={"trace_id": trace_id},
                    name=span_name,
                    as_type="span",
                    input={"query": state.get("query")},
                    metadata=_span_input_metadata(span_name, state),
                )
                span = cm.__enter__()
            except Exception as exc:
                log_event(
                    logger, "WARNING", "langfuse_span_start_failed",
                    node=span_name, trace_id=trace_id, error=str(exc),
                )
                cm, span = None, None

        result = await node_fn(state)  # untouched — real exceptions propagate

        if span is not None:
            try:
                # output=result — the node's own real return dict, exactly
                # as returned, uniformly for every node. Deliberately not
                # a hand-curated per-node field list the way metadata=
                # below is: this stays automatically correct as nodes
                # evolve, with zero risk of a stale/incomplete field list.
                span.update(output=result, metadata=_span_result_metadata(span_name, state, result))
            except Exception as exc:
                log_event(
                    logger, "WARNING", "langfuse_span_update_failed",
                    node=span_name, trace_id=trace_id, error=str(exc),
                )
        if cm is not None:
            try:
                cm.__exit__(None, None, None)
            except Exception as exc:
                log_event(
                    logger, "WARNING", "langfuse_span_exit_failed",
                    node=span_name, trace_id=trace_id, error=str(exc),
                )

        return result

    wrapper.__name__ = node_fn.__name__
    return wrapper


def traced_root_span(
    name: str, trace_id: str, *, input: dict | None = None, metadata: dict | None = None
) -> tuple[Any, Any]:
    """Like traced_child_span, but for the FIRST span of a trace that has
    no node-shaped wrapper of its own (pipeline.py's ingestion trace —
    run_ingestion/​_process_document aren't graph nodes, so traced() doesn't
    apply). Needs an explicit trace_context, unlike every span nested
    inside one of these — those pick up OTel's already-active context.

    input= is Langfuse's own dedicated parameter (confirmed against the
    installed package — see module docstring), not folded into metadata=
    the way this project's own request-context fields are."""
    client = _safe_client()
    if client is None:
        return None, None
    try:
        cm = client.start_as_current_observation(
            trace_context={"trace_id": trace_id}, name=name, as_type="span", input=input, metadata=metadata
        )
        return cm, cm.__enter__()
    except Exception as exc:
        log_event(
            logger, "WARNING", "langfuse_root_span_start_failed",
            name=name, trace_id=trace_id, error=str(exc),
        )
        return None, None


def traced_child_span(name: str, *, input: dict | None = None, metadata: dict | None = None) -> tuple[Any, Any]:
    """For spans nested inside an already-active parent span, without
    their own node-shaped wrapper: hybrid_search() inside doc_retrieval_node,
    and each of ingestion's 8 named steps. Relies on OTel context
    propagation from the already-active parent — no explicit trace_context
    needed, it auto-attaches as a child. Returns (cm, span), both possibly
    None on failure; caller does its real work between acquiring this and
    calling end_child_span(), the real work itself never wrapped."""
    client = _safe_client()
    if client is None:
        return None, None
    try:
        cm = client.start_as_current_observation(name=name, as_type="span", input=input, metadata=metadata)
        return cm, cm.__enter__()
    except Exception as exc:
        log_event(logger, "WARNING", "langfuse_child_span_start_failed", name=name, error=str(exc))
        return None, None


def end_child_span(cm: Any, span: Any, *, output: Any = None, output_metadata: dict | None = None) -> None:
    """output= is Langfuse's own dedicated field (see module docstring) —
    the real, substantive result of whatever this span wrapped (an
    embedding count, a caption, a parsed diagram's shape). output_metadata
    stays separate, for genuinely auxiliary/diagnostic fields, matching
    the same input/metadata split traced() uses."""
    if span is not None:
        try:
            span.update(output=output, metadata=output_metadata)
        except Exception as exc:
            log_event(logger, "WARNING", "langfuse_child_span_update_failed", error=str(exc))
    if cm is not None:
        try:
            cm.__exit__(None, None, None)
        except Exception as exc:
            log_event(logger, "WARNING", "langfuse_child_span_exit_failed", error=str(exc))


def safe_create_score(*, trace_id: str, name: str, value: float | str, **kwargs: Any) -> None:
    """Built per the "every single call" requirement; not called anywhere
    yet in this stage — no eval harness exists to call it until the
    calibrate_thresholds.py/ragas_metrics.py follow-up (§25, out of scope
    for this stage). Kept here, already defensive, for that future caller."""
    client = _safe_client()
    if client is None:
        return
    try:
        client.create_score(trace_id=trace_id, name=name, value=value, **kwargs)
    except Exception as exc:
        log_event(
            logger, "WARNING", "langfuse_create_score_failed",
            trace_id=trace_id, name=name, error=str(exc),
        )


def safe_flush() -> None:
    """§15: "Flush | langfuse.flush() at request teardown." Called from
    routes_chat.py at the end of the /chat handler and from pipeline.py's
    run_ingestion() in a finally block."""
    client = _safe_client()
    if client is None:
        return
    try:
        client.flush()
    except Exception as exc:
        log_event(logger, "WARNING", "langfuse_flush_failed", error=str(exc))


def safe_query_trace_metrics(
    *, names: list[str], from_timestamp: datetime, to_timestamp: datetime
) -> list[dict] | None:
    """GET /metrics' (§17/§18) real aggregate-data source for latency/cost
    — client.api.trace.list(), NOT client.api.metrics.metrics(). Replaces
    an earlier implementation (safe_query_metrics(), removed) that queried
    the "observations" metrics view filtered to terminal node span NAMES
    (respond/escalate/out_of_scope_refusal) — real, confirmed problem
    with that approach, found by inspecting an actual trace directly, not
    assumed: those thin wrapper spans' OWN duration/cost (a few
    milliseconds; no LLM call happens inside respond_node/escalate_node/
    out_of_scope_refusal_node themselves) is not what "one full request"
    latency/cost means. The real per-request time and LLM cost live on
    the OTHER node spans (classify/account_validation/reflect) and their
    nested OpenAI-generation children — none of which share a `name` with
    the terminal spans, so the old filter structurally could never see
    them, regardless of the earlier "type" discriminator fix.

    client.api.trace.list() instead returns Langfuse's own pre-computed,
    real per-TRACE `latency` (seconds) and `total_cost` (USD) fields —
    confirmed directly against a real completed trace: trace.latency
    (16.949s) matched the real wall-clock sum of that request's 5 node
    spans (classify 3.932 + router 0.002 + account_validation 5.071 +
    reflect 7.874 + respond 0.005 ≈ 16.884, the small remainder being
    real inter-node orchestration overhead), and trace.total_cost
    (0.00183625) matched EXACTLY the sum of that same trace's 3 real
    OpenAI-generation costs (0.0003373 + 0.0002392 + 0.00125975). Every
    graph node for one real request correctly shares one trace_id
    (confirmed directly via client.api.trace.get() — all 8 of that
    request's observations, spans and generations alike, belonged to the
    one trace) — the earlier suspicion that each node was becoming its
    own separate trace was wrong; that impression came from `trace.list()`
    returning several genuinely-different real requests, not one
    fragmented one.

    A trace's own `name` field resolves to whichever node ran LAST for
    that trace, not the first (confirmed: a real, completed RAG-path
    trace was named "respond", even though classify ran first) — so
    filtering trace.list() by `name` to the 3 terminal node names still
    correctly selects "one full, completed real request" traces, the
    same intent the old filter had, just against the right API.

    Paginates through every page for each requested name (Langfuse caps
    each page at 100 results) rather than trusting a single page —
    confirmed necessary, not precautionary: a real call during this
    project's own build returned totalItems=239 for a single 24h window
    on just the "respond" name.

    Returns a list of {"latency": <seconds, float>, "total_cost": <usd,
    float>} — one entry per real trace found, across all pages, for the
    given names/time window. Percentiles/sums are computed by the caller
    (routes_metrics.py), since this API aggregates at the trace level,
    not via a server-side percentile/sum query. Returns None on any
    failure (client unavailable, network error) so GET /metrics can
    degrade to its local-DB-only fields (escalation rate, last eval run)
    instead of a 500 — tracing/metrics-querying is an optimization, never
    a hard dependency of the endpoint responding at all."""
    client = _safe_client()
    if client is None:
        return None
    try:
        results: list[dict] = []
        for name in names:
            page = 1
            while True:
                response = client.api.trace.list(
                    name=name, from_timestamp=from_timestamp, to_timestamp=to_timestamp, page=page, limit=100
                )
                results.extend(
                    {"latency": t.latency, "total_cost": t.total_cost}
                    for t in response.data
                    if t.latency is not None and t.total_cost is not None
                )
                if len(response.data) < 100:
                    break
                page += 1
        return results
    except Exception as exc:
        log_event(logger, "WARNING", "langfuse_query_trace_metrics_failed", error=str(exc))
        return None
