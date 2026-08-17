"""
app/orchestration/graph.py

The LangGraph state machine (§2, §11). Deterministic supervisor pattern
(§2.1): this file + router.py's pure functions are the only orchestration
logic — agent nodes never call each other directly.

Stage 6 wires the real SQL/Hybrid/Critical branches (Stage 5 only ever
ran doc_retrieval alone, regardless of retrieval_mode — see git history /
the Stage 5 plan's Deviation B for that earlier provisional scope):

  "RAG"      -> doc_retrieval_node alone (unchanged from Stage 5)
  "SQL"      -> account_validation_node alone (Stage 6 Gap 1's resolution —
                §11's diagram never drew this branch, but §3's roster and
                §13's own latency table both require it)
  "Hybrid"   -> doc_retrieval_node ∥ account_validation_node, GENUINE
  "Critical"    concurrent execution via LangGraph's Send API — not two
                sequential calls that happen to both run

Wiring clarification vs. the plan's own ASCII diagram: the diagram shows
"classify_node -> [conditional] -> doc_retrieval_node" without depicting
router_node in between. router_node is a real node (writes retrieval_mode
to state per §4) and must actually run in the graph to do that — it sits
between classify_node and the out-of-scope conditional check below. This is
a literal-wiring refinement of the diagram, not a scope change.

§39.2's StructuredOutputError handling ("caught at the graph level, which
routes directly to escalate_node") is implemented via _guard_structured_output:
every LLM-calling node (classify, doc_retrieval, account_validation,
incident_severity, reflect) is wrapped so that a StructuredOutputError
never propagates out of graph execution — instead the wrapper returns
{"escalation_flag": True}, and every conditional edge downstream of a
wrapped node checks escalation_flag FIRST, before its own normal routing
logic, sending execution straight to escalate_node regardless of which
node's LLM call actually failed. escalation_flag is a reducer field
(state.py, Stage 6 Deviation J) precisely because doc_retrieval_node and
account_validation_node can both hit this path in the SAME superstep
during a Hybrid/Critical fan-out — a plain last-write-wins field would
raise LangGraph's InvalidUpdateError if both failed at once.

reflection_loopback_count is never read or written by any conditional edge
function in this file — LangGraph conditional edges can only select the
next node, they cannot return a state update (see doc_retrieval.py's own
docstring for the full mechanics). doc_retrieval_node owns that counter
entirely; the edge below only reads the value already sitting in state.

README §5's "explicit request for human support" escalation trigger is a
second short-circuit checked in _route_after_classify, alongside the
out_of_scope check: a literal "connect me with a human" request routes
straight to escalate_node, bypassing doc_retrieval/reflect entirely, the
same shape as the out_of_scope -> fixed-refusal short-circuit. Checked
before the out_of_scope check — if a query is somehow both (e.g.
off-topic AND an explicit human request), honoring the human request
takes priority, since routing to a person is always a safe superset of
refusing outright.

_route_after_retrieval (§11's SEVCHECK diamond, router._needs_incident_severity)
is registered against BOTH doc_retrieval_node and account_validation_node's
outgoing edges — when both halves of a Hybrid/Critical fan-out
independently evaluate it against the same already-converged category/
retrieval_mode, they agree on the same target, and LangGraph's fan-in
behavior should run that target exactly once. This is a claim about
library behavior, not just asserted with confidence — it is directly,
empirically verified by test_graph_parallel_fanout.py's exact-call-count
assertion on incident_severity_node's LLM client (Stage 6 plan's own
verification requirement, added after review).

recursion_limit=15 (§5) is not set here — it's a per-invocation config value
(routes_chat.py passes it to .ainvoke()), since LangGraph has no
compile-time recursion_limit parameter. Still comfortably covers the
longest legitimate path (classify -> router -> [doc_retrieval ∥
account_validation] -> incident_severity -> reflect -> loop-back ->
doc_retrieval -> reflect -> escalate/respond, ~9-10 steps).

Per this project's own Stage 5 plan (Deviation G): the module-level
`graph` singleton below still compiles with no checkpointer (backward
compatible with every test that imports it directly). Stage 8 adds real
Postgres-backed persistence (§40) via build_graph(checkpointer=...),
constructed at FastAPI startup — see app/orchestration/checkpointer.py
and app/main.py's lifespan.
"""

from __future__ import annotations

import logging
from typing import Awaitable, Callable

import openai
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from app.llm.structured_output import StructuredOutputError, is_content_filter_error
from app.logging.structured_logger import log_event
from app.observability import tracing
from app.orchestration.nodes.account_validation import account_validation_node
from app.orchestration.nodes.classify import classify_node
from app.orchestration.nodes.doc_retrieval import doc_retrieval_node
from app.orchestration.nodes.escalate import escalate_node
from app.orchestration.nodes.incident_severity import incident_severity_node
from app.orchestration.nodes.reflect import reflect_node
from app.orchestration.nodes.respond import respond_node
from app.orchestration.nodes.router import (
    _needs_incident_severity,
    decide_action,
    resolve_effective_severity,
    router_node,
    should_escalate_for_explicit_request,
)
from app.schemas.state import SupportGraphState

logger = logging.getLogger(__name__)

GRAPH_RECURSION_LIMIT = 15  # §5 — passed via config at invocation time, not a compile-time param

NodeFn = Callable[[SupportGraphState], Awaitable[dict]]


def _guard_structured_output(node_fn: NodeFn) -> NodeFn:
    """§39.2: wraps an LLM-calling node so a StructuredOutputError (raised
    after call_llm_structured's own one bounded retry already failed) never
    propagates out of graph execution. Instead of re-raising, returns a
    state update that every downstream conditional edge checks first —
    routing straight to escalate_node regardless of which node failed.

    Also catches Azure content-filter refusals (openai.BadRequestError,
    filtered via is_content_filter_error() — see that function's own
    docstring for the real, confirmed gap this closes) the exact same
    way: escalating to a human is the correct response to a query Azure
    itself flagged as adversarial, not an unhandled crash. A
    BadRequestError NOT caused by content filtering still propagates —
    this only ever absorbs the specific, identified case."""

    async def wrapped(state: SupportGraphState) -> dict:
        try:
            return await node_fn(state)
        except StructuredOutputError as exc:
            log_event(
                logger,
                "ERROR",
                "structured_output_error_escalated",
                node=node_fn.__name__,
                error=str(exc),
            )
            return {"escalation_flag": True}
        except openai.BadRequestError as exc:
            if not is_content_filter_error(exc):
                raise
            log_event(
                logger,
                "ERROR",
                "content_filter_error_escalated",
                node=node_fn.__name__,
                error=str(exc),
            )
            return {"escalation_flag": True}

    wrapped.__name__ = node_fn.__name__
    return wrapped


async def out_of_scope_refusal_node(state: SupportGraphState) -> dict:
    """§31 Layer A's terminal action — classify_node's own out_of_scope
    category short-circuits straight here, no retrieval agent ever runs.
    Fixed, deterministic response; no LLM call."""
    return {
        "final_answer": (
            "I'm only able to help with questions about this product's usage, integration, "
            "billing, incidents, and security. This request appears to be outside that scope, "
            "so I'm not able to assist with it here."
        ),
        "sources": [],
    }


def _route_after_classify(state: SupportGraphState) -> str:
    if state.get("escalation_flag"):
        return "escalate_node"
    if should_escalate_for_explicit_request(state.get("explicit_human_request", False)):
        return "escalate_node"
    if state.get("category") == "out_of_scope":
        return "out_of_scope_refusal_node"
    return "router_node"


def _route_after_router(state: SupportGraphState):
    """Gap 1's resolution: a real third (SQL-alone) branch, plus genuine
    concurrent Send fan-out for Hybrid/Critical — see module docstring."""
    mode = state.get("retrieval_mode")
    if mode == "RAG":
        return "doc_retrieval_node"
    if mode == "SQL":
        return "account_validation_node"
    # "Hybrid" or "Critical" — router_node never produces anything else for
    # a non-out-of-scope query (out_of_scope is already short-circuited
    # before router_node ever runs), so this is exhaustive.
    return [Send("doc_retrieval_node", state), Send("account_validation_node", state)]


def _route_after_retrieval(state: SupportGraphState) -> str:
    """Shared conditional-edge target for BOTH doc_retrieval_node and
    account_validation_node's outgoing edges — §11's SEVCHECK diamond."""
    if state.get("escalation_flag"):
        return "escalate_node"
    if _needs_incident_severity(state.get("category"), state.get("retrieval_mode")):
        return "incident_severity_node"
    return "reflect_node"


def _route_after_incident_severity(state: SupportGraphState) -> str:
    if state.get("escalation_flag"):
        return "escalate_node"
    return "reflect_node"


def _route_after_reflect(state: SupportGraphState) -> str:
    if state.get("escalation_flag"):
        return "escalate_node"

    if not state.get("groundedness_flag", False) and state.get("reflection_loopback_count", 0) < 1:
        return "doc_retrieval_node"

    severity = resolve_effective_severity(state.get("severity_final"), state.get("severity_initial"))
    action, _ = decide_action(severity, state.get("confidence_tier"))
    return "escalate_node" if action == "escalate" else "respond_node"


def build_graph(checkpointer=None):
    """Builds and compiles the support graph. A fresh StateGraph is
    constructed each call rather than mutating a shared builder — cheap,
    and avoids any risk of node/edge registration leaking across callers
    (e.g. repeated test-suite imports).

    checkpointer=None (StateGraph.compile()'s own default) keeps this
    module's `graph = build_graph()` singleton below exactly as it's
    always behaved — the ~118 tests that `from app.orchestration.graph
    import graph` are unaffected. The real Postgres-backed checkpointer
    (§40) is constructed asynchronously at FastAPI startup
    (app/main.py's lifespan) and passed in here to build the app's real
    request-serving graph, stored on app.state.graph."""
    builder = StateGraph(SupportGraphState)

    # Every node gets a Langfuse span (§15 + the "trace everything" coverage
    # principle — see app/observability/tracing.py's module docstring).
    # traced() wraps OUTSIDE _guard_structured_output for the 5 nodes that
    # have it: _guard_structured_output must see the real
    # StructuredOutputError first (turning it into a normal returned dict),
    # so traced()'s own await node_fn(state) never has to distinguish a
    # caught business error from a genuinely unexpected one — anything it
    # sees propagates untouched.
    builder.add_node("classify_node", tracing.traced(_guard_structured_output(classify_node), "classify"))
    builder.add_node("router_node", tracing.traced(router_node, "router"))
    builder.add_node(
        "doc_retrieval_node", tracing.traced(_guard_structured_output(doc_retrieval_node), "doc_retrieval")
    )
    builder.add_node(
        "account_validation_node",
        tracing.traced(_guard_structured_output(account_validation_node), "account_validation"),
    )
    builder.add_node(
        "incident_severity_node",
        tracing.traced(_guard_structured_output(incident_severity_node), "incident_severity"),
    )
    builder.add_node("reflect_node", tracing.traced(_guard_structured_output(reflect_node), "reflect"))
    builder.add_node("respond_node", tracing.traced(respond_node, "respond"))
    builder.add_node("escalate_node", tracing.traced(escalate_node, "escalate"))
    builder.add_node(
        "out_of_scope_refusal_node", tracing.traced(out_of_scope_refusal_node, "out_of_scope_refusal")
    )

    builder.add_edge(START, "classify_node")

    builder.add_conditional_edges(
        "classify_node",
        _route_after_classify,
        {
            "escalate_node": "escalate_node",
            "out_of_scope_refusal_node": "out_of_scope_refusal_node",
            "router_node": "router_node",
        },
    )

    # No path_map: _route_after_router returns either a plain node-name
    # string (RAG/SQL) or a list of Send objects (Hybrid/Critical) — Send
    # carries its own target, so a path_map isn't applicable to that case.
    builder.add_conditional_edges("router_node", _route_after_router)

    builder.add_conditional_edges(
        "doc_retrieval_node",
        _route_after_retrieval,
        {
            "escalate_node": "escalate_node",
            "incident_severity_node": "incident_severity_node",
            "reflect_node": "reflect_node",
        },
    )
    builder.add_conditional_edges(
        "account_validation_node",
        _route_after_retrieval,
        {
            "escalate_node": "escalate_node",
            "incident_severity_node": "incident_severity_node",
            "reflect_node": "reflect_node",
        },
    )
    builder.add_conditional_edges(
        "incident_severity_node",
        _route_after_incident_severity,
        {
            "escalate_node": "escalate_node",
            "reflect_node": "reflect_node",
        },
    )
    builder.add_conditional_edges(
        "reflect_node",
        _route_after_reflect,
        {
            "escalate_node": "escalate_node",
            "respond_node": "respond_node",
            "doc_retrieval_node": "doc_retrieval_node",
        },
    )

    builder.add_edge("respond_node", END)
    builder.add_edge("escalate_node", END)
    builder.add_edge("out_of_scope_refusal_node", END)

    return builder.compile(checkpointer=checkpointer)


graph = build_graph()
