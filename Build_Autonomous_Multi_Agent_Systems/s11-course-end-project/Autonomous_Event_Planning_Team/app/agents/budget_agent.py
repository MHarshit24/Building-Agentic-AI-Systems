"""Responsible for the budget specialist agent implementation."""

from app.agents.base import BaseAgent
from app.agents.prompts.specialist_prompts import BUDGET_PROMPT, build_feedback_context
from app.llm.structured_output import build_response_format, parse_structured_json
from app.schemas.domain import BudgetPlan
from app.tools.pricing_tool import estimate_costs

# 1.0 = tool baseline unchanged. The LLM can move this up (contingency, for
# extra risk) or down (real cost cuts — smaller venue, simpler catering) in
# response to prior critique feedback; a one-way contingency-only factor
# could never bring an over-budget plan back under the cap.
MIN_COST_ADJUSTMENT_FACTOR = 0.5
MAX_COST_ADJUSTMENT_FACTOR = 1.5
DEFAULT_COST_ADJUSTMENT_FACTOR = 1.1

_RESPONSE_SCHEMA = build_response_format(
    "budget_adjustment",
    {
        "type": "object",
        "properties": {
            "cost_adjustment_factor": {
                "type": "number",
                "minimum": MIN_COST_ADJUSTMENT_FACTOR,
                "maximum": MAX_COST_ADJUSTMENT_FACTOR,
            },
        },
        "required": ["cost_adjustment_factor"],
        "additionalProperties": False,
    },
)


class BudgetAgent(BaseAgent):
    name = "budget"

    def _get_value(self, value, key):
        if isinstance(value, dict):
            return value[key]
        return getattr(value, key)

    def _is_budget_revision(self, state) -> bool:
        critique_history = state.get("critique_history") or []
        if not critique_history:
            return False
        latest = critique_history[-1]
        revision_targets = self._get_value(latest, "revision_targets")
        return "budget" in revision_targets

    def run(self, state) -> dict:
        brief = state["brief"]
        event_type = self._get_value(brief, "event_type")
        audience_size = self._get_value(brief, "audience_size")
        budget = self._get_value(brief, "budget")
        budget_max_amount = self._get_value(budget, "max_amount")
        budget_currency = self._get_value(budget, "currency")
        constraints = state.get("constraints") or self._get_value(brief, "constraints")

        baseline = estimate_costs(audience_size, event_type, budget_currency)
        baseline_total = baseline["total_estimated_cost"]

        factor = None
        try:
            response = self._think(
                BUDGET_PROMPT.format(
                    event_type=event_type,
                    audience_size=audience_size,
                    baseline_total=baseline_total,
                    budget_currency=budget_currency,
                    budget_max_amount=budget_max_amount,
                    constraints=constraints,
                    feedback=build_feedback_context(state),
                ),
                response_format=_RESPONSE_SCHEMA,
                plan_id=state["plan_id"],
                provider=state.get("provider"),
            )
            candidate = parse_structured_json(response, required_keys={"cost_adjustment_factor"})
            if candidate is not None:
                value = float(candidate["cost_adjustment_factor"])
                if MIN_COST_ADJUSTMENT_FACTOR <= value <= MAX_COST_ADJUSTMENT_FACTOR:
                    factor = value
        except Exception:
            factor = None

        if factor is None:
            factor = DEFAULT_COST_ADJUSTMENT_FACTOR

        total_estimated_cost = round(baseline_total * factor, 2)

        # The LLM is asked to cut costs on a budget revision pass, but
        # nothing guarantees it actually does — observed in practice to
        # sometimes pick the same factor regardless of feedback. When this
        # is specifically a budget revision and it's still over budget,
        # force compliance deterministically rather than let the loop burn
        # every remaining iteration on an unresponsive model. Deliberately
        # NOT clamped to MIN_COST_ADJUSTMENT_FACTOR here — that floor exists
        # to bound the LLM's own qualitative judgment, but a baseline that
        # is many times the budget (e.g. a large-audience event with a tight
        # cap) needs a steeper cut than 0.5 to actually land within budget,
        # and this branch's whole point is guaranteeing within_budget.
        if self._is_budget_revision(state) and total_estimated_cost > budget_max_amount and baseline_total > 0:
            factor = budget_max_amount / baseline_total
            # min() guards against the rounding below nudging the total a
            # cent above budget_max_amount and re-failing within_budget.
            total_estimated_cost = min(round(baseline_total * factor, 2), budget_max_amount)

        category_breakdown = {
            category: round(amount * factor, 2)
            for category, amount in baseline["category_breakdown"].items()
        }

        budget_plan = BudgetPlan(
            total_estimated_cost=total_estimated_cost,
            currency=budget_currency,
            category_breakdown=category_breakdown,
            within_budget=total_estimated_cost <= budget_max_amount,
        )

        return {"budget": budget_plan}
