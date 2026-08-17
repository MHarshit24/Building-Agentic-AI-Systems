"""
tests/unit/test_graph_tracing_composition.py

L1 structural test (§19): confirms build_graph() actually wraps every
one of the 9 real nodes with tracing.traced(...), without running the
graph or making any real Langfuse/LLM calls — the same "verify the code
is structured correctly" discipline as Stage 6/7's fan-in-convergence
and BackgroundTasks structural tests, applied here because a
timing/network-based check ("did a span really get created") would be
flaky and slow, while whether the WIRING is correct is a pure, fast,
static property of build_graph() itself.

Detection mechanism: tracing.traced(node_fn, span_name) returns a
closure over both node_fn and span_name — CPython closures capture free
variables by name, so a callable's __code__.co_freevars containing
"span_name" is a reliable, specific fingerprint that it was produced by
traced() specifically (not by _guard_structured_output, whose own
wrapper closes over node_fn alone, or by no wrapping at all).
"""

from __future__ import annotations

from langgraph.graph import StateGraph

import app.orchestration.graph as graph_module

# The 9 real nodes registered by build_graph() and traced per §15 + the
# "trace everything" coverage principle (see tracing.py's module
# docstring) — every node build_graph() registers, including
# out_of_scope_refusal_node, which isn't one of §15's literal 9 names
# but is deliberately traced too (see the plan's decision note).
EXPECTED_TRACED_NODES = {
    "classify_node": "classify",
    "router_node": "router",
    "doc_retrieval_node": "doc_retrieval",
    "account_validation_node": "account_validation",
    "incident_severity_node": "incident_severity",
    "reflect_node": "reflect",
    "respond_node": "respond",
    "escalate_node": "escalate",
    "out_of_scope_refusal_node": "out_of_scope_refusal",
}


def _is_traced_wrapper(fn) -> bool:
    return "span_name" in getattr(fn.__code__, "co_freevars", ())


def _captured_node_registrations() -> dict[str, object]:
    """Monkeypatch-free capture: StateGraph.add_node's real implementation
    still runs (so build_graph() behaves identically to production), but
    every (name, callable) pair passed to it is also recorded via a thin
    subclass, avoiding any reliance on LangGraph's internal Runnable
    wrapping to get the original callable back out."""
    captured: dict[str, object] = {}
    original_add_node = StateGraph.add_node

    def recording_add_node(self, name, action=None, **kwargs):
        if action is not None:
            captured[name if isinstance(name, str) else getattr(name, "__name__", str(name))] = action
        return original_add_node(self, name, action, **kwargs)

    real_cls_add_node = StateGraph.add_node
    StateGraph.add_node = recording_add_node
    try:
        graph_module.build_graph()
    finally:
        StateGraph.add_node = real_cls_add_node
    return captured


def test_every_expected_node_is_registered():
    registrations = _captured_node_registrations()
    assert set(registrations.keys()) == set(EXPECTED_TRACED_NODES.keys())


def test_every_registered_node_is_wrapped_by_traced():
    registrations = _captured_node_registrations()
    for node_name in EXPECTED_TRACED_NODES:
        fn = registrations[node_name]
        assert _is_traced_wrapper(fn), f"{node_name} is not wrapped by tracing.traced()"


def test_traced_wrapper_name_matches_original_node_function():
    """traced()'s wrapper sets wrapper.__name__ = node_fn.__name__ —
    confirms it's wrapping the RIGHT node, not just some traced callable."""
    registrations = _captured_node_registrations()
    for node_name, fn in registrations.items():
        assert fn.__name__ == node_name


def test_guarded_nodes_are_wrapped_by_guard_before_traced():
    """The 5 nodes with _guard_structured_output must have traced()
    OUTSIDE it (composition order matters — see graph.py's own comment):
    traced()'s closure captures node_fn, which for these 5 is itself
    _guard_structured_output's own "wrapped" closure (freevar "node_fn"
    only, no "span_name") — confirming the guard runs first, inside."""
    guarded_node_names = {
        "classify_node",
        "doc_retrieval_node",
        "account_validation_node",
        "incident_severity_node",
        "reflect_node",
    }
    registrations = _captured_node_registrations()
    for node_name in guarded_node_names:
        traced_wrapper = registrations[node_name]
        inner = traced_wrapper.__closure__[
            traced_wrapper.__code__.co_freevars.index("node_fn")
        ].cell_contents
        assert "span_name" not in inner.__code__.co_freevars  # not itself another traced() layer
        assert "node_fn" in inner.__code__.co_freevars  # it's _guard_structured_output's own wrapper


def test_untraced_helper_functions_are_not_accidentally_wrapped():
    """graph.py's own _guard_structured_output and _route_after_* helpers
    are not graph nodes and must never be picked up as if they were."""
    registrations = _captured_node_registrations()
    assert "_guard_structured_output" not in registrations
    assert "_route_after_classify" not in registrations
