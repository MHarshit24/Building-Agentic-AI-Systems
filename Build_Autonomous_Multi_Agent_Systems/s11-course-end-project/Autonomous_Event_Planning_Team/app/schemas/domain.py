import operator
from datetime import date
from typing import Annotated, Literal, TypedDict

from pydantic import BaseModel


# ---- What comes in from the user (Section 8.2 / 7.1) ----------------------
class BudgetConstraint(BaseModel):
    currency: str
    max_amount: float


class TimelinePreference(BaseModel):
    preferred_date: date
    duration_days: int


class EventBrief(BaseModel):
    event_type: str
    objective: str
    audience_size: int
    budget: BudgetConstraint
    timeline: TimelinePreference
    venue_preference: str | None = None
    constraints: list[str] = []


# ---- What each specialist agent produces (Section 5 "Key Outputs") --------
class LogisticsPlan(BaseModel):
    venue: str
    capacity: int
    layout_notes: str
    catering: str
    vendors: list[str] = []
    equipment: list[str] = []


class BudgetPlan(BaseModel):
    total_estimated_cost: float
    currency: str
    category_breakdown: dict[str, float]
    within_budget: bool


class MarketingPlan(BaseModel):
    channels: list[str]
    content_calendar: list[str]
    outreach_start_date: date


class ScheduleTimeline(BaseModel):
    milestones: list[dict[str, str]]     # [{"name": ..., "date": ...}, ...]
    conflicts_detected: list[str] = []


class RiskRegister(BaseModel):
    risks: list[dict[str, str]]          # [{"name":..,"likelihood":..,"impact":..,"mitigation":..}]
    contingency_notes: str = ""


SpecialistOutput = LogisticsPlan | BudgetPlan | MarketingPlan | ScheduleTimeline | RiskRegister


def merge_specialist_outputs(current: dict, update: dict) -> dict:
    """Reducer for EventPlanState.specialist_outputs. Up to five specialist
    nodes can write to this key within the same LangGraph superstep (the
    parallel fan-out in Section 6). Without this, LangGraph raises
    InvalidUpdateError: 'Can receive only one value per step.'"""
    merged = dict(current) if current else {}
    merged.update(update)
    return merged


# ---- What the manager merges everything into (Section 10.2) ---------------
class EventOverview(BaseModel):
    event_type: str
    objective: str
    audience_size: int
    date: date
    summary: str = ""   # short natural-language overview, produced by the
                         # manager agent's synthesis LLM call (Section 6.1 step 4)


class EventBlueprint(BaseModel):
    overview: EventOverview
    logistics: LogisticsPlan
    budget: BudgetPlan
    marketing: MarketingPlan
    schedule: ScheduleTimeline
    risks: RiskRegister


# ---- What the reflection agent produces (Section 8.3 / 9.1) ---------------
class CritiqueNote(BaseModel):
    iteration: int
    score: float                      # 0.0-1.0, weighted rubric
    passed: bool
    revision_targets: list[str]       # e.g. ["budget", "schedule"]
    notes: dict[str, str]             # per-dimension rationale
    # The three fields below are computed once in ReflectionAgent.critique()
    # and also reported to Langfuse (see app.observability.langfuse_tracer)
    # via the same values, so the score/timing/delta shown in the UI is
    # never a second, independently-computed number that could drift from
    # what Langfuse records for the same plan.
    duration_ms: float | None = None       # wall-clock time of the critique LLM call
    score_delta: float | None = None       # this score minus the previous iteration's score
    threshold_delta: float | None = None   # this score minus the quality gate threshold


# ---- The one object every graph node reads and writes (Section 8.1) -------
class EventPlanState(TypedDict):
    plan_id: str
    brief: EventBrief
    # User-selected LLM provider ("azure" | "anthropic" | "gemini"), or None
    # for the default Azure -> Anthropic -> Gemini fallback chain (see
    # app.llm.model_router.resolve_chain). A run-level orchestration
    # setting, not part of the event brief domain object.
    provider: str | None
    # User-selected minimum weighted critique score required to pass (see
    # ReflectionAgent.critique), or None for app.config.Settings.quality_gate_threshold.
    # Fixed at plan creation and carried through every refine, same as provider.
    quality_gate_threshold: float | None
    constraints: list[str]
    specialist_outputs: Annotated[dict[str, SpecialistOutput], merge_specialist_outputs]
    draft_blueprint: EventBlueprint | None
    # operator.add so each reflect_node visit appends its CritiqueNote
    # instead of racing/overwriting — same append-only pattern as
    # specialist_outputs' merge_specialist_outputs reducer above.
    critique_history: Annotated[list[CritiqueNote], operator.add]
    iteration_count: int
    max_iterations: int               # default 3
    active_revision_targets: list[str]
    status: Literal["in_progress", "needs_review", "completed", "failed"]