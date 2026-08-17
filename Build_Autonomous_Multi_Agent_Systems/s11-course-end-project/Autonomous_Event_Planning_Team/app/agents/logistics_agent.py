"""Responsible for the logistics specialist agent implementation."""

from app.agents.base import BaseAgent
from app.agents.prompts.specialist_prompts import LOGISTICS_PROMPT, build_feedback_context
from app.llm.structured_output import build_response_format, parse_structured_json
from app.schemas.domain import LogisticsPlan
from app.tools.venue_tool import find_venue

_RESPONSE_SCHEMA = build_response_format(
    "logistics_plan",
    {
        "type": "object",
        "properties": {
            "catering": {"type": "string"},
            "vendors": {"type": "array", "items": {"type": "string"}},
            "equipment": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["catering", "vendors", "equipment"],
        "additionalProperties": False,
    },
)


class LogisticsAgent(BaseAgent):
    name = "logistics"

    def _get_value(self, value, key):
        if isinstance(value, dict):
            return value[key]
        return getattr(value, key)

    def run(self, state) -> dict:
        brief = state["brief"]
        event_type = self._get_value(brief, "event_type")
        objective = self._get_value(brief, "objective")
        audience_size = self._get_value(brief, "audience_size")
        venue_preference = self._get_value(brief, "venue_preference")
        constraints = state.get("constraints") or self._get_value(brief, "constraints")

        venue_info = find_venue(audience_size, venue_preference)

        required_keys = {"catering", "vendors", "equipment"}
        fallback_response = {
            "catering": "Standard catering package sized for the expected audience.",
            "vendors": ["AV vendor", "Catering vendor"],
            "equipment": ["Projector", "Sound system"],
        }

        try:
            response = self._think(
                LOGISTICS_PROMPT.format(
                    event_type=event_type,
                    objective=objective,
                    audience_size=audience_size,
                    venue=venue_info["venue"],
                    capacity=venue_info["capacity"],
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

        logistics_plan = LogisticsPlan(
            venue=venue_info["venue"],
            capacity=venue_info["capacity"],
            layout_notes=venue_info["layout_notes"],
            catering=parsed_response["catering"],
            vendors=parsed_response["vendors"],
            equipment=parsed_response["equipment"],
        )

        return {"logistics": logistics_plan}
