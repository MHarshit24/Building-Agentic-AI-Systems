"""Centralized settings, loaded once via the dual .env pattern (root
secrets + project-specific overrides) and shared everywhere via
get_settings(). No other file in this project should read os.environ or
call load_dotenv() directly."""

import os
import sys
from functools import lru_cache
from pathlib import Path

from dotenv import dotenv_values, load_dotenv
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _load_env() -> None:
    """
    Load environment variables using the dual .env pattern.

    Root .env (parents[4]) — C:\\Users\\harsh\\NIIT\\Building_Agentic_AI_Systems\\.env
    — is loaded first, for shared secrets: AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_LLM_DEPLOYMENT,
    AZURE_OPENAI_API_VERSION, ANTHROPIC_API_KEY, ANTHROPIC_MODEL_NAME,
    GEMINI_API_KEY, GEMINI_MODEL, GUARDRAILS_API_KEY, LANGFUSE_PUBLIC_KEY,
    LANGFUSE_SECRET_KEY, LANGFUSE_HOST.

    Project .env (parents[1]) — .../Autonomous_Event_Planning_Team\\.env —
    is loaded second with override=True, for project-only config:
    OLLAMA_BASE_URL, OLLAMA_MODEL_NAME, PII_ENGINE, PRESIDIO_ENABLED,
    DEBUG_MODE, DATABASE_URL, MAX_ITERATIONS.

    Secrets from root .env are preserved across the second load so the
    project .env can never accidentally blank them out.

    This file: app/config.py -> parents[0]=app/, parents[1]=project root
    (Autonomous_Event_Planning_Team), parents[2]=s11-course-end-project,
    parents[3]=Build_Autonomous_Multi_Agent_Systems,
    parents[4]=Building_Agentic_AI_Systems (root).
    """
    if "pytest" in sys.modules:
        return

    # On Vercel (and other platforms that inject env vars directly), there is
    # no local .env file tree to walk up to, and the deployed file depth
    # differs from the dev machine's, so parents[4] below would raise
    # IndexError. Vercel sets VERCEL=1 in both build and runtime.
    if os.environ.get("VERCEL"):
        return

    base_dir = Path(__file__).resolve().parents[4]
    base_env_path = base_dir / ".env"

    if base_env_path.exists():
        load_dotenv(dotenv_path=base_env_path)
    else:
        load_dotenv()

    # Preserve root secrets before the project .env can touch them
    preserved = {
        key: os.getenv(key)
        for key in (
            "AZURE_OPENAI_API_KEY",
            "AZURE_OPENAI_ENDPOINT",
            "AZURE_OPENAI_LLM_DEPLOYMENT",
            "AZURE_OPENAI_API_VERSION",
            "ANTHROPIC_API_KEY",
            "ANTHROPIC_MODEL_NAME",
            "GEMINI_API_KEY",
            "GEMINI_MODEL",
            "GUARDRAILS_API_KEY",
            "LANGFUSE_PUBLIC_KEY",
            "LANGFUSE_SECRET_KEY",
            "LANGFUSE_HOST",
        )
    }

    proj_dir = Path(__file__).resolve().parents[1]
    proj_env_path = proj_dir / ".env"

    if proj_env_path.exists():
        load_dotenv(dotenv_path=proj_env_path, override=True)
    else:
        load_dotenv()

    # Restore preserved secrets so project .env can never overwrite them
    for key, value in preserved.items():
        if value:
            os.environ[key] = value

    # Remove conflicting PostgreSQL variables that may leak in from root
    # .env (root .env's DATABASE_URL points at a completely different
    # assignment's Postgres DB — this project uses its own local SQLite
    # file instead, so that value must never survive into this process).
    conflicting_pg_vars = [
        "DATABASE_URL", "POSTGRES_URL", "PGHOST", "PGPORT",
        "PGUSER", "PGPASSWORD", "PGDATABASE",
    ]
    for var in conflicting_pg_vars:
        os.environ.pop(var, None)

    # Re-apply THIS project's own DATABASE_URL, read directly from the
    # project .env file (not from the just-cleared os.environ), so the
    # pop above only ever removes the leaked Postgres value from root,
    # never this project's own SQLite path.
    if proj_env_path.exists():
        project_values = dotenv_values(proj_env_path)
        project_db_url = project_values.get("DATABASE_URL")
        if project_db_url:
            os.environ["DATABASE_URL"] = project_db_url

    # Drop any remaining key that resolved to an empty string, so Pydantic
    # falls back to the field default instead of failing to parse "" as
    # int/bool (affects DEBUG_MODE, MAX_ITERATIONS, PRESIDIO_ENABLED, etc.)
    for key in list(os.environ.keys()):
        if os.environ.get(key) == "":
            os.environ.pop(key, None)


_load_env()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    # Primary LLM — Azure OpenAI (root .env)
    azure_openai_api_key: str = ""
    azure_openai_endpoint: str = ""
    azure_openai_llm_deployment: str = Field(
        default="",
        validation_alias=AliasChoices("AZURE_OPENAI_LLM_DEPLOYMENT", "AZURE_OPENAI_DEPLOYMENT_NAME"),
    )
    azure_openai_api_version: str = ""

    # Fallback LLM — Anthropic (root .env)
    anthropic_api_key: str = ""
    anthropic_model: str = Field(
        default="claude-sonnet-5",
        validation_alias=AliasChoices("ANTHROPIC_MODEL", "ANTHROPIC_MODEL_NAME"),
    )

    # Fallback LLM — Gemini (root .env)
    gemini_api_key: str = ""
    gemini_model: str = Field(
        default="gemini-flash-lite-latest",
        validation_alias=AliasChoices("GEMINI_MODEL", "GEMINI_MODEL_NAME"),
    )

    # Local helper-task LLM — Ollama (project .env)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model_name: str = "phi3:mini"

    # Security / PII (project .env)
    pii_engine: str = "presidio"
    presidio_enabled: bool = True
    guardrails_api_key: str = ""          # root .env; blank is expected on Presidio-only setups

    # Observability (root .env)
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = ""

    # Orchestration behavior (project .env)
    max_iterations: int = 3
    quality_gate_threshold: float = 0.80

    # Misc (project .env)
    debug_mode: bool = False
    database_url: str = "sqlite:///./event_plans.db"

    # API (project .env) — comma-separated origins allowed to call this API
    # cross-origin, e.g. a Vercel-hosted frontend. "*" allows any origin.
    cors_allowed_origins: str = "*"


@lru_cache
def get_settings() -> Settings:
    """Import this everywhere, never Settings() directly."""
    return Settings()