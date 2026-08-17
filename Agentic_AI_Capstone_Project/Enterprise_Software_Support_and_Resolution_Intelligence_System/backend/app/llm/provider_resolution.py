"""
app/llm/provider_resolution.py

Startup-time provider selection (provider_fallback_plan.md): prefer
Azure OpenAI if and only if both its chat and embedding deployments are
genuinely reachable; otherwise fall back to Groq (chat) + Gemini
(embeddings/vision), but only if Groq, Gemini, and the already-implemented
judge model (llama-3.3-70b-versatile, unchanged) are all confirmed
reachable too. Refuses to start (raises) if neither tier fully checks
out — never silently degrades to MockLLMClient, which is a test-only
concept, not a production fallback.

Every check below hits each provider's own free metadata/listing
endpoint only, EXCEPT gemini_model_reachable()'s generateContent path
(see that function's own docstring) — no other generate/embed call, no
other tokens spent, no other billed inference on any provider, including
Azure. A model being listed is not a full reachability guarantee — this
was CONFIRMED live, not just a theoretical concern this docstring used to
flag defensively: the real configured GEMINI_VISION_MODEL
(models/gemini-2.5-flash) stayed listed with generateContent support in
this endpoint long after Google had already started rejecting real
generateContent calls to it with a 404 ("no longer available to new
users"). A listing-only check had zero way to catch this — the deployed
system would have silently believed the fallback tier was fully healthy
while every real vision call failed. gemini_model_reachable() now makes
one minimal, real, deliberately tiny-cost generateContent probe when
required_method=="generateContent" specifically to close this exact,
now-demonstrated gap — see that function's own docstring for the real
cost tradeoff being made. Every other check (Azure deployment listing,
Groq model listing, Gemini embedContent) still catches the dominant
failure modes (expired key, renamed/removed deployment) for free; the
residual gap there is left to call_llm_structured's existing
bounded-retry logic, same as any other transient real-call failure.

No caching across restarts, deliberately: these checks are free, so
re-running the full check on every app start costs nothing and means
Azure becoming valid again later (e.g. renewed) is picked up
automatically on the next restart with zero manual intervention.

Every check function below takes its key/endpoint/model explicitly as
arguments rather than reading get_settings() internally — reusable later
if these keys become per-end-user instead of env-sourced (only the
orchestration in resolve_llm_provider() would need to change then, not
this module's check logic).
"""

from __future__ import annotations

import httpx

from app.config import Settings
from app.logging.structured_logger import log_event
import logging

logger = logging.getLogger(__name__)

_HTTP_TIMEOUT = 10.0

# The classic `GET {endpoint}/openai/deployments` listing endpoint used
# by azure_deployments_reachable() below is a DIFFERENT API surface from
# real chat/embedding calls, with its own, older supported api-version
# range. Real, confirmed finding (not assumed): this project's configured
# settings.azure_openai_api_version (2024-02-01) works fine for actual
# chat completions and embeddings, but returns a plain 404 "Resource not
# found" for THIS listing endpoint specifically on this Azure resource —
# a false negative that made resolve_llm_provider() below believe Azure
# was unreachable and silently fall back to Groq+Gemini for all real
# traffic, even though Azure was fully working. Confirmed 2022-12-01 and
# 2023-03-15-preview both list the real deployments correctly on this
# same resource; 2022-12-01 is used here as the older, more broadly
# supported of the two. Deliberately independent of
# settings.azure_openai_api_version — that setting is correct as-is for
# every other Azure call in this project and must not change.
_DEPLOYMENTS_LIST_API_VERSION = "2022-12-01"


async def _get_json(url: str, *, headers: dict | None = None, params: dict | None = None) -> tuple[int, dict | None]:
    """Shared GET-and-parse helper — the one seam every reachability
    check in this module routes through, so tests only need to
    monkeypatch this single function to control every scenario."""
    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            resp = await client.get(url, headers=headers, params=params)
    except httpx.HTTPError:
        return 0, None
    try:
        body = resp.json()
    except ValueError:
        body = None
    return resp.status_code, body


async def azure_deployments_reachable(
    api_key: str,
    endpoint: str,
    api_version: str,
    chat_deployment: str,
    embedding_deployment: str,
) -> bool:
    """GET {endpoint}/openai/deployments — free, lists real deployments
    on the resource. True only if both the configured chat and embedding
    deployment names actually appear.

    `api_version` (the caller's real chat/embedding api-version) is
    accepted but deliberately NOT used for this specific listing call —
    see _DEPLOYMENTS_LIST_API_VERSION's own comment for the real,
    confirmed reason. Kept as a parameter anyway since callers/tests
    reasonably expect this function's signature to take the resource's
    configured api-version, even though this one call path pins its own."""
    if not api_key or not endpoint or not chat_deployment or not embedding_deployment:
        return False
    status, body = await _get_json(
        f"{endpoint.rstrip('/')}/openai/deployments",
        headers={"api-key": api_key},
        params={"api-version": _DEPLOYMENTS_LIST_API_VERSION},
    )
    if status != 200 or not body:
        return False
    deployment_ids = {item.get("id") for item in body.get("data", [])}
    return chat_deployment in deployment_ids and embedding_deployment in deployment_ids


async def groq_model_reachable(api_key: str, model_id: str) -> bool:
    """GET https://api.groq.com/openai/v1/models — free, lists real
    models available on this key."""
    if not api_key or not model_id:
        return False
    status, body = await _get_json(
        "https://api.groq.com/openai/v1/models",
        headers={"Authorization": f"Bearer {api_key}"},
    )
    if status != 200 or not body:
        return False
    model_ids = {item.get("id") for item in body.get("data", [])}
    return model_id in model_ids


async def _gemini_generate_content_probe(api_key: str, model_id: str) -> bool:
    """A real, minimal, deliberately tiny-cost generateContent call —
    NOT free, unlike every other check in this module, and a real
    trade-off, deliberately made rather than left unaddressed: a listed
    model can be already-deprecated on Google's side (confirmed live —
    see this module's own docstring) and the free listing endpoint alone
    cannot see that. `max_tokens=1` and a one-word prompt keep the real
    cost of this one call as close to negligible as a real call can be,
    and this only ever runs once per process start (resolve_llm_provider
    is not re-invoked per request), not per request. Uses litellm rather
    than a raw httpx POST specifically so this probe exercises the SAME
    real call path app/llm/groq_gemini_client.py's generate_vision()
    actually uses in production — a probe that succeeds via a different
    code path wouldn't actually prove production calls will work."""
    import litellm

    try:
        await litellm.acompletion(
            model=f"gemini/{model_id}",
            messages=[{"role": "user", "content": "Hi"}],
            api_key=api_key,
            max_tokens=1,
        )
        return True
    except Exception as exc:  # noqa: BLE001 — any failure here means "not reachable", not a crash
        log_event(
            logger, "WARNING", "gemini_generate_content_probe_failed",
            model_id=model_id, error=str(exc),
        )
        return False


async def gemini_model_reachable(api_key: str, model_id: str, required_method: str) -> bool:
    """GET https://generativelanguage.googleapis.com/v1beta/models —
    free, lists real models available on this key. True only if
    model_id is listed AND required_method (e.g. "embedContent",
    "generateContent") appears in its supportedGenerationMethods —
    catches the real, confirmed case of a model being listed but not
    actually usable for the method this project needs.

    For required_method=="generateContent" specifically, listing alone
    is NOT sufficient — confirmed live (see this module's own docstring):
    a real, currently-configured vision model stayed listed with
    generateContent support long after Google had already started
    rejecting real calls to it with a 404. So this path also makes one
    real, minimal generateContent probe (_gemini_generate_content_probe)
    before returning True — the only non-free check in this whole
    module, a deliberate, disclosed trade-off given the real,
    demonstrated cost of NOT doing it (a fully silent, undetected outage
    of the vision path)."""
    if not api_key or not model_id:
        return False
    status, body = await _get_json(
        "https://generativelanguage.googleapis.com/v1beta/models",
        params={"key": api_key},
    )
    if status != 200 or not body:
        return False
    target_name = f"models/{model_id}"
    listed_and_supported = False
    for item in body.get("models", []):
        if item.get("name") == target_name:
            listed_and_supported = required_method in item.get("supportedGenerationMethods", [])
            break
    if not listed_and_supported:
        return False
    if required_method == "generateContent":
        return await _gemini_generate_content_probe(api_key, model_id)
    return True


class NoLLMProviderAvailableError(RuntimeError):
    """Raised when neither the Azure tier nor the full Groq+Gemini
    fallback tier is reachable. The app must refuse to start rather than
    silently serve real users from MockLLMClient (a test-only concept)
    or a half-working provider."""


async def resolve_llm_provider(settings: Settings) -> str:
    """Returns "azure" or "groq". Raises NoLLMProviderAvailableError if
    neither tier is fully reachable."""
    azure_ok = await azure_deployments_reachable(
        api_key=settings.azure_openai_api_key,
        endpoint=settings.azure_openai_endpoint,
        api_version=settings.azure_openai_api_version,
        chat_deployment=settings.azure_openai_llm_deployment,
        embedding_deployment=settings.azure_openai_embedding_deployment,
    )
    if azure_ok:
        log_event(logger, "INFO", "llm_provider_resolved", provider="azure")
        return "azure"

    groq_chat_ok = await groq_model_reachable(settings.groq_api_key, settings.groq_chat_model)
    groq_judge_ok = await groq_model_reachable(settings.groq_api_key, settings.groq_judge_model)
    gemini_embed_ok = await gemini_model_reachable(
        settings.gemini_api_key, settings.gemini_embedding_model, "embedContent"
    )
    gemini_vision_ok = await gemini_model_reachable(
        settings.gemini_api_key, settings.gemini_vision_model, "generateContent"
    )

    if groq_chat_ok and groq_judge_ok and gemini_embed_ok and gemini_vision_ok:
        log_event(logger, "INFO", "llm_provider_resolved", provider="groq")
        return "groq"

    log_event(
        logger,
        "ERROR",
        "llm_provider_resolution_failed",
        azure_reachable=azure_ok,
        groq_chat_reachable=groq_chat_ok,
        groq_judge_reachable=groq_judge_ok,
        gemini_embedding_reachable=gemini_embed_ok,
        gemini_vision_reachable=gemini_vision_ok,
    )
    raise NoLLMProviderAvailableError(
        "Neither the Azure OpenAI tier nor the Groq+Gemini fallback tier is fully reachable — "
        f"azure={azure_ok}, groq_chat={groq_chat_ok}, groq_judge={groq_judge_ok}, "
        f"gemini_embedding={gemini_embed_ok}, gemini_vision={gemini_vision_ok}. "
        "Refusing to start rather than silently serving from an unverified provider."
    )
