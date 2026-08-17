"""Responsible for response schema definitions used by the API layer.

Every endpoint returns the same envelope (APIResponse[T]) so API consumers
can branch on `success` once instead of special-casing each endpoint's
error shape."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel

from app.config import get_settings
from app.schemas.domain import CritiqueNote, EventBlueprint

T = TypeVar("T")


class HealthResponse(BaseModel):
    status: str
    llm_configured: bool
    # Providers with real credentials in the running environment, in
    # display order — the UI's model picker only offers these, so the
    # default here doubles as this deployment's "available providers" list.
    available_providers: list[str] = []
    # app.config.Settings.quality_gate_threshold — the UI's quality slider
    # initializes to this value rather than hardcoding a guess that could
    # drift out of sync with the server's actual default.
    default_quality_gate_threshold: float = 0.0


class PlanResponse(BaseModel):
    plan_id: str
    status: str
    iteration_count: int
    max_iterations: int | None = None
    # Exposed so the UI can show "0.64 (needs 0.80)" instead of a bare score
    # with no context for what "revising" actually means.
    quality_gate_threshold: float = 0.0
    # The LLM provider this plan is running on ("azure" | "anthropic" |
    # "gemini"), or None for the default fallback chain. Fixed at plan
    # creation (see app.orchestrator.graph_builder.run_new_plan) and carried
    # through every refine on the same plan.
    provider: str | None = None
    active_revision_targets: list[str] = []
    specialist_outputs_ready: list[str] = []
    blueprint: EventBlueprint | None = None
    critique_history: list[CritiqueNote] = []
    error_message: str | None = None

    @classmethod
    def from_state(cls, plan_id: str, state: dict) -> "PlanResponse":
        return cls(
            plan_id=plan_id,
            status=state.get("status", "in_progress"),
            iteration_count=state.get("iteration_count", 0),
            max_iterations=state.get("max_iterations"),
            quality_gate_threshold=state.get("quality_gate_threshold") or get_settings().quality_gate_threshold,
            provider=state.get("provider"),
            active_revision_targets=state.get("active_revision_targets", []),
            specialist_outputs_ready=list(state.get("specialist_outputs", {}).keys()),
            blueprint=state.get("draft_blueprint"),
            critique_history=state.get("critique_history", []),
        )

    @classmethod
    def from_store(cls, plan_id: str, stored: dict) -> "PlanResponse":
        critique_history = stored.get("critique_history", [])
        return cls(
            plan_id=plan_id,
            status=stored["status"],
            iteration_count=len(critique_history),
            quality_gate_threshold=stored.get("quality_gate_threshold") or get_settings().quality_gate_threshold,
            provider=stored.get("provider"),
            blueprint=stored.get("blueprint"),
            critique_history=critique_history,
            error_message=stored.get("error_message"),
        )


class PlanSummary(BaseModel):
    plan_id: str
    event_type: str
    objective: str
    status: str
    created_at: str
    updated_at: str
    iteration_count: int
    latest_score: float | None = None

    @classmethod
    def from_store(cls, stored: dict) -> "PlanSummary":
        critique_history = stored.get("critique_history", [])
        latest_score = None
        if critique_history:
            last = critique_history[-1]
            latest_score = last.score if hasattr(last, "score") else last["score"]

        return cls(
            plan_id=stored["plan_id"],
            event_type=stored.get("event_type", ""),
            objective=stored.get("objective", ""),
            status=stored["status"],
            created_at=stored["created_at"],
            updated_at=stored["updated_at"],
            iteration_count=len(critique_history),
            latest_score=latest_score,
        )


class ErrorDetail(BaseModel):
    code: str
    message: str


class APIResponse(BaseModel, Generic[T]):
    success: bool
    data: T | None = None
    error: ErrorDetail | None = None
    request_id: str

    @classmethod
    def ok(cls, data: T, request_id: str) -> "APIResponse[T]":
        return cls(success=True, data=data, error=None, request_id=request_id)

    @classmethod
    def fail(cls, code: str, message: str, request_id: str) -> "APIResponse[T]":
        return cls(success=False, data=None, error=ErrorDetail(code=code, message=message), request_id=request_id)
