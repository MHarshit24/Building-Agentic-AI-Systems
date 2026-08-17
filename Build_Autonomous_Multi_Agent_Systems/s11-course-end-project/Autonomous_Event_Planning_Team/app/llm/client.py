"""Responsible for LLM client integration and model communication.

Single entry point every agent uses (via app.agents.base.BaseAgent._think):
    complete(prompt: str, tier: "reasoning" | "helper", response_format: dict | None, plan_id: str | None, provider: str | None) -> str

"reasoning" tries Azure OpenAI first, then Anthropic, then Gemini, falling
through the chain if a provider is unconfigured or the call fails. "helper"
targets the local Ollama model only, per the model-tiering split (cheap
sub-steps never hit a paid API). Every attempt is wrapped in the Langfuse
tracer; if every provider in the chain fails, raises LLMProviderError so
callers can degrade gracefully (every current caller already has a
fallback path for this).

provider (e.g. "azure" / "anthropic" / "gemini") pins the call to a single
user-selected provider — see app.llm.model_router.resolve_chain — with no
fallback to a different model than the one requested; None keeps the
default fallback chain.

response_format (see app.llm.structured_output.build_response_format) is
forwarded as-is to litellm.completion() so agents can request
schema-constrained JSON output instead of relying on prompt wording alone.

plan_id is passed to the tracer as the Langfuse session_id, so every call
for one plan groups together in Langfuse. Wall-clock duration is measured
here (not estimated later) and attached to the same trace, so "how long
did this call take" always matches between the app and Langfuse.
"""

import contextvars
import time

import litellm

from app.errors.exceptions import LLMProviderError
from app.llm.model_router import resolve_chain
from app.observability.langfuse_tracer import trace_llm

# Set to the exact figure handed to trace_llm's finish() (and therefore
# attached to the Langfuse generation's metadata.duration_ms), so a caller
# that wants "how long did the LLM call take" can read the same number
# Langfuse records instead of independently timing a wider window (e.g. one
# that also includes response parsing) that would drift from it.
_last_duration_ms: contextvars.ContextVar[float | None] = contextvars.ContextVar(
    "_last_duration_ms", default=None
)


def get_last_duration_ms() -> float | None:
    return _last_duration_ms.get()


def complete(
    prompt: str,
    tier: str = "reasoning",
    response_format: dict | None = None,
    plan_id: str | None = None,
    provider: str | None = None,
) -> str:
    chain = resolve_chain(tier, provider=provider)
    if not chain:
        raise LLMProviderError(
            f"No LLM provider configured for tier={tier!r}"
            + (f", provider={provider!r}" if provider else "")
        )

    messages = [{"role": "user", "content": prompt}]
    last_error: Exception | None = None
    _last_duration_ms.set(None)

    for config in chain:
        call_kwargs = dict(config)
        if response_format is not None:
            call_kwargs["response_format"] = response_format
        with trace_llm(name=f"complete:{tier}", tier=tier, prompt=prompt, session_id=plan_id) as finish:
            start = time.perf_counter()
            try:
                response = litellm.completion(messages=messages, **call_kwargs)
                content = response.choices[0].message.content
                duration_ms = round((time.perf_counter() - start) * 1000, 1)
                finish(content, model=config.get("model"), duration_ms=duration_ms)
                _last_duration_ms.set(duration_ms)
                return content
            except Exception as exc:  # noqa: BLE001 - try the next provider in the chain
                duration_ms = round((time.perf_counter() - start) * 1000, 1)
                last_error = exc
                finish(f"ERROR: {exc}", model=config.get("model"), duration_ms=duration_ms)

    raise LLMProviderError(
        f"All LLM providers failed for tier={tier!r}: {last_error}"
    ) from last_error
