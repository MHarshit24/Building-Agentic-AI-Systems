"""Conditional routing function for the quality gate described in the architecture document, Section 6.1 step 6."""

from typing import Literal


def quality_gate_edge(state) -> Literal["decompose", "finalize"]:
    if not state["critique_history"]:
        return "decompose"

    last_entry = state["critique_history"][-1]
    if hasattr(last_entry, "passed"):
        passed = last_entry.passed
    else:
        passed = last_entry["passed"]

    if passed:
        return "finalize"

    if state["iteration_count"] >= state["max_iterations"]:
        return "finalize"

    return "decompose"
