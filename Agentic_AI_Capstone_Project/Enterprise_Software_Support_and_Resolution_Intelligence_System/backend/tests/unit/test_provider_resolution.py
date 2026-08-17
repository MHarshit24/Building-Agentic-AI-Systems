"""
tests/unit/test_provider_resolution.py

L1/L2 coverage (§19) for app/llm/provider_resolution.py — the Azure vs.
Groq+Gemini startup provider selection (provider_fallback_plan.md).
Every real HTTP call goes through the module's own _get_json() seam,
monkeypatched here with fake responses matching real shapes already
observed live during this project's own investigation (Groq/Gemini's
real /models responses, a listed-but-wrong-method Gemini case) — no real
network call anywhere in this file, per explicit instruction.
"""

from __future__ import annotations

import pytest

import app.llm.provider_resolution as provider_resolution_module
from app.config import Settings
from app.llm.provider_resolution import (
    NoLLMProviderAvailableError,
    azure_deployments_reachable,
    gemini_model_reachable,
    groq_model_reachable,
    resolve_llm_provider,
)


def _fake_settings(**overrides) -> Settings:
    defaults = dict(
        azure_openai_endpoint="https://example.openai.azure.com",
        azure_openai_api_key="azure-key",
        azure_openai_embedding_deployment="text-embedding-3-small",
        azure_openai_llm_deployment="gpt-5-mini",
        azure_openai_api_version="2024-02-01",
        langfuse_secret_key="x",
        langfuse_public_key="x",
        langfuse_host="x",
        db_host="localhost",
        db_user="x",
        db_password="x",
        db_name="x",
        jwt_secret_key="x",
        mcp_notification_url="http://localhost:8001",
        smtp_host="x",
        smtp_port=587,
        smtp_username="x",
        smtp_password="x",
        application_email="x@x.com",
        support_email="x@x.com",
        groq_api_key="groq-key",
        groq_judge_model="llama-3.3-70b-versatile",
        gemini_api_key="gemini-key",
        groq_chat_model="openai/gpt-oss-20b",
        gemini_vision_model="gemini-2.5-flash",
        gemini_embedding_model="gemini-embedding-001",
    )
    defaults.update(overrides)
    return Settings(**defaults)


@pytest.fixture
def patch_get_json(monkeypatch):
    """Queues (status, body) tuples returned in call order — the exact
    seam every reachability check in the module routes through."""
    def _patch(responses: list[tuple[int, dict | None]]):
        queue = list(responses)

        async def _fake_get_json(url, *, headers=None, params=None):
            return queue.pop(0)

        monkeypatch.setattr(provider_resolution_module, "_get_json", _fake_get_json)

    return _patch


# ---------------------------------------------------------------------------
# azure_deployments_reachable
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_azure_reachable_when_both_deployments_listed(patch_get_json):
    patch_get_json([(200, {"data": [{"id": "gpt-5-mini"}, {"id": "text-embedding-3-small"}]})])
    result = await azure_deployments_reachable(
        api_key="k", endpoint="https://x.openai.azure.com", api_version="2024-02-01",
        chat_deployment="gpt-5-mini", embedding_deployment="text-embedding-3-small",
    )
    assert result is True


@pytest.mark.asyncio
async def test_azure_unreachable_when_embedding_deployment_missing(patch_get_json):
    patch_get_json([(200, {"data": [{"id": "gpt-5-mini"}]})])
    result = await azure_deployments_reachable(
        api_key="k", endpoint="https://x.openai.azure.com", api_version="2024-02-01",
        chat_deployment="gpt-5-mini", embedding_deployment="text-embedding-3-small",
    )
    assert result is False


@pytest.mark.asyncio
async def test_azure_unreachable_on_non_200(patch_get_json):
    patch_get_json([(401, None)])
    result = await azure_deployments_reachable(
        api_key="bad-key", endpoint="https://x.openai.azure.com", api_version="2024-02-01",
        chat_deployment="gpt-5-mini", embedding_deployment="text-embedding-3-small",
    )
    assert result is False


@pytest.mark.asyncio
async def test_azure_unreachable_when_key_missing_no_http_call(patch_get_json, monkeypatch):
    called = False

    async def _should_not_be_called(*a, **k):
        nonlocal called
        called = True
        return 200, {}

    monkeypatch.setattr(provider_resolution_module, "_get_json", _should_not_be_called)
    result = await azure_deployments_reachable(
        api_key="", endpoint="https://x.openai.azure.com", api_version="2024-02-01",
        chat_deployment="gpt-5-mini", embedding_deployment="text-embedding-3-small",
    )
    assert result is False
    assert called is False


# ---------------------------------------------------------------------------
# groq_model_reachable
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_groq_reachable_when_model_listed(patch_get_json):
    patch_get_json([(200, {"data": [{"id": "openai/gpt-oss-20b"}, {"id": "llama-3.3-70b-versatile"}]})])
    assert await groq_model_reachable("k", "openai/gpt-oss-20b") is True


@pytest.mark.asyncio
async def test_groq_unreachable_when_model_not_listed(patch_get_json):
    patch_get_json([(200, {"data": [{"id": "llama-3.3-70b-versatile"}]})])
    assert await groq_model_reachable("k", "openai/gpt-oss-20b") is False


# ---------------------------------------------------------------------------
# gemini_model_reachable — including the real "listed but wrong tier/method"
# shape confirmed live during this project's own investigation
# (gemini-2.0-flash was listed but had zero free-tier request quota;
# gemini-2.5-flash-lite was listed but 404'd on real use — this function
# can't detect quota/404 directly via a list call, but it DOES catch the
# analogous "listed, but doesn't support the method this project needs"
# case, which is the one signal a list call can actually give).
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gemini_reachable_when_model_listed_with_required_method(patch_get_json):
    patch_get_json([(200, {
        "models": [
            {"name": "models/gemini-embedding-001", "supportedGenerationMethods": ["embedContent", "countTextTokens"]},
        ]
    })])
    assert await gemini_model_reachable("k", "gemini-embedding-001", "embedContent") is True


@pytest.mark.asyncio
async def test_gemini_unreachable_when_required_method_not_supported(patch_get_json):
    """The real, confirmed shape: a model can be listed without supporting
    the specific method this project needs."""
    patch_get_json([(200, {
        "models": [
            {"name": "models/gemini-embedding-001", "supportedGenerationMethods": ["countTextTokens"]},
        ]
    })])
    assert await gemini_model_reachable("k", "gemini-embedding-001", "embedContent") is False


@pytest.mark.asyncio
async def test_gemini_unreachable_when_model_not_listed_at_all(patch_get_json):
    patch_get_json([(200, {"models": [{"name": "models/gemini-2.5-flash", "supportedGenerationMethods": ["generateContent"]}]})])
    assert await gemini_model_reachable("k", "gemini-embedding-001", "embedContent") is False


# ---------------------------------------------------------------------------
# gemini_model_reachable("generateContent") — the real, confirmed-live
# listing-is-not-enough gap: models/gemini-2.5-flash stayed listed with
# generateContent support long after Google had already started rejecting
# real calls to it with a 404. Every generateContent check now also makes
# one real, minimal litellm.acompletion() probe — mocked here via
# _gemini_generate_content_probe directly (not litellm itself), the same
# "patch the module's own seam" pattern this whole file already uses.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gemini_generate_content_reachable_when_listed_and_probe_succeeds(patch_get_json, monkeypatch):
    patch_get_json([(200, {"models": [{"name": "models/gemini-flash-latest", "supportedGenerationMethods": ["generateContent"]}]})])

    async def _fake_probe_ok(api_key, model_id):
        return True

    monkeypatch.setattr(provider_resolution_module, "_gemini_generate_content_probe", _fake_probe_ok)
    assert await gemini_model_reachable("k", "gemini-flash-latest", "generateContent") is True


@pytest.mark.asyncio
async def test_gemini_generate_content_unreachable_when_listed_but_probe_fails(patch_get_json, monkeypatch):
    """The exact real, confirmed-live regression this whole mechanism
    exists to catch: a model listed with generateContent support that
    404s on a real call (Google-side deprecation, e.g. the real
    models/gemini-2.5-flash outage this project hit)."""
    patch_get_json([(200, {"models": [{"name": "models/gemini-2.5-flash", "supportedGenerationMethods": ["generateContent"]}]})])

    async def _fake_probe_fails(api_key, model_id):
        return False

    monkeypatch.setattr(provider_resolution_module, "_gemini_generate_content_probe", _fake_probe_fails)
    assert await gemini_model_reachable("k", "gemini-2.5-flash", "generateContent") is False


@pytest.mark.asyncio
async def test_gemini_embed_content_never_calls_the_generate_content_probe(patch_get_json, monkeypatch):
    """embedContent checks stay listing-only, free — the extra real probe
    is scoped to generateContent specifically, since that's the one
    real, confirmed failure mode."""
    patch_get_json([(200, {"models": [{"name": "models/gemini-embedding-001", "supportedGenerationMethods": ["embedContent"]}]})])
    called = False

    async def _should_not_be_called(api_key, model_id):
        nonlocal called
        called = True
        return True

    monkeypatch.setattr(provider_resolution_module, "_gemini_generate_content_probe", _should_not_be_called)
    assert await gemini_model_reachable("k", "gemini-embedding-001", "embedContent") is True
    assert called is False


# ---------------------------------------------------------------------------
# resolve_llm_provider — the full decision
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_returns_azure_when_fully_reachable(patch_get_json):
    settings = _fake_settings()
    patch_get_json([
        (200, {"data": [{"id": "gpt-5-mini"}, {"id": "text-embedding-3-small"}]}),  # azure
    ])
    assert await resolve_llm_provider(settings) == "azure"


@pytest.mark.asyncio
async def test_resolve_falls_back_to_groq_when_azure_unreachable_and_fallback_fully_reachable(patch_get_json, monkeypatch):
    async def _fake_probe_ok(api_key, model_id):
        return True

    monkeypatch.setattr(provider_resolution_module, "_gemini_generate_content_probe", _fake_probe_ok)
    settings = _fake_settings()
    patch_get_json([
        (401, None),  # azure fails
        (200, {"data": [{"id": "openai/gpt-oss-20b"}]}),  # groq chat
        (200, {"data": [{"id": "llama-3.3-70b-versatile"}]}),  # groq judge
        (200, {"models": [{"name": "models/gemini-embedding-001", "supportedGenerationMethods": ["embedContent"]}]}),  # gemini embed
        (200, {"models": [{"name": "models/gemini-2.5-flash", "supportedGenerationMethods": ["generateContent"]}]}),  # gemini vision listed
    ])
    assert await resolve_llm_provider(settings) == "groq"


@pytest.mark.asyncio
async def test_resolve_raises_when_neither_tier_fully_reachable(patch_get_json):
    settings = _fake_settings()
    patch_get_json([
        (401, None),  # azure fails
        (200, {"data": [{"id": "openai/gpt-oss-20b"}]}),  # groq chat ok
        (200, {"data": []}),  # groq judge missing
        (200, {"models": [{"name": "models/gemini-embedding-001", "supportedGenerationMethods": ["embedContent"]}]}),  # gemini embed ok
        (200, {"models": []}),  # gemini vision missing
    ])
    with pytest.raises(NoLLMProviderAvailableError):
        await resolve_llm_provider(settings)


@pytest.mark.asyncio
async def test_resolve_raises_when_gemini_vision_listed_but_real_probe_fails(patch_get_json, monkeypatch):
    """The real, confirmed-live regression this whole resolve_llm_provider
    path exists to prevent: a Gemini vision model listed as generateContent
    -capable that actually 404s on real use (the exact real outage this
    project hit on models/gemini-2.5-flash) must NOT let resolve_llm_provider
    believe the fallback tier is healthy."""

    async def _fake_probe_fails(api_key, model_id):
        return False

    monkeypatch.setattr(provider_resolution_module, "_gemini_generate_content_probe", _fake_probe_fails)
    settings = _fake_settings()
    patch_get_json([
        (401, None),  # azure fails
        (200, {"data": [{"id": "openai/gpt-oss-20b"}]}),  # groq chat ok
        (200, {"data": [{"id": "llama-3.3-70b-versatile"}]}),  # groq judge ok
        (200, {"models": [{"name": "models/gemini-embedding-001", "supportedGenerationMethods": ["embedContent"]}]}),  # gemini embed ok
        (200, {"models": [{"name": "models/gemini-2.5-flash", "supportedGenerationMethods": ["generateContent"]}]}),  # gemini vision listed, but probe below fails
    ])
    with pytest.raises(NoLLMProviderAvailableError):
        await resolve_llm_provider(settings)
