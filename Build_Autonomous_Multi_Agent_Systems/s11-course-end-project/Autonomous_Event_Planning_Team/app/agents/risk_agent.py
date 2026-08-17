"""Responsible for the risk specialist agent implementation."""

from app.agents.base import BaseAgent
from app.agents.prompts.specialist_prompts import RISK_PROMPT, build_feedback_context
from app.llm.structured_output import build_response_format, parse_structured_json
from app.schemas.domain import RiskRegister

_REQUIRED_RISK_KEYS = {"name", "likelihood", "impact", "mitigation"}

_RESPONSE_SCHEMA = build_response_format(
    "risk_register",
    {
        "type": "object",
        "properties": {
            "risks": {
                "type": "array",
                "minItems": 3,
                "maxItems": 5,
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "likelihood": {"type": "string", "enum": ["low", "medium", "high"]},
                        "impact": {"type": "string", "enum": ["low", "medium", "high"]},
                        "mitigation": {"type": "string"},
                    },
                    "required": ["name", "likelihood", "impact", "mitigation"],
                    "additionalProperties": False,
                },
            },
            "contingency_notes": {"type": "string"},
        },
        "required": ["risks", "contingency_notes"],
        "additionalProperties": False,
    },
)


class RiskAgent(BaseAgent):
    name = "risk"

    def _get_value(self, value, key):
        if isinstance(value, dict):
            return value[key]
        return getattr(value, key)

    def run(self, state) -> dict:
        brief = state["brief"]
        event_type = self._get_value(brief, "event_type")
        objective = self._get_value(brief, "objective")
        audience_size = self._get_value(brief, "audience_size")
        budget = self._get_value(brief, "budget")
        budget_max_amount = self._get_value(budget, "max_amount")
        budget_currency = self._get_value(budget, "currency")
        constraints = state.get("constraints") or self._get_value(brief, "constraints")

        fallback_response = {
            "risks": [
                {
                    "name": "Vendor cancellation",
                    "likelihood": "low",
                    "impact": "high",
                    "mitigation": "Confirm backup vendors ahead of the event date.",
                },
                {
                    "name": "Lower than expected turnout",
                    "likelihood": "medium",
                    "impact": "medium",
                    "mitigation": "Track registrations against outreach and boost marketing if needed.",
                },
                {
                    "name": "Budget overrun",
                    "likelihood": "medium",
                    "impact": "high",
                    "mitigation": "Track spend against the budget plan weekly and hold a contingency reserve.",
                },
            ],
            "contingency_notes": "Fallback contingency plan — LLM risk assessment was unavailable.",
        }

        parsed_response = None
        try:
            response = self._think(
                RISK_PROMPT.format(
                    event_type=event_type,
                    objective=objective,
                    audience_size=audience_size,
                    budget_max_amount=budget_max_amount,
                    budget_currency=budget_currency,
                    constraints=constraints,
                    feedback=build_feedback_context(state),
                ),
                response_format=_RESPONSE_SCHEMA,
                plan_id=state["plan_id"],
                provider=state.get("provider"),
            )
            candidate = parse_structured_json(response)
            risks = candidate.get("risks") if isinstance(candidate, dict) else None
            valid_risks = (
                isinstance(risks, list)
                and len(risks) > 0
                and all(isinstance(r, dict) and _REQUIRED_RISK_KEYS.issubset(r.keys()) for r in risks)
            )
            if valid_risks and "contingency_notes" in candidate:
                parsed_response = candidate
        except Exception:
            parsed_response = None

        if parsed_response is None:
            parsed_response = fallback_response

        risk_register = RiskRegister(
            risks=parsed_response["risks"],
            contingency_notes=parsed_response["contingency_notes"],
        )

        return {"risk": risk_register}
