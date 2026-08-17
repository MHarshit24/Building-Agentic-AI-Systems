"""
Central configuration for the Enterprise Software Support & Resolution
Intelligence System.

get_settings() is the SOLE access point for environment/config values in
this codebase. No other module should read os.environ directly.
"""

import json
import logging
import os
import sys
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import dotenv_values, load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


def _load_env() -> tuple[set[str], set[str]]:
    """
    Load environment variables using the project's established
    secret-preservation dual-.env pattern.

    - Root .env (Building_Agentic_AI_Systems/.env) is loaded first for
      account-level secrets shared across every assignment: AZURE_OPENAI_*,
      LANGFUSE_*, DB_HOST/DB_PORT/DB_USER/DB_PASSWORD, SMTP_*.
    - Project .env (this project's root) is loaded second with
      override=True, for project-scoped values: DB_NAME, JWT_SECRET_KEY,
      REDIS_URL, MCP_NOTIFICATION_URL.
    - Root secrets are preserved across the second load so a stray
      same-named variable in the project .env can never silently
      overwrite them.
    - Stray/conflicting Postgres variables that don't belong to this
      project's isolation scheme are explicitly dropped, whichever file
      they came from.
    - Returns the raw key sets found in each file so the caller can scrub
      anything neither file's keys nor this project's declared Settings
      fields need — see the scrub pass below the Settings class.

    File location: backend/app/config.py
      parents[0] = backend/app
      parents[1] = backend
      parents[2] = <project root>   (Enterprise_Software_Support_and_Resolution_Intelligence_System)
      parents[3] = Agentic_AI_Capstone_Project
      parents[4] = Building_Agentic_AI_Systems   (root)
    """
    # Skip loading .env when tests intentionally clear/mock environment
    if "pytest" in sys.modules:
        return set(), set()

    this_file = Path(__file__).resolve()

    # ---- Root .env ----
    root_env_path = this_file.parents[4] / ".env"
    root_keys = set(dotenv_values(root_env_path).keys()) if root_env_path.exists() else set()
    if root_env_path.exists():
        load_dotenv(dotenv_path=root_env_path)
        logger.debug(f"Loaded root .env from {root_env_path}")
    else:
        logger.warning(f"Root .env not found at {root_env_path}")

    # Preserve root secrets before the project .env can touch them
    db_password = os.getenv("DB_PASSWORD")
    azure_api_key = os.getenv("AZURE_OPENAI_API_KEY")
    azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")

    # ---- Project .env ----
    project_env_path = this_file.parents[2] / ".env"
    project_keys = set(dotenv_values(project_env_path).keys()) if project_env_path.exists() else set()
    if project_env_path.exists():
        load_dotenv(dotenv_path=project_env_path, override=True)
        logger.debug(f"Loaded project .env from {project_env_path}")
    else:
        logger.warning(f"Project .env not found at {project_env_path}")

    # Restore preserved secrets so the project .env can never overwrite them
    if db_password:
        os.environ["DB_PASSWORD"] = db_password
    if azure_api_key:
        os.environ["AZURE_OPENAI_API_KEY"] = azure_api_key
    if azure_endpoint:
        os.environ["AZURE_OPENAI_ENDPOINT"] = azure_endpoint

    # Drop stray/unused Postgres variables so they can never cause a silent
    # misroute (this project deliberately builds its connection string from
    # DB_HOST/DB_PORT/DB_USER/DB_PASSWORD/DB_NAME only, never a raw URL var)
    conflicting_pg_vars = [
        "DATABASE_URL",
        "POSTGRES_URL",
        "POSTGRES_PASSWORD",
        "PGHOST",
        "PGPORT",
        "PGUSER",
        "PGPASSWORD",
        "PGDATABASE",
    ]
    for var in conflicting_pg_vars:
        os.environ.pop(var, None)

    return root_keys, project_keys


_ROOT_ENV_KEYS, _PROJECT_ENV_KEYS = _load_env()


class Settings(BaseSettings):
    """
    Typed, validated settings for the whole backend. Field names are
    matched case-insensitively against environment variable names by
    pydantic-settings; this class deliberately does NOT declare its own
    env_file, since _load_env() above already assembled the correct,
    precedence-ordered environment before this class is instantiated.
    """

    model_config = SettingsConfigDict(case_sensitive=False, extra="ignore")

    # --- Azure OpenAI (root .env) ---
    azure_openai_endpoint: str
    azure_openai_api_key: str
    azure_openai_embedding_deployment: str
    azure_openai_llm_deployment: str = "gpt-5-mini"
    azure_openai_api_version: str

    # --- Langfuse (root .env) ---
    langfuse_secret_key: str
    langfuse_public_key: str
    langfuse_host: str

    # --- Database (host/user/password from root .env, name from project .env) ---
    db_host: str
    db_port: int = 5432
    db_user: str
    db_password: str
    db_name: str

    # --- Auth (project .env) ---
    jwt_secret_key: str

    # --- CORS (project .env) — comma-separated allowed origins for the
    # frontend. Kept as a plain str field (not list[str]) because
    # pydantic-settings expects list-typed env vars to be JSON-encoded;
    # a comma-separated string matches this project's other env-var
    # conventions and is parsed via the cors_origins_list property below. ---
    cors_allowed_origins: str = "http://localhost:5173"

    # --- Redis (project .env) — optional for now, deferred until Memurai is set up ---
    redis_url: str | None = Field(default=None)

    # --- MCP notification server (project .env) ---
    mcp_notification_url: str

    # --- Mailtrap SMTP (root .env) ---
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    application_email: str
    support_email: str

    # --- LLM provider selection ---
    # "azure" (default, production), "groq" (fallback tier: Groq chat +
    # Gemini embeddings/vision, resolved automatically at startup —
    # app/llm/provider_resolution.py), or "mock" (CI / local dev without
    # real credentials). Used by the get_llm_client() factory in
    # app/llm/azure_client.py — this is the SOLE switch point; nothing
    # else should read LLM_PROVIDER from os.environ directly.
    llm_provider: str = "azure"

    # --- Independent LLM judge (§24.2, root .env for the shared secret,
    # project .env for this project's own model choice) ---
    # groq_api_key is a shared, account-level secret (root .env), same
    # category as azure_openai_api_key — never touched by this project.
    groq_api_key: str = ""
    # groq_judge_model is the bare model ID as Groq names it (e.g.
    # "llama-3.3-70b-versatile") — the "groq/" litellm provider prefix is added
    # only at the evaluation/groq_judge_client.py call site, never stored
    # here, so this value stays meaningful if the client implementation
    # ever changes away from litellm.
    groq_judge_model: str = ""

    # --- Azure fallback tier (provider_fallback_plan.md) — Groq for chat,
    # Gemini for embeddings/vision. API keys are shared, account-level
    # secrets (root .env); model names are project-specific choices
    # (project .env), same split as groq_api_key/groq_judge_model above. ---
    gemini_api_key: str = ""
    groq_chat_model: str = ""
    gemini_vision_model: str = ""
    gemini_embedding_model: str = ""

    # --- Confidence tier thresholds (§6), calibration-overridable ---
    # Today's starting values (project .env) — evaluation/calibrate_
    # thresholds.py's real output is evaluation/results/calibrated_
    # thresholds.json, applied as an override in get_settings() below,
    # never a source-code edit or a .env rewrite.
    confidence_high_threshold: float = 0.85
    confidence_medium_threshold: float = 0.70

    # --- Password reset token expiry (production-readiness gap analysis,
    # item B.4) — bounds the exposure window of an intercepted reset email ---
    password_reset_token_expiry_minutes: int = 30

    # --- Active prompt version (§32.4 promotion workflow) ---
    # A prompt file is never edited in place once live — a new version
    # file is added instead (classify_v1.py -> classify_v2.py), and
    # promotion is meant to be this ONE field, not a source-code edit to
    # every node. The blueprint names it as a single global switch (not
    # one field per agent), so every agent's prompt module is expected to
    # move in lockstep when this is bumped — app/prompts/loader.py's
    # get_build_prompt() is the one place that resolves
    # "<agent_name>_<version>" into an actual module, read fresh via
    # get_settings() each call rather than cached at import time, so a
    # promotion takes effect on the next process start with no other
    # change, matching how calibrated_thresholds.json already works.
    active_prompt_version: str = "v1"

    @property
    def cors_origins_list(self) -> list[str]:
        """Parsed, whitespace-trimmed, empty-entry-filtered form of
        cors_allowed_origins — what main.py's CORSMiddleware actually uses."""
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]

    @property
    def database_url(self) -> str:
        """Sync connection string (psycopg) — used by Alembic migrations."""
        password = quote_plus(self.db_password)
        return (
            f"postgresql+psycopg://{self.db_user}:{password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def async_database_url(self) -> str:
        """Async connection string (asyncpg) — used by the FastAPI app at runtime."""
        password = quote_plus(self.db_password)
        return (
            f"postgresql+asyncpg://{self.db_user}:{password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def checkpointer_conn_string(self) -> str:
        """§40's Postgres checkpointer uses langgraph-checkpoint-postgres,
        built on raw psycopg/psycopg-pool — a separate driver/pool from
        this app's SQLAlchemy+asyncpg stack above, so it needs its own
        plain `postgresql://` DSN (psycopg's own conninfo format; the
        `+psycopg`/`+asyncpg` dialect suffixes above are SQLAlchemy-only
        and not valid here). Same host/port/user/password/db_name."""
        password = quote_plus(self.db_password)
        return (
            f"postgresql://{self.db_user}:{password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


# Scrub anything either .env file loaded that this project doesn't actually
# declare a use for — e.g. GEMINI_*, OPENROUTER_*, HF_*, ASTRA_DB_*,
# VITE_AUTH0_*, niit_gitlab_link, LLAMA_CLOUD_API_KEY, etc. from root .env,
# left over from other assignments sharing that file (GROQ_API_KEY is no
# longer in this list — §24.2's independent judge is a real, declared use
# of it now). Derived
# from Settings' own declared fields rather than a hardcoded blacklist, so
# it self-maintains if fields are ever added/removed, and it never touches
# pre-existing system environment variables that didn't come from either
# .env file (e.g. PATH).
_ALLOWED_ENV_KEYS = {name.upper() for name in Settings.model_fields}
for _key in _ROOT_ENV_KEYS | _PROJECT_ENV_KEYS:
    if _key.upper() not in _ALLOWED_ENV_KEYS:
        os.environ.pop(_key, None)


_CALIBRATED_THRESHOLDS_PATH = (
    Path(__file__).resolve().parents[1] / "evaluation" / "results" / "calibrated_thresholds.json"
)


def _apply_calibrated_thresholds(settings: Settings) -> None:
    """evaluation/calibrate_thresholds.py's real output — a small JSON
    file, never a .env rewrite or a source-code edit (keeps get_settings()
    the sole thing app/orchestration/nodes/reflect.py ever touches).
    Silently a no-op until the first real calibration run has produced
    this file; malformed/partial content logs a warning and keeps
    whichever values (file or .env default) already parsed correctly,
    rather than crashing settings load over a bad calibration artifact."""
    if not _CALIBRATED_THRESHOLDS_PATH.exists():
        return
    try:
        overrides = json.loads(_CALIBRATED_THRESHOLDS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning(f"Failed to read {_CALIBRATED_THRESHOLDS_PATH}: {exc}")
        return
    if "confidence_high_threshold" in overrides:
        settings.confidence_high_threshold = float(overrides["confidence_high_threshold"])
    if "confidence_medium_threshold" in overrides:
        settings.confidence_medium_threshold = float(overrides["confidence_medium_threshold"])


@lru_cache
def get_settings() -> Settings:
    """
    Sole access point for configuration in this codebase.
    Cached so .env is only parsed once per process.
    """
    settings = Settings()
    _apply_calibrated_thresholds(settings)
    logger.debug(
        "Settings loaded: db=%s@%s:%s/%s, redis_configured=%s, mcp_url=%s",
        settings.db_user,
        settings.db_host,
        settings.db_port,
        settings.db_name,
        settings.redis_url is not None,
        settings.mcp_notification_url,
    )
    return settings