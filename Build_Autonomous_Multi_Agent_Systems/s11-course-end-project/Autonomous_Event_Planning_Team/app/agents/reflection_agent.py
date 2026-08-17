"""Responsible for the reflection agent implementation."""

import json

from app.agents.base import BaseAgent
from app.agents.prompts.reflection_prompts import CRITIQUE_PROMPT
from app.config import get_settings
from app.llm.structured_output import build_response_format, parse_structured_json
from app.observability.langfuse_tracer import record_score
from app.schemas.domain import CritiqueNote

_RESPONSE_SCHEMA = build_response_format(
    "plan_critique",
    {
        "type": "object",
        "properties": {
            "feasibility_score": {"type": "number"},
            "budget_fit_score": {"type": "number"},
            "risk_coverage_score": {"type": "number"},
            "coherence_score": {"type": "number"},
            "feasibility_notes": {"type": "string"},
            "budget_fit_notes": {"type": "string"},
            "risk_coverage_notes": {"type": "string"},
            "coherence_notes": {"type": "string"},
            "revision_targets": {
                "type": "array",
                "items": {"type": "string", "enum": ["logistics", "budget", "marketing", "schedule", "risk"]},
            },
        },
        "required": [
            "feasibility_score", "budget_fit_score", "risk_coverage_score", "coherence_score",
            "feasibility_notes", "budget_fit_notes", "risk_coverage_notes", "coherence_notes",
            "revision_targets",
        ],
        "additionalProperties": False,
    },
)


class ReflectionAgent(BaseAgent):
    name = "reflection"
    WEIGHTS = {
        "feasibility": 0.35,
        "budget_fit": 0.25,
        "risk_coverage": 0.20,
        "coherence": 0.20,
    }

    def _get_value(self, value, key):
        if isinstance(value, dict):
            return value[key]
        return getattr(value, key)

    def critique(self, state) -> dict:
        draft_blueprint = state["draft_blueprint"]
        if hasattr(draft_blueprint, "model_dump_json"):
            blueprint_json = draft_blueprint.model_dump_json()
        else:
            blueprint_json = json.dumps(draft_blueprint)

        brief = state["brief"]
        budget = self._get_value(brief, "budget")
        budget_max_amount = self._get_value(budget, "max_amount")
        budget_currency = self._get_value(budget, "currency")
        audience_size = self._get_value(brief, "audience_size")
        constraints = state.get("constraints") or self._get_value(brief, "constraints")
        venue_preference = self._get_value(brief, "venue_preference")

        # The blueprint JSON alone doesn't carry the original request's
        # constraints/venue preference (EventBlueprint has no such field), so
        # without passing them here the reviewer has no ground truth to check
        # "does this plan honor what was asked" against — it would be scoring
        # coherence against its own guess. Same for budget: without the
        # computed total/within_budget, the reviewer has to do that arithmetic
        # itself from the raw JSON, which is a needless source of noise.
        try:
            draft_budget = self._get_value(draft_blueprint, "budget")
            total_estimated_cost = self._get_value(draft_budget, "total_estimated_cost")
            within_budget = "yes" if self._get_value(draft_budget, "within_budget") else "no"
        except (KeyError, AttributeError, TypeError):
            total_estimated_cost = "unknown"
            within_budget = "unknown"

        # Grounded Reflexion for feasibility (Sprint 5 Advanced): rather than
        # trusting the LLM to notice a too-small venue on its own, compute
        # the one deterministic fact that most directly falsifies
        # feasibility and hand it over as a fact, not an opinion.
        try:
            draft_logistics = self._get_value(draft_blueprint, "logistics")
            venue_capacity = self._get_value(draft_logistics, "capacity")
            venue_capacity_ok = "yes" if venue_capacity >= audience_size else "no"
        except (KeyError, AttributeError, TypeError):
            venue_capacity = "unknown"
            venue_capacity_ok = "unknown"

        prompt = CRITIQUE_PROMPT.format(
            event_blueprint_json=blueprint_json,
            budget_max_amount=budget_max_amount,
            budget_currency=budget_currency,
            total_estimated_cost=total_estimated_cost,
            within_budget=within_budget,
            constraints=constraints,
            venue_preference=venue_preference,
            audience_size=audience_size,
            venue_capacity=venue_capacity,
            venue_capacity_ok=venue_capacity_ok,
        )

        fallback_response = {
            "feasibility_score": 0.5,
            "budget_fit_score": 0.5,
            "risk_coverage_score": 0.5,
            "coherence_score": 0.5,
            "feasibility_notes": "unavailable — LLM call or parsing failed",
            "budget_fit_notes": "unavailable — LLM call or parsing failed",
            "risk_coverage_notes": "unavailable — LLM call or parsing failed",
            "coherence_notes": "unavailable — LLM call or parsing failed",
            "revision_targets": ["logistics", "budget", "marketing", "schedule", "risk"],
        }

        plan_id = state["plan_id"]
        try:
            response = self._think(
                prompt, response_format=_RESPONSE_SCHEMA, plan_id=plan_id, provider=state.get("provider")
            )
            parsed_response = parse_structured_json(response, required_keys=set(fallback_response.keys()))
        except Exception:
            parsed_response = None
        # Read back the exact figure _think() already measured around the
        # raw litellm call and handed to Langfuse (see get_last_duration_ms)
        # instead of independently timing a wider window here — the two
        # would otherwise drift apart (this function also does JSON
        # parsing, and previously included the Langfuse flush() network
        # round trip too), and the UI and Langfuse should show one number.
        # Imported lazily, matching BaseAgent._think's app.llm.client import
        # — both exist so tests can swap in a fake module before this runs.
        from app.llm.client import get_last_duration_ms

        duration_ms = get_last_duration_ms()

        if parsed_response is None:
            parsed_response = fallback_response

        weighted_score = round(
            (
                parsed_response["feasibility_score"] * self.WEIGHTS["feasibility"]
                + parsed_response["budget_fit_score"] * self.WEIGHTS["budget_fit"]
                + parsed_response["risk_coverage_score"] * self.WEIGHTS["risk_coverage"]
                + parsed_response["coherence_score"] * self.WEIGHTS["coherence"]
            ),
            2,
        )
        threshold = state.get("quality_gate_threshold") or get_settings().quality_gate_threshold
        passed = weighted_score >= threshold
        threshold_delta = round(weighted_score - threshold, 4)

        previous_entries = state.get("critique_history") or []
        score_delta = None
        if previous_entries:
            previous_score = self._get_value(previous_entries[-1], "score")
            score_delta = round(weighted_score - previous_score, 4)

        critique_note = CritiqueNote(
            iteration=state["iteration_count"],
            score=weighted_score,
            passed=passed,
            revision_targets=parsed_response["revision_targets"],
            notes={
                "feasibility": parsed_response["feasibility_notes"],
                "budget_fit": parsed_response["budget_fit_notes"],
                "risk_coverage": parsed_response["risk_coverage_notes"],
                "coherence": parsed_response["coherence_notes"],
            },
            duration_ms=duration_ms,
            score_delta=score_delta,
            threshold_delta=threshold_delta,
        )

        # Reported with the exact values just stored on critique_note, so
        # what Langfuse shows for this plan never drifts from what the API
        # serves to the frontend.
        iteration_label = f"iteration {state['iteration_count']}"
        record_score(plan_id, "critique_score", weighted_score, comment=iteration_label)
        record_score(plan_id, "critique_threshold_delta", threshold_delta, comment=iteration_label)
        if score_delta is not None:
            record_score(plan_id, "critique_score_delta", score_delta, comment=iteration_label)

        return {
            # The operator.add reducer on EventPlanState.critique_history
            # appends this to the existing list; do not concatenate here.
            "critique_history": [critique_note],
            "active_revision_targets": [] if passed else critique_note.revision_targets,
        }

    def run(self, state) -> dict:
        return self.critique(state)