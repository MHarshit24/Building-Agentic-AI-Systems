"""Responsible for the manager agent implementation."""

from app.agents.base import BaseAgent
from app.agents.prompts.manager_prompts import SYNTHESIS_PROMPT
from app.schemas.domain import (
    BudgetPlan,
    EventBlueprint,
    EventBrief,
    EventOverview,
    LogisticsPlan,
    MarketingPlan,
    RiskRegister,
    ScheduleTimeline,
)


class ManagerAgent(BaseAgent):
    name = "manager"

    def _get_value(self, value, key):
        if isinstance(value, dict):
            return value[key]
        return getattr(value, key)

    def decompose(self, state) -> dict:
        # Use specialist_outputs being empty as the "brand new plan" signal
        # instead of iteration_count == 0. refine_plan() also resets
        # iteration_count to 0 to give each refinement its own iteration
        # budget, so iteration_count alone can't distinguish "new plan" from
        # "refinement of an existing plan" — specialist_outputs can, since a
        # refinement always carries forward prior specialist results.
        if not state.get("specialist_outputs"):
            return {
                "iteration_count": 1,
                "active_revision_targets": ["logistics", "budget", "marketing", "schedule", "risk"],
            }
        return {
            "iteration_count": state["iteration_count"] + 1,
            "active_revision_targets": state["active_revision_targets"],
        }

    def _coerce_model(self, model_or_mapping, cls):
        if isinstance(model_or_mapping, cls):
            return model_or_mapping
        if isinstance(model_or_mapping, dict):
            return cls(**model_or_mapping)
        return cls(**model_or_mapping.dict())

    def synthesize(self, state) -> dict:
        brief = state["brief"]
        specialist_outputs = state["specialist_outputs"]

        event_type = self._get_value(brief, "event_type")
        objective = self._get_value(brief, "objective")
        audience_size = self._get_value(brief, "audience_size")
        constraints = state.get("constraints") or self._get_value(brief, "constraints")

        try:
            overview_summary = self._think(
                SYNTHESIS_PROMPT.format(
                    event_type=event_type,
                    objective=objective,
                    audience_size=audience_size,
                    constraints=constraints,
                    logistics_plan=specialist_outputs["logistics"],
                    budget_plan=specialist_outputs["budget"],
                    marketing_plan=specialist_outputs["marketing"],
                    schedule_timeline=specialist_outputs["schedule"],
                    risk_register=specialist_outputs["risk"],
                ),
                plan_id=state["plan_id"],
                provider=state.get("provider"),
            )
        except Exception:
            overview_summary = "Event plan synthesized from specialist outputs."

        overview = EventOverview(
            event_type=event_type,
            objective=objective,
            audience_size=audience_size,
            date=self._get_value(self._get_value(brief, "timeline"), "preferred_date"),
            summary=overview_summary,
        )

        blueprint = EventBlueprint(
            overview=overview,
            logistics=self._coerce_model(specialist_outputs["logistics"], LogisticsPlan),
            budget=self._coerce_model(specialist_outputs["budget"], BudgetPlan),
            marketing=self._coerce_model(specialist_outputs["marketing"], MarketingPlan),
            schedule=self._coerce_model(specialist_outputs["schedule"], ScheduleTimeline),
            risks=self._coerce_model(specialist_outputs["risk"], RiskRegister),
        )

        return {"draft_blueprint": blueprint}

    def run(self, state) -> dict:
        # decompose() is invoked directly by the orchestrator node rather than through run() since it is not an LLM-driven step.
        return self.synthesize(state)