"""Responsible for the schedule specialist agent implementation."""

from datetime import timedelta

from app.agents.base import BaseAgent
from app.agents.prompts.specialist_prompts import SCHEDULE_PROMPT, build_feedback_context
from app.llm.structured_output import build_response_format, parse_structured_json
from app.schemas.domain import ScheduleTimeline
from app.tools.calendar_tool import build_milestones, check_conflicts

# Additional LLM-suggested milestones are placed at decreasing offsets ahead
# of this many days before the event, so they never collide with each other
# or with the baseline timeline's fixed offsets.
_ADDITIONAL_MILESTONE_START_OFFSET = -14

_RESPONSE_SCHEMA = build_response_format(
    "schedule_additions",
    {
        "type": "object",
        "properties": {
            "additional_milestones": {
                "type": "array",
                "maxItems": 3,
                "items": {"type": "string"},
            },
        },
        "required": ["additional_milestones"],
        "additionalProperties": False,
    },
)


class ScheduleAgent(BaseAgent):
    name = "schedule"

    def _get_value(self, value, key):
        if isinstance(value, dict):
            return value[key]
        return getattr(value, key)

    def run(self, state) -> dict:
        brief = state["brief"]
        event_type = self._get_value(brief, "event_type")
        objective = self._get_value(brief, "objective")
        timeline = self._get_value(brief, "timeline")
        preferred_date = self._get_value(timeline, "preferred_date")
        duration_days = self._get_value(timeline, "duration_days")
        constraints = state.get("constraints") or self._get_value(brief, "constraints")

        milestones = build_milestones(preferred_date, duration_days)

        additional_names: list[str] = []
        try:
            response = self._think(
                SCHEDULE_PROMPT.format(
                    event_type=event_type,
                    objective=objective,
                    duration_days=duration_days,
                    preferred_date=preferred_date.isoformat(),
                    constraints=constraints,
                    feedback=build_feedback_context(state),
                ),
                response_format=_RESPONSE_SCHEMA,
                plan_id=state["plan_id"],
                provider=state.get("provider"),
            )
            candidate = parse_structured_json(response, required_keys={"additional_milestones"})
            if candidate is not None and isinstance(candidate["additional_milestones"], list):
                additional_names = [str(name) for name in candidate["additional_milestones"][:3]]
        except Exception:
            additional_names = []

        for index, name in enumerate(additional_names):
            offset = _ADDITIONAL_MILESTONE_START_OFFSET - index
            milestones.append({"name": name, "date": (preferred_date + timedelta(days=offset)).isoformat()})

        conflicts_detected = check_conflicts(preferred_date, milestones)

        schedule_timeline = ScheduleTimeline(
            milestones=milestones,
            conflicts_detected=conflicts_detected,
        )

        return {"schedule": schedule_timeline}
