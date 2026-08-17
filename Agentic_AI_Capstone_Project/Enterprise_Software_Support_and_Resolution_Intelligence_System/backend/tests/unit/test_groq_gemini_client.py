"""
tests/unit/test_groq_gemini_client.py

L1/L2 coverage (§19) for app/llm/groq_gemini_client.py — the fallback-tier
BaseLLMClient (Groq chat, Gemini vision/embeddings). litellm.acompletion/
aembedding are monkeypatched with fakes matching litellm's real response
shapes, verified directly against the installed package (ModelResponse/
Choices/Message and EmbeddingResponse/Embedding all extend openai.BaseModel
-> pydantic.BaseModel — genuine attribute access, not dict-style) — never
a real Groq/Gemini call anywhere in this file, per explicit instruction.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import app.llm.groq_gemini_client as groq_gemini_client_module
from app.llm.base import EMBEDDING_DIMENSIONS
from app.llm.groq_gemini_client import GroqGeminiClient, GroqGeminiEmbeddingDimensionError


def _make_client(monkeypatch, *, groq_chat_model: str) -> GroqGeminiClient:
    # groq_gemini_client.py has its own `from app.config import
    # get_settings` local binding — patching app.config's own attribute
    # would not affect it (confirmed elsewhere this project: the same
    # separate-local-binding gotcha applies to every `from X import Y`
    # site), so the module's own name must be patched directly.
    monkeypatch.setattr(
        groq_gemini_client_module,
        "get_settings",
        lambda: SimpleNamespace(
            groq_api_key="groq-key",
            gemini_api_key="gemini-key",
            groq_chat_model=groq_chat_model,
            gemini_vision_model="gemini-flash-latest",
            gemini_embedding_model="gemini-embedding-001",
        ),
    )
    return GroqGeminiClient()


@pytest.fixture
def client(monkeypatch):
    return _make_client(monkeypatch, groq_chat_model="openai/gpt-oss-20b")


@pytest.fixture
def client_120b(monkeypatch):
    return _make_client(monkeypatch, groq_chat_model="openai/gpt-oss-120b")


def _fake_completion(content: str) -> SimpleNamespace:
    message = SimpleNamespace(content=content)
    choice = SimpleNamespace(message=message)
    return SimpleNamespace(choices=[choice])


def _fake_embedding_response(vectors: list[list[float]]) -> SimpleNamespace:
    data = [SimpleNamespace(embedding=v, index=i) for i, v in enumerate(vectors)]
    return SimpleNamespace(data=data)


@pytest.mark.asyncio
async def test_generate_routes_to_groq_with_prefixed_model(client, monkeypatch):
    captured = {}

    async def fake_acompletion(**kwargs):
        captured.update(kwargs)
        return _fake_completion('{"category": "usage"}')

    monkeypatch.setattr(groq_gemini_client_module.litellm, "acompletion", fake_acompletion)

    result = await client.generate("classify this", response_format={"type": "json_object"})

    assert captured["model"] == "groq/openai/gpt-oss-20b"
    assert captured["api_key"] == "groq-key"
    assert captured["messages"] == [{"role": "user", "content": "classify this"}]
    assert captured["response_format"] == {"type": "json_object"}
    assert result.choices[0].message.content == '{"category": "usage"}'


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "requested,expected_sent",
    [
        ("minimal", "none"),  # the real, confirmed-live remapping (classify_node/account_validation_node)
        ("low", "low"),       # already valid on Groq — passed through unchanged
        ("medium", "medium"),
        ("high", "high"),
    ],
)
async def test_generate_remaps_reasoning_effort_for_groq(client, monkeypatch, requested, expected_sent):
    """Regression test for a real, confirmed-live bug: a real call against
    groq/openai/gpt-oss-20b with reasoning_effort="minimal" was rejected
    with `400 - 'reasoning_effort' : value is not one of the allowed
    values ['none','default','low','medium','high']` — Groq's gpt-oss
    models have no "minimal" tier. Without this remap, classify_node
    (which uses "minimal" on every single request) would 400 on every
    chat request routed to the fallback tier."""
    captured = {}

    async def fake_acompletion(**kwargs):
        captured.update(kwargs)
        return _fake_completion('{"category": "usage"}')

    monkeypatch.setattr(groq_gemini_client_module.litellm, "acompletion", fake_acompletion)

    await client.generate("classify this", reasoning_effort=requested)

    assert captured["reasoning_effort"] == expected_sent


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "requested,expected_sent",
    [
        ("minimal", "low"),  # the real, confirmed-live 120b remapping — NOT "none", unlike 20b
        ("low", "low"),
        ("medium", "medium"),
        ("high", "high"),
    ],
)
async def test_generate_remaps_reasoning_effort_for_groq_120b(client_120b, monkeypatch, requested, expected_sent):
    """Regression test for a real, confirmed-live bug distinct from the
    20b remap above: a real call against groq/openai/gpt-oss-120b with
    reasoning_effort="none" was rejected with `400 - 'reasoning_effort'
    must be one of 'low', 'medium', or 'high'` — the 120b model has NO
    "none"/"default" tier at all, unlike 20b. Reusing 20b's mapping
    ("minimal" -> "none") against 120b unmodified would 400 on every
    single classify/account_validation call — the exact same total-outage
    failure mode the 20b remap itself exists to prevent, just for a
    different model size."""
    captured = {}

    async def fake_acompletion(**kwargs):
        captured.update(kwargs)
        return _fake_completion('{"category": "usage"}')

    monkeypatch.setattr(groq_gemini_client_module.litellm, "acompletion", fake_acompletion)

    await client_120b.generate("classify this", reasoning_effort=requested)

    assert captured["reasoning_effort"] == expected_sent
    assert captured["model"] == "groq/openai/gpt-oss-120b"


@pytest.mark.asyncio
async def test_generate_vision_routes_to_gemini_and_returns_plain_string(client, monkeypatch):
    captured = {}

    async def fake_acompletion(**kwargs):
        captured.update(kwargs)
        return _fake_completion("A flowchart showing the OAuth login sequence.")

    monkeypatch.setattr(groq_gemini_client_module.litellm, "acompletion", fake_acompletion)

    result = await client.generate_vision(b"\x89PNG\r\n\x1a\n" + b"fake", "Caption this diagram.")

    assert captured["model"] == "gemini/gemini-flash-latest"
    assert captured["api_key"] == "gemini-key"
    content_parts = captured["messages"][0]["content"]
    assert content_parts[0] == {"type": "text", "text": "Caption this diagram."}
    assert content_parts[1]["image_url"]["url"].startswith("data:image/png;base64,")
    assert result == "A flowchart showing the OAuth login sequence."


@pytest.mark.asyncio
async def test_embed_routes_to_gemini_with_dimensions_and_returns_vector(client, monkeypatch):
    captured = {}
    expected_vector = [0.1] * EMBEDDING_DIMENSIONS

    async def fake_aembedding(**kwargs):
        captured.update(kwargs)
        return _fake_embedding_response([expected_vector])

    monkeypatch.setattr(groq_gemini_client_module.litellm, "aembedding", fake_aembedding)

    result = await client.embed("How do I reset my password?")

    assert captured["model"] == "gemini/gemini-embedding-001"
    assert captured["api_key"] == "gemini-key"
    assert captured["dimensions"] == EMBEDDING_DIMENSIONS
    assert result == expected_vector


@pytest.mark.asyncio
async def test_embed_raises_on_dimension_mismatch(client, monkeypatch):
    async def fake_aembedding(**kwargs):
        return _fake_embedding_response([[0.1] * 768])  # wrong dimension

    monkeypatch.setattr(groq_gemini_client_module.litellm, "aembedding", fake_aembedding)

    with pytest.raises(GroqGeminiEmbeddingDimensionError):
        await client.embed("some text")


@pytest.mark.asyncio
async def test_embed_batch_preserves_order_via_index(client, monkeypatch):
    v0, v1 = [0.1] * EMBEDDING_DIMENSIONS, [0.2] * EMBEDDING_DIMENSIONS

    async def fake_aembedding(**kwargs):
        # Return out of order on purpose — index must be what restores order.
        data = [SimpleNamespace(embedding=v1, index=1), SimpleNamespace(embedding=v0, index=0)]
        return SimpleNamespace(data=data)

    monkeypatch.setattr(groq_gemini_client_module.litellm, "aembedding", fake_aembedding)

    result = await client.embed_batch(["first text", "second text"])

    assert result == [v0, v1]


@pytest.mark.asyncio
async def test_embed_batch_empty_list_returns_empty_without_calling_litellm(client, monkeypatch):
    called = False

    async def fake_aembedding(**kwargs):
        nonlocal called
        called = True
        return _fake_embedding_response([])

    monkeypatch.setattr(groq_gemini_client_module.litellm, "aembedding", fake_aembedding)

    result = await client.embed_batch([])

    assert result == []
    assert called is False


# ---------------------------------------------------------------------------
# _call_with_rate_limit_retry — regression coverage for a real, confirmed
# gap: a real, live 429 (Groq's 8,000 TPM cap on openai/gpt-oss-120b's free
# tier) was hit during this project's own real end-to-end verification
# (README §37). asyncio.sleep is monkeypatched to a no-op so these tests
# run instantly — the real wait-time computation is covered separately below.
# ---------------------------------------------------------------------------


def _make_rate_limit_error(response=None) -> "groq_gemini_client_module.litellm.exceptions.RateLimitError":
    return groq_gemini_client_module.litellm.exceptions.RateLimitError(
        message="Rate limit reached", llm_provider="groq", model="openai/gpt-oss-120b", response=response,
    )


@pytest.fixture(autouse=True)
def _no_real_sleep(monkeypatch):
    async def _fake_sleep(seconds):
        return None

    monkeypatch.setattr(groq_gemini_client_module.asyncio, "sleep", _fake_sleep)


@pytest.mark.asyncio
async def test_rate_limit_retry_succeeds_on_second_attempt():
    attempts = 0

    async def _call():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise _make_rate_limit_error()
        return "real success on retry"

    result = await groq_gemini_client_module._call_with_rate_limit_retry(_call)

    assert result == "real success on retry"
    assert attempts == 2


@pytest.mark.asyncio
async def test_rate_limit_retry_is_bounded_to_exactly_one_retry():
    attempts = 0

    async def _call():
        nonlocal attempts
        attempts += 1
        raise _make_rate_limit_error()

    with pytest.raises(groq_gemini_client_module.litellm.exceptions.RateLimitError):
        await groq_gemini_client_module._call_with_rate_limit_retry(_call)

    assert attempts == 2  # exactly one bounded retry, never unbounded


@pytest.mark.asyncio
async def test_non_rate_limit_errors_are_never_retried():
    attempts = 0

    async def _call():
        nonlocal attempts
        attempts += 1
        raise ValueError("not a rate limit — must not be retried")

    with pytest.raises(ValueError):
        await groq_gemini_client_module._call_with_rate_limit_retry(_call)

    assert attempts == 1


def test_retry_after_seconds_uses_real_header_when_present():
    fake_response = SimpleNamespace(headers={"retry-after": "12.5"})
    exc = _make_rate_limit_error(response=fake_response)
    assert groq_gemini_client_module._retry_after_seconds(exc) == 12.5


def test_retry_after_seconds_caps_an_unreasonably_large_header():
    fake_response = SimpleNamespace(headers={"retry-after": "999"})
    exc = _make_rate_limit_error(response=fake_response)
    assert groq_gemini_client_module._retry_after_seconds(exc) == groq_gemini_client_module._RATE_LIMIT_MAX_WAIT_SECONDS


def test_retry_after_seconds_falls_back_when_header_missing():
    exc = _make_rate_limit_error(response=None)
    assert groq_gemini_client_module._retry_after_seconds(exc) == groq_gemini_client_module._RATE_LIMIT_FALLBACK_WAIT_SECONDS


@pytest.mark.asyncio
async def test_generate_retries_through_a_real_rate_limit_error(client, monkeypatch):
    attempts = 0

    async def fake_acompletion(**kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise _make_rate_limit_error()
        return _fake_completion('{"category": "usage"}')

    monkeypatch.setattr(groq_gemini_client_module.litellm, "acompletion", fake_acompletion)

    result = await client.generate("classify this")

    assert attempts == 2
    assert result.choices[0].message.content == '{"category": "usage"}'
