"""Responsible for request schema definitions used by the API layer."""

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.domain import EventBrief


class CreatePlanRequest(EventBrief):
    """POST /plans body — identical shape to EventBrief plus API-only
    fields, kept as a distinct class so the API layer can evolve
    independently of the graph's schema."""

    # None = default Azure -> Anthropic -> Gemini fallback chain (see
    # app.llm.model_router.resolve_chain). The router validates the chosen
    # provider actually has credentials configured before starting the run
    # (see app.api.routers.plans.create_plan) — this Literal only bounds it
    # to a known provider name.
    provider: Literal["azure", "anthropic", "gemini"] | None = None

    # None = app.config.Settings.quality_gate_threshold (see GET /health's
    # default_quality_gate_threshold, which the UI's slider initializes
    # from). Bounded so a plan can't be configured to trivially "pass" (too
    # low) or be practically unreachable (too high).
    quality_gate_threshold: float | None = Field(default=None, ge=0.5, le=0.9)


class RefinePlanRequest(BaseModel):
    instruction: str
    target_agents: list[str] | None = None
