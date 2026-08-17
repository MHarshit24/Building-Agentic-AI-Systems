"""Responsible for tests covering orchestration edge behavior."""

from app.orchestrator.edges import quality_gate_edge


def test_quality_gate_finalizes_when_last_critique_passed():
    state = {
        "critique_history": [{"passed": True}],
        "iteration_count": 0,
        "max_iterations": 3,
    }

    assert quality_gate_edge(state) == "finalize"


def test_quality_gate_decomposes_when_last_critique_failed_before_limit():
    state = {
        "critique_history": [{"passed": False}],
        "iteration_count": 1,
        "max_iterations": 3,
    }

    assert quality_gate_edge(state) == "decompose"


def test_quality_gate_finalizes_when_last_critique_failed_at_limit():
    state = {
        "critique_history": [{"passed": False}],
        "iteration_count": 3,
        "max_iterations": 3,
    }

    assert quality_gate_edge(state) == "finalize"
