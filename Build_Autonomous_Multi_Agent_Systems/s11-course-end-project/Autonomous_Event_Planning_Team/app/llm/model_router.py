"""Responsible for routing requests to the appropriate model provider.

Maps a reasoning "tier" (see app/agents/base.py::_think) to a concrete
LiteLLM completion call, plus an ordered fallback chain for when the
primary provider is unconfigured or fails. Reads exclusively from
app.config.get_settings() per the project-wide config convention.
"""

from app.config import get_settings

# Display order for the UI's model picker and the default fallback chain —
# Azure first (primary), then Anthropic, then Gemini, matching the .env.example
# comments' documented intent ("Fallback LLM: Anthropic... if Azure fails",
# "...Gemini... if Anthropic fails").
PROVIDERS = ["azure", "anthropic", "gemini"]


def _azure_config() -> dict | None:
    settings = get_settings()
    if not (settings.azure_openai_api_key and settings.azure_openai_llm_deployment):
        return None
    return {
        "model": f"azure/{settings.azure_openai_llm_deployment}",
        "api_key": settings.azure_openai_api_key,
        "api_base": settings.azure_openai_endpoint,
        "api_version": settings.azure_openai_api_version,
    }


def _anthropic_config() -> dict | None:
    settings = get_settings()
    if not settings.anthropic_api_key:
        return None
    return {
        "model": f"anthropic/{settings.anthropic_model}",
        "api_key": settings.anthropic_api_key,
        # Anthropic's Messages API requires max_tokens on every request;
        # set an explicit default rather than relying on litellm's own.
        "max_tokens": 4096,
    }


def _gemini_config() -> dict | None:
    settings = get_settings()
    if not settings.gemini_api_key:
        return None
    return {
        "model": f"gemini/{settings.gemini_model}",
        "api_key": settings.gemini_api_key,
    }


def _ollama_config() -> dict | None:
    settings = get_settings()
    return {
        "model": f"ollama/{settings.ollama_model_name}",
        "api_base": settings.ollama_base_url,
    }


_PROVIDER_BUILDERS = {
    "azure": _azure_config,
    "anthropic": _anthropic_config,
    "gemini": _gemini_config,
}


def available_providers() -> list[str]:
    """Providers with real credentials configured, in display order. Used by
    GET /health so the frontend's model picker only ever offers options that
    will actually work, without hardcoding that list client-side."""
    return [name for name in PROVIDERS if _PROVIDER_BUILDERS[name]() is not None]


def resolve_chain(tier: str, provider: str | None = None) -> list[dict]:
    """Return an ordered list of LiteLLM kwargs dicts to try for this tier.
    Each dict is passed to litellm.completion(**cfg, messages=...). Configs
    with missing credentials are omitted rather than attempted and left to
    fail. "helper" only ever targets the local Ollama model — never falls
    back to a paid provider, since it exists purely to keep cheap sub-steps
    cheap.

    provider: an explicit user choice (e.g. "anthropic") restricts the chain
    to that single provider — no silent fallback to a different model than
    the one the user picked. None keeps the default Azure -> Anthropic ->
    Gemini fallback chain. Unknown provider names raise rather than
    silently falling through to the default chain."""
    if tier == "helper":
        return [_ollama_config()]

    if provider is not None:
        builder = _PROVIDER_BUILDERS.get(provider)
        if builder is None:
            raise ValueError(f"Unknown provider: {provider!r}")
        config = builder()
        return [config] if config is not None else []

    chain = [_azure_config(), _anthropic_config(), _gemini_config()]
    return [cfg for cfg in chain if cfg is not None]
