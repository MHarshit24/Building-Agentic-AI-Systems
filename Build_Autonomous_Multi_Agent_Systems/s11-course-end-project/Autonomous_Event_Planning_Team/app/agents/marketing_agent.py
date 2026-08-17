"""Responsible for the marketing specialist agent implementation."""

from app.agents.base import BaseAgent
from app.agents.prompts.specialist_prompts import MARKETING_PROMPT, build_feedback_context
from app.llm.structured_output import build_response_format, parse_structured_json
from app.schemas.domain import MarketingPlan
from app.tools.calendar_tool import outreach_start_date as compute_outreach_start_date

_RESPONSE_SCHEMA = build_response_format(
    "marketing_plan",
    {
        "type": "object",
        "properties": {
            "channels": {"type": "array", "items": {"type": "string"}},
            "content_calendar": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["channels", "content_calendar"],
        "additionalProperties": False,
    },
)


class MarketingAgent(BaseAgent):
    name = "marketing"

    def _get_value(self, value, key):
        if isinstance(value, dict):
            return value[key]
        return getattr(value, key)

    def run(self, state) -> dict:
        brief = state["brief"]
        event_type = self._get_value(brief, "event_type")
        objective = self._get_value(brief, "objective")
        audience_size = self._get_value(brief, "audience_size")
        timeline = self._get_value(brief, "timeline")
        preferred_date = self._get_value(timeline, "preferred_date")
        constraints = state.get("constraints") or self._get_value(brief, "constraints")

        outreach_start = compute_outreach_start_date(preferred_date)

        required_keys = {"channels", "content_calendar"}
        fallback_response = {
            "channels": ["email", "social media"],
            "content_calendar": ["Save-the-date announcement", "Registration reminder", "Final agenda"],
        }

        try:
            response = self._think(
                MARKETING_PROMPT.format(
                    event_type=event_type,
                    objective=objective,
                    audience_size=audience_size,
                    outreach_start_date=outreach_start.isoformat(),
                    preferred_date=preferred_date.isoformat(),
                    constraints=constraints,
                    feedback=build_feedback_context(state),
                ),
                response_format=_RESPONSE_SCHEMA,
                plan_id=state["plan_id"],
                provider=state.get("provider"),
            )
            parsed_response = parse_structured_json(response, required_keys=required_keys)
        except Exception:
            parsed_response = None

        if parsed_response is None:
            parsed_response = fallback_response

        marketing_plan = MarketingPlan(
            channels=parsed_response["channels"],
            content_calendar=parsed_response["content_calendar"],
            outreach_start_date=outreach_start,
        )

        return {"marketing": marketing_plan}
