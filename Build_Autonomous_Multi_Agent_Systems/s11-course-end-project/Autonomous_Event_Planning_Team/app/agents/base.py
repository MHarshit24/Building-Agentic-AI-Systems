"""Shared bounded ReAct loop every reasoning agent (manager, specialists,
reflection) inherits, so nobody re-implements 'call the LLM a few times
and stop' from scratch.

Depends on one function from Track B's app/llm/client.py:
    complete(prompt: str, tier: Literal["reasoning", "helper"]) -> str
Not built yet — this is an assumed contract, confirm it with your partner."""

from abc import ABC, abstractmethod
from typing import Any

from app.schemas.domain import EventPlanState


class BaseAgent(ABC):
    """One agent = one entry point (`run`) plus a small bounded reasoning
    helper it can use internally. Agents never call the LLM directly —
    always through `self._think()` — so retry/timeout/model-routing logic
    lives in one place, not copy-pasted into every agent file."""

    name: str = "base_agent"

    @abstractmethod
    def run(self, state: EventPlanState) -> Any:
        """Every agent implements this. Reads what it needs from state,
        returns its typed output — a SpecialistOutput, a CritiqueNote, or
        (for the manager) task assignments / the merged EventBlueprint."""
        raise NotImplementedError

    def _think(
        self,
        prompt: str,
        tier: str = "reasoning",
        response_format: dict | None = None,
        plan_id: str | None = None,
        provider: str | None = None,
    ) -> str:
        """tier="reasoning" -> Azure/Anthropic/Gemini (manager, specialist
        core reasoning, reflection scoring). tier="helper" -> local Ollama
        for cheap sub-steps, per the model-tiering optimization in 11.1.

        response_format: pass app.llm.structured_output.build_response_format(...)
        to request schema-constrained JSON output instead of relying on
        prompt wording alone.

        plan_id: pass state["plan_id"] so this call groups under the same
        Langfuse session as every other call for this plan.

        provider: pass state.get("provider") to honor the user's model
        selection (see app.llm.model_router.resolve_chain) instead of the
        default fallback chain."""
        from app.llm.client import complete   # Track B — may not exist yet
        return complete(prompt, tier=tier, response_format=response_format, plan_id=plan_id, provider=provider)