"""
Gemini LLM factory and invocation helper.

``get_llm()``   — returns a cached LangChain ChatOpenAI instance backed by Gemini.
``invoke_llm()`` — wraps a raw LLM call and translates every known OpenAI /
                   Gemini API error into a typed ``GeminiError`` subclass so
                   callers never have to inspect raw openai exceptions.
"""
import os
import logging
from functools import lru_cache

from exceptions import (
    AppError,
    GeminiConfigError,
    GeminiError,
    GeminiInvalidRequestError,
    GeminiNetworkError,
    GeminiQuotaExceededError,
    GeminiRateLimitError,
)

logger = logging.getLogger(__name__)


# ── LLM factory ───────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def get_llm():
    """
    Return a cached LangChain LLM instance backed by the Gemini API
    via its OpenAI-compatible endpoint.

    Environment variables:
        GEMINI_API_KEY    — API key (required)
        GEMINI_MODEL_NAME — model name, e.g. "gemini-2.0-flash" (optional)
        GEMINI_BASE_URL   — OpenAI-compatible base URL (optional)

    Raises:
        GeminiConfigError: if GEMINI_API_KEY is not set.
    """
    from langchain_openai import ChatOpenAI

    api_key  = os.getenv("GEMINI_API_KEY", "").strip()
    model    = os.getenv("GEMINI_MODEL_NAME", "gemini-2.0-flash").strip()
    base_url = os.getenv(
        "GEMINI_BASE_URL",
        "https://generativelanguage.googleapis.com/v1beta/openai/",
    ).strip()

    if not api_key:
        raise GeminiConfigError(
            "GEMINI_API_KEY environment variable is not set. "
            "Add it to your .env file or deployment secrets."
        )

    llm = ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=base_url,
        temperature=0.7,
        max_tokens=4096,
    )
    logger.info("LLM initialized: model=%s, base_url=%s", model, base_url)
    return llm


# ── Safe invocation helper ────────────────────────────────────────────────────

def invoke_llm(prompt: str, callbacks: list | None = None) -> str:
    """
    Invoke the Gemini LLM and return the response text.

    Translates every known OpenAI / Gemini SDK exception into the matching
    ``GeminiError`` subclass so callers can handle them specifically without
    importing the openai package directly.

    Args:
        prompt:    The full prompt string to send to the model.
        callbacks: Optional list of LangChain callbacks (e.g. Langfuse handler).

    Returns:
        The model's response text.

    Raises:
        GeminiConfigError:         Authentication or model-not-found errors.
        GeminiRateLimitError:      HTTP 429 from the Gemini API.
        GeminiQuotaExceededError:  Daily / monthly quota exhausted.
        GeminiNetworkError:        Connection refused, timeout, or 5xx from Gemini.
        GeminiInvalidRequestError: The request was malformed / content was blocked.
        GeminiError:               Any other unexpected LLM error.
    """
    llm = get_llm()
    try:
        invoke_kwargs = {"config": {"callbacks": callbacks}} if callbacks else {}
        response = llm.invoke(prompt, **invoke_kwargs)
        return response.content
    except AppError:
        raise  # already a domain exception — propagate as-is
    except Exception as exc:
        _translate_llm_error(exc)
        raise  # unreachable — _translate_llm_error always raises


# ── Error translation ─────────────────────────────────────────────────────────

def _translate_llm_error(exc: Exception) -> None:
    """
    Classify *exc* and raise the matching ``GeminiError`` subclass.

    Prefers isinstance checks against the openai SDK; falls back to heuristic
    string matching when the package is unavailable or the exception comes from
    a non-openai layer (e.g. LangChain retries, network libraries).

    This function always raises — it never returns.
    """
    # ── openai SDK type-based classification ──────────────────────────────────
    try:
        import openai as _oa
    except ImportError:
        _oa = None  # openai not directly importable; use string matching below

    if _oa is not None:
        if isinstance(exc, _oa.RateLimitError):
            raise GeminiRateLimitError(
                "Gemini API rate limit exceeded. Please wait a moment before retrying."
            ) from exc

        if isinstance(exc, _oa.AuthenticationError):
            raise GeminiConfigError(
                "Gemini API authentication failed. Verify your GEMINI_API_KEY."
            ) from exc

        if isinstance(exc, _oa.PermissionDeniedError):
            raise GeminiConfigError(
                f"Gemini API access denied — check your API key permissions: {exc}"
            ) from exc

        if isinstance(exc, _oa.NotFoundError):
            raise GeminiConfigError(
                "Gemini model not found. Verify GEMINI_MODEL_NAME is correct."
            ) from exc

        if isinstance(exc, (_oa.APIConnectionError, _oa.APITimeoutError)):
            raise GeminiNetworkError(
                "Could not reach the Gemini API. "
                "Check your network connection and retry shortly."
            ) from exc

        if isinstance(exc, _oa.InternalServerError):
            raise GeminiNetworkError(
                f"Gemini API returned an internal server error (5xx): {exc}"
            ) from exc

        if isinstance(exc, _oa.BadRequestError):
            raise GeminiInvalidRequestError(
                "Gemini rejected the request — the prompt may be too long "
                f"or contain content that violates the usage policy: {exc}"
            ) from exc

    # ── Heuristic string-matching fallback ────────────────────────────────────
    msg = str(exc).lower()

    if "rate limit" in msg or "429" in msg:
        raise GeminiRateLimitError(
            "Gemini API rate limit exceeded. Please wait before retrying."
        ) from exc

    if "quota" in msg:
        raise GeminiQuotaExceededError(
            "Gemini API quota exhausted. Check your billing or usage limits."
        ) from exc

    if "authentication" in msg or "api key" in msg or "401" in msg or "unauthenticated" in msg:
        raise GeminiConfigError(
            "Gemini API authentication failed. Verify your GEMINI_API_KEY."
        ) from exc

    if "permission" in msg or "403" in msg:
        raise GeminiConfigError(
            f"Gemini API access denied: {exc}"
        ) from exc

    if (
        "connection" in msg
        or "timeout" in msg
        or "unreachable" in msg
        or "503" in msg
        or "502" in msg
    ):
        raise GeminiNetworkError(
            "Could not reach the Gemini API. Check your network connection."
        ) from exc

    if "400" in msg or "bad request" in msg or "invalid" in msg:
        raise GeminiInvalidRequestError(
            f"Gemini rejected the request: {exc}"
        ) from exc

    raise GeminiError(f"Gemini LLM call failed unexpectedly: {exc}") from exc
