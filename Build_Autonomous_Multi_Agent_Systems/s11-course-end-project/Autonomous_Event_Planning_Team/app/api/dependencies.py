"""Responsible for shared API dependency providers and helpers."""

from fastapi import Request

from app.orchestrator.graph_builder import PlanningOrchestrator


def get_orchestrator(request: Request) -> PlanningOrchestrator:
    """The orchestrator is built once in app.main's lifespan (it owns the
    long-lived checkpointer connection) and stashed on app.state."""
    return request.app.state.orchestrator
