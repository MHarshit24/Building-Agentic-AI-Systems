"""Typed exception hierarchy (Section 12.1). Raise/catch from here only —
don't define a new exception type without adding it here first."""


class EventPlanningError(Exception):
    """Base class for every error this system raises on purpose."""


class ValidationError(EventPlanningError):
    """Malformed EventBrief or a schema violation on an agent output."""


class LLMProviderError(EventPlanningError):
    """Azure/Gemini/Ollama call failed after retries (Section 12.2)."""


class AgentExecutionError(EventPlanningError):
    """A specialist or manager agent failed to produce a valid output."""


class MaxIterationsExceededError(EventPlanningError):
    """Escape hatch (Section 6.1) — the graph catches this itself to
    finalize the best available draft, so this isn't necessarily fatal."""