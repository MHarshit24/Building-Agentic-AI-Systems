"""
app/llm/groq_gemini_client.py

The fallback-tier BaseLLMClient implementation (provider_fallback_plan.md):
chat -> Groq (settings.groq_chat_model, e.g. "openai/gpt-oss-20b"),
vision -> Gemini (settings.gemini_vision_model, e.g. "gemini-2.5-flash"),
embeddings -> Gemini (settings.gemini_embedding_model, e.g.
"gemini-embedding-001"). Only ever constructed when
app.llm.provider_resolution.resolve_llm_provider() has already confirmed
all four models reachable, plus the judge model separately (unchanged,
evaluation/groq_judge_client.py).

Built on litellm.acompletion/aembedding, the same library
groq_judge_client.py already proved out — verified directly against the
real installed package (not assumed) that litellm routes the plain
"gemini/" provider (matching a free AI-Studio API key, not the separate
paid Vertex AI product) through the same embedding transformation code
that supports dimension control, via the "dimensions" kwarg (OpenAI's
own naming convention; litellm translates it to Gemini's real
outputDimensionality parameter internally — confirmed by reading that
transformation code directly).

Chat routes to Groq specifically because it's the only fallback-tier
chat model confirmed (this project's own real testing) to support
native strict json_schema structured output — matching
call_llm_structured's existing Azure-shaped request unmodified, unlike
the judge model, which needs the looser json_object fallback (see
groq_judge_client.py's own docstring for that real, separate finding).

generate_vision()'s structured-output combination with Gemini
(response_format passed through call_llm_structured_vision) is
implemented the same way as the text path, but this specific
combination has not been verified against a real call, unlike the
Azure/Gemini-chat-schema combinations that were — flagged here rather
than silently assumed to work.

reasoning_effort remapping — a real, confirmed bug found and fixed, not
a precaution: every LLM-driven orchestration node passes
reasoning_effort=... into call_llm_structured (classify_node/
account_validation_node use "minimal"; doc_retrieval/escalate use "low";
incident_severity/reflect use "medium" — this project's own established
per-node tuning, §13). A real call against groq/openai/gpt-oss-20b with
reasoning_effort="minimal" was rejected outright: `400 - 'reasoning_effort'
: value is not one of the allowed values ['none','default','low','medium',
'high']`. Groq's gpt-oss models don't have a "minimal" tier at all — only
"low" and "medium" (already valid, passed through unchanged) needed no
fix; "minimal" is remapped to Groq's actual floor value, "none", since
that's the correct semantic match (both represent the lowest/near-zero
reasoning tier on their respective scales) — not "low", which would
overstate the effort level classify_node/account_validation_node were
actually asking for. Without this fix, every single chat request would
have 400'd at the classify step — the fallback tier would have been
completely unusable for live serving, not degraded.

The remap is PER-MODEL, not one fixed mapping, because the two real
gpt-oss sizes have genuinely different allowed reasoning_effort ranges —
confirmed via two separate real 400 responses, not assumed to match:
  groq/openai/gpt-oss-20b:  none / default / low / medium / high
  groq/openai/gpt-oss-120b: low / medium / high  (NO "none"/"default" tier
                             at all — `400 - 'reasoning_effort' must be
                             one of 'low', 'medium', or 'high'`)
So "minimal" maps to "none" for the 20b model but must map to "low" (its
actual floor) for the 120b model — reusing 20b's mapping unmodified
against 120b would 400 on every single classify/account_validation call,
the exact same total-outage failure mode this whole mechanism exists to
prevent.

Rate-limit retry — a real, confirmed gap closed, not preemptive
hardening: a real, live `429 Too Many Requests` (Groq's 8,000 TPM cap on
`openai/gpt-oss-120b`'s free tier) was hit during this project's own real
end-to-end verification (README §37). Reading litellm's own source
directly did not give a clear, confirmed answer on whether its async
`acompletion()` path retries a `RateLimitError` automatically (the
`num_retries`/tenacity retry logic found there could not be confirmed to
apply to the async path specifically) — rather than ship a fix that
depends on unverified library-internal behavior, `_call_with_rate_limit_retry()`
below adds one explicit, bounded retry (the exact same "exactly one
bounded retry, never silent, never unbounded" philosophy
`call_llm_structured`'s own Pydantic-validation retry already uses,
app/llm/structured_output.py), waiting on the provider's real
`Retry-After` response header when present, a fixed 5s fallback
otherwise, capped at 30s either way.
"""

from __future__ import annotations

import asyncio
import base64
from typing import Any, Awaitable, Callable, TypeVar

import litellm

from app.config import get_settings

T = TypeVar("T")

_RATE_LIMIT_FALLBACK_WAIT_SECONDS = 5.0
_RATE_LIMIT_MAX_WAIT_SECONDS = 30.0


def _retry_after_seconds(exc: litellm.exceptions.RateLimitError) -> float:
    """The provider's own real Retry-After header if present (httpx.Response
    on the real openai.RateLimitError base class litellm's RateLimitError
    subclasses, confirmed live); a fixed, disclosed fallback otherwise —
    never trusts an unbounded or missing wait hint."""
    response = getattr(exc, "response", None)
    header = response.headers.get("retry-after") if response is not None else None
    if header:
        try:
            return min(float(header), _RATE_LIMIT_MAX_WAIT_SECONDS)
        except ValueError:
            pass
    return _RATE_LIMIT_FALLBACK_WAIT_SECONDS


async def _call_with_rate_limit_retry(call: Callable[[], Awaitable[T]]) -> T:
    """Exactly one bounded retry on a real litellm.exceptions.RateLimitError.
    Any other exception (BadRequestError, NotFoundError, etc.) propagates
    immediately, unretried — a rate limit is the one real, transient
    condition retrying can actually help with; retrying a malformed
    request or a dead model would just waste the wait."""
    try:
        return await call()
    except litellm.exceptions.RateLimitError as exc:
        await asyncio.sleep(_retry_after_seconds(exc))
        return await call()

# Groq's real, confirmed allowed reasoning_effort values per gpt-oss model
# size (each found via a real 400 response, not documentation) — see this
# module's own docstring for the two real error messages. Keyed by the
# BARE model id (no "groq/" litellm prefix), since that's what
# settings.groq_chat_model actually holds.
_REASONING_EFFORT_REMAP_BY_MODEL: dict[str, dict[str, str]] = {
    "openai/gpt-oss-20b": {"minimal": "none"},
    "openai/gpt-oss-120b": {"minimal": "low"},
}
# Safe fallback if a different gpt-oss size (or a future model with no
# known mapping) is ever configured: "low" is a real, valid value on
# every gpt-oss size confirmed so far, so this degrades to "not the
# exact intended floor" rather than a guaranteed 400.
_DEFAULT_REASONING_EFFORT_REMAP: dict[str, str] = {"minimal": "low"}


def _remap_reasoning_effort(kwargs: dict[str, Any], chat_model: str) -> dict[str, Any]:
    """`chat_model` is the bare model id (settings.groq_chat_model), not
    the "groq/"-prefixed litellm string — the remap table above is keyed
    the same way."""
    effort = kwargs.get("reasoning_effort")
    remap = _REASONING_EFFORT_REMAP_BY_MODEL.get(chat_model, _DEFAULT_REASONING_EFFORT_REMAP)
    if effort in remap:
        kwargs = {**kwargs, "reasoning_effort": remap[effort]}
    return kwargs
from app.llm.azure_client import _detect_image_mime_type
from app.llm.base import EMBEDDING_DIMENSIONS, BaseLLMClient


class GroqGeminiEmbeddingDimensionError(Exception):
    """Raised when Gemini's embeddings endpoint returns a vector whose
    length doesn't match EMBEDDING_DIMENSIONS, despite requesting
    dimensions=EMBEDDING_DIMENSIONS explicitly — same fail-loud
    philosophy as azure_client.py's own EmbeddingDimensionError, for the
    same reason (a silent mismatch would surface far more confusingly
    downstream, at a pgvector insert/index)."""


class GroqGeminiClient(BaseLLMClient):
    """Fallback-tier client: Groq for chat, Gemini for vision/embeddings."""

    def __init__(self) -> None:
        settings = get_settings()
        self._groq_api_key = settings.groq_api_key
        self._gemini_api_key = settings.gemini_api_key
        self._groq_chat_model_bare = settings.groq_chat_model  # e.g. "openai/gpt-oss-120b" — no "groq/" prefix
        self._chat_model = f"groq/{settings.groq_chat_model}"
        self._vision_model = f"gemini/{settings.gemini_vision_model}"
        self._embedding_model = f"gemini/{settings.gemini_embedding_model}"

    async def generate(self, prompt: str, **kwargs: Any) -> Any:
        kwargs = _remap_reasoning_effort(kwargs, self._groq_chat_model_bare)
        return await _call_with_rate_limit_retry(lambda: litellm.acompletion(
            model=self._chat_model,
            messages=[{"role": "user", "content": prompt}],
            api_key=self._groq_api_key,
            **kwargs,
        ))

    async def generate_vision(self, image_bytes: bytes, prompt: str, **kwargs: Any) -> str:
        mime_type = _detect_image_mime_type(image_bytes)
        encoded = base64.b64encode(image_bytes).decode("ascii")
        response = await _call_with_rate_limit_retry(lambda: litellm.acompletion(
            model=self._vision_model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime_type};base64,{encoded}"},
                        },
                    ],
                }
            ],
            api_key=self._gemini_api_key,
            **kwargs,
        ))
        return response.choices[0].message.content

    async def embed(self, text: str, **kwargs: Any) -> list[float]:
        response = await _call_with_rate_limit_retry(lambda: litellm.aembedding(
            model=self._embedding_model,
            input=text,
            api_key=self._gemini_api_key,
            dimensions=EMBEDDING_DIMENSIONS,
            **kwargs,
        ))
        vector = response.data[0].embedding
        _check_dimension(vector)
        return vector

    async def embed_batch(self, texts: list[str], **kwargs: Any) -> list[list[float]]:
        if not texts:
            return []
        response = await _call_with_rate_limit_retry(lambda: litellm.aembedding(
            model=self._embedding_model,
            input=texts,
            api_key=self._gemini_api_key,
            dimensions=EMBEDDING_DIMENSIONS,
            **kwargs,
        ))
        ordered = sorted(response.data, key=lambda item: item.index)
        vectors = [item.embedding for item in ordered]
        for vector in vectors:
            _check_dimension(vector)
        return vectors

    @property
    def embedding_namespace(self) -> str:
        return f"gemini:{self._embedding_model.removeprefix('gemini/')}"


def _check_dimension(vector: list[float]) -> None:
    if len(vector) != EMBEDDING_DIMENSIONS:
        raise GroqGeminiEmbeddingDimensionError(
            f"Gemini embeddings endpoint returned a {len(vector)}-dimensional "
            f"vector despite requesting dimensions={EMBEDDING_DIMENSIONS} — "
            "every vector(1536) column in §21's schema assumes this dimension."
        )
