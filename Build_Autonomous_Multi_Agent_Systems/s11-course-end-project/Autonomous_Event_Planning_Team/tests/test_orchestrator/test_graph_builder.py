"""Responsible for tests covering orchestration graph construction."""

from app.orchestrator.graph_builder import build_graph


def test_build_graph_returns_compiled_graph():
    graph = build_graph()

    assert graph is not None
    assert hasattr(graph, "ainvoke")
