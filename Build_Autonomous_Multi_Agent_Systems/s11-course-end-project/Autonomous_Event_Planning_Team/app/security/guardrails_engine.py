"""Responsible for guardrails enforcement logic.

Best-effort and config-gated: with no `guardrails_api_key` configured, or if
the `guardrails-ai` package / its hub validators aren't available, this
no-ops rather than blocking a planning request.
"""

from functools import lru_cache

from app.config import get_settings


@lru_cache
def _get_guard():
    if not get_settings().guardrails_api_key:
        return None
    try:
        from guardrails import Guard
        from guardrails.hub import ToxicLanguage

        return Guard().use(ToxicLanguage(on_fail="fix"))
    except Exception:
        return None


def enforce(text: str) -> str:
    """Run text through the configured guard, returning the validated (or
    unmodified) text. Never raises."""
    if not text:
        return text

    guard = _get_guard()
    if guard is None:
        return text

    try:
        result = guard.validate(text)
        return result.validated_output or text
    except Exception:
        return text
