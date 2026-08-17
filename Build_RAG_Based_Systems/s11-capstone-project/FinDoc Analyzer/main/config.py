"""
FinDoc Analyzer — Centralized configuration and logging.
Dual .env loader: root .env (secrets) + project .env (config).
quote_plus applied to DB_PASSWORD wherever connection strings are built.
"""

import os
import sys
import logging
from pathlib import Path
from typing import Dict, Any
from urllib.parse import quote_plus
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


def _load_env():
    """
    Dual .env loader.
    config.py lives at main/config.py
      parents[4] = Building_Agentic_AI_Systems  -> root .env (secrets)
      parents[1] = FinDoc Analyzer              -> project .env (config)
    """
    if "pytest" in sys.modules:
        return

    base_dir = Path(__file__).resolve().parents[4]
    base_env_path = base_dir / ".env"

    if base_env_path.exists():
        load_dotenv(dotenv_path=base_env_path)
        logger.debug(f"Loaded root .env from {base_env_path}")
    else:
        load_dotenv()
        logger.warning(f"Root .env not found at {base_env_path}, falling back to default load_dotenv()")

    _preserved = {
        "DB_PASSWORD":           os.getenv("DB_PASSWORD"),
        "AZURE_OPENAI_API_KEY":  os.getenv("AZURE_OPENAI_API_KEY"),
        "AZURE_OPENAI_ENDPOINT": os.getenv("AZURE_OPENAI_ENDPOINT"),
        "LANGFUSE_PUBLIC_KEY":   os.getenv("LANGFUSE_PUBLIC_KEY"),
        "LANGFUSE_SECRET_KEY":   os.getenv("LANGFUSE_SECRET_KEY"),
        "LANGFUSE_HOST":         os.getenv("LANGFUSE_HOST"),
    }

    proj_dir = Path(__file__).resolve().parents[1]
    proj_env_path = proj_dir / ".env"

    if proj_env_path.exists():
        load_dotenv(dotenv_path=proj_env_path, override=True)
        logger.debug(f"Loaded project .env from {proj_env_path}")
    else:
        load_dotenv()
        logger.warning(f"Project .env not found at {proj_env_path}, falling back to default load_dotenv()")

    for key, val in _preserved.items():
        if val:
            os.environ[key] = val

    for var in ["DATABASE_URL", "POSTGRES_URL", "PGHOST", "PGPORT",
                "PGUSER", "PGPASSWORD", "PGDATABASE"]:
        os.environ.pop(var, None)


def setup_logging(level: int = logging.INFO):
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )
    for noisy in ["urllib3", "openai", "watchfiles", "httpx", "httpcore", "anthropic"]:
        logging.getLogger(noisy).setLevel(logging.WARNING)


setup_logging()


def load_config() -> Dict[str, Any]:
    """Load and validate all environment configuration."""
    _load_env()
    logger.info("Loading FinDoc Analyzer configuration...")

    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "azure").lower()

    DB_USER     = os.getenv("DB_USER",     "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DB_HOST     = os.getenv("DB_HOST",     "localhost")
    DB_PORT     = os.getenv("DB_PORT",     "5432")
    DB_NAME     = os.getenv("DB_NAME",     "findoc_db")

    # quote_plus on password to handle special characters safely
    DB_PASSWORD_ENCODED = quote_plus(DB_PASSWORD) if DB_PASSWORD else ""

    AZURE_OPENAI_ENDPOINT       = os.getenv("AZURE_OPENAI_ENDPOINT")
    AZURE_OPENAI_API_KEY        = os.getenv("AZURE_OPENAI_API_KEY")
    AZURE_OPENAI_API_VERSION    = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01")
    AZURE_OPENAI_LLM_DEPLOYMENT = os.getenv("AZURE_OPENAI_LLM_DEPLOYMENT")
    AZURE_OPENAI_LLM_MODEL      = os.getenv("AZURE_OPENAI_LLM_MODEL",      "gpt-4o-mini")
    AZURE_OPENAI_EMB_DEPLOYMENT = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")
    AZURE_OPENAI_EMB_MODEL      = os.getenv("AZURE_OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
    ANTHROPIC_MODEL   = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")

    OPENAI_API_KEY         = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL           = os.getenv("OPENAI_MODEL",           "gpt-4o-mini")
    OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

    DB_TABLE_NAME    = os.getenv("DB_TABLE_NAME",    "findoc_embeddings")
    DB_FINANCE_TABLE = os.getenv("DB_FINANCE_TABLE", "financial_statements")

    LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY")
    LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY")
    LANGFUSE_HOST       = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

    MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "https://huggingface.co/mcp")
    HF_TOKEN       = os.getenv("HF_TOKEN")

    SMTP_HOST         = os.getenv("SMTP_HOST")
    SMTP_PORT         = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME     = os.getenv("SMTP_USERNAME")
    SMTP_PASSWORD     = os.getenv("SMTP_PASSWORD")
    APPLICATION_EMAIL = os.getenv("APPLICATION_EMAIL")
    SUPPORT_EMAIL     = os.getenv("SUPPORT_EMAIL")

    config: Dict[str, Any] = {
        "llm_provider": LLM_PROVIDER,
        # DB — always use quote_plus-encoded password in connection strings
        "database_url":     f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD_ENCODED}@{DB_HOST}:{DB_PORT}/{DB_NAME}",
        "psycopg2_dsn":     f"postgresql://{DB_USER}:{DB_PASSWORD_ENCODED}@{DB_HOST}:{DB_PORT}/{DB_NAME}",
        "db_user":          DB_USER,
        "db_password":      DB_PASSWORD,          # raw, for psycopg2 keyword arg
        "db_password_enc":  DB_PASSWORD_ENCODED,  # encoded, for connection strings
        "db_host":          DB_HOST,
        "db_port":          DB_PORT,
        "db_name":          DB_NAME,
        "db_vector_table":  DB_TABLE_NAME,
        "db_finance_table": DB_FINANCE_TABLE,
        # Azure OpenAI
        "azure_endpoint":       AZURE_OPENAI_ENDPOINT,
        "azure_api_key":        AZURE_OPENAI_API_KEY,
        "azure_api_version":    AZURE_OPENAI_API_VERSION,
        "azure_llm_deployment": AZURE_OPENAI_LLM_DEPLOYMENT,
        "azure_llm_model":      AZURE_OPENAI_LLM_MODEL,
        "azure_emb_deployment": AZURE_OPENAI_EMB_DEPLOYMENT,
        "azure_emb_model":      AZURE_OPENAI_EMB_MODEL,
        # Anthropic
        "anthropic_api_key": ANTHROPIC_API_KEY,
        "anthropic_model":   ANTHROPIC_MODEL,
        # OpenAI direct
        "openai_api_key":         OPENAI_API_KEY,
        "openai_model":           OPENAI_MODEL,
        "openai_embedding_model": OPENAI_EMBEDDING_MODEL,
        # Langfuse
        "langfuse_public_key": LANGFUSE_PUBLIC_KEY,
        "langfuse_secret_key": LANGFUSE_SECRET_KEY,
        "langfuse_host":       LANGFUSE_HOST,
        # MCP
        "mcp_server_url": MCP_SERVER_URL,
        "hf_token":       HF_TOKEN,
        # Handoff / SMTP
        "smtp_host":         SMTP_HOST,
        "smtp_port":         SMTP_PORT,
        "smtp_username":     SMTP_USERNAME,
        "smtp_password":     SMTP_PASSWORD,
        "application_email": APPLICATION_EMAIL,
        "support_email":     SUPPORT_EMAIL,
    }

    # Validate required credentials per provider
    if LLM_PROVIDER == "anthropic":
        if not ANTHROPIC_API_KEY:
            raise ValueError("LLM_PROVIDER=anthropic but ANTHROPIC_API_KEY is not set")
    elif LLM_PROVIDER == "openai":
        if not OPENAI_API_KEY:
            raise ValueError("LLM_PROVIDER=openai but OPENAI_API_KEY is not set")
    else:  # azure (default)
        missing = [k for k, v in {
            "AZURE_OPENAI_API_KEY":              AZURE_OPENAI_API_KEY,
            "AZURE_OPENAI_ENDPOINT":             AZURE_OPENAI_ENDPOINT,
            "AZURE_OPENAI_LLM_DEPLOYMENT":       AZURE_OPENAI_LLM_DEPLOYMENT,
            "AZURE_OPENAI_EMBEDDING_DEPLOYMENT": AZURE_OPENAI_EMB_DEPLOYMENT,
        }.items() if not v]
        if missing:
            raise ValueError(f"LLM_PROVIDER=azure but missing: {missing}")

    logger.info(f"Configuration loaded | LLM provider: {LLM_PROVIDER}")
    logger.info(f"  DB       : {DB_HOST}:{DB_PORT}/{DB_NAME}")
    logger.info(f"  Langfuse : {'enabled' if LANGFUSE_PUBLIC_KEY else 'disabled'}")
    logger.info(f"  MCP      : {MCP_SERVER_URL}")

    return config