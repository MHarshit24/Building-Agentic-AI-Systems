"""
Main Entry Point
Starts the FastAPI application server.
"""

import os
import sys
import uvicorn
import logging
from pathlib import Path
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Dual .env loading
# ---------------------------------------------------------------------------
# This file lives at: <project_root>/main.py  -> parents[0] = project root
#                                              -> parents[3] = Building_Agentic_AI_Systems (root)
# ---------------------------------------------------------------------------
def _load_env():
    """Load root .env first for secrets, then project .env with override."""
    if "pytest" in sys.modules:
        return

    # Root .env (Building_Agentic_AI_Systems/.env)
    # main.py -> parents[0] = project root -> parents[2] = root
    base_dir = Path(__file__).resolve().parents[2]
    base_env_path = base_dir / ".env"

    if base_env_path.exists():
        load_dotenv(dotenv_path=base_env_path)
    else:
        load_dotenv()

    # Preserve secrets before project .env overrides them
    db_password = os.getenv("DB_PASSWORD")
    azure_api_key = os.getenv("AZURE_OPENAI_API_KEY")
    azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    llama_cloud_api_key = os.getenv("LLAMA_CLOUD_API_KEY")
    langfuse_secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    langfuse_public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    langfuse_host = os.getenv("LANGFUSE_HOST")
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = os.getenv("SMTP_PORT")
    smtp_username = os.getenv("SMTP_USERNAME")
    smtp_password = os.getenv("SMTP_PASSWORD")
    application_email = os.getenv("APPLICATION_EMAIL")
    support_email = os.getenv("SUPPORT_EMAIL")

    # Project .env (s10 project root/.env)
    # main.py -> parents[0] = project root
    proj_dir = Path(__file__).resolve().parents[0]
    proj_env_path = proj_dir / ".env"

    if proj_env_path.exists():
        load_dotenv(dotenv_path=proj_env_path, override=True)
    else:
        load_dotenv()

    # Restore secrets so project .env cannot overwrite them
    if db_password:
        os.environ["DB_PASSWORD"] = db_password
    if azure_api_key:
        os.environ["AZURE_OPENAI_API_KEY"] = azure_api_key
    if azure_endpoint:
        os.environ["AZURE_OPENAI_ENDPOINT"] = azure_endpoint
    if llama_cloud_api_key:
        os.environ["LLAMA_CLOUD_API_KEY"] = llama_cloud_api_key
    if langfuse_secret_key:
        os.environ["LANGFUSE_SECRET_KEY"] = langfuse_secret_key
    if langfuse_public_key:
        os.environ["LANGFUSE_PUBLIC_KEY"] = langfuse_public_key
    if langfuse_host:
        os.environ["LANGFUSE_HOST"] = langfuse_host
    if smtp_host:
        os.environ["SMTP_HOST"] = smtp_host
    if smtp_port:
        os.environ["SMTP_PORT"] = smtp_port
    if smtp_username:
        os.environ["SMTP_USERNAME"] = smtp_username
    if smtp_password:
        os.environ["SMTP_PASSWORD"] = smtp_password
    if application_email:
        os.environ["APPLICATION_EMAIL"] = application_email
    if support_email:
        os.environ["SUPPORT_EMAIL"] = support_email

    # Remove conflicting PostgreSQL variables that may come from root .env
    conflicting_pg_vars = [
        "DATABASE_URL", "POSTGRES_URL", "PGHOST", "PGPORT",
        "PGUSER", "PGPASSWORD", "PGDATABASE",
    ]
    for var in conflicting_pg_vars:
        os.environ.pop(var, None)


_load_env()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Start the FastAPI application server."""
    # Get configuration from environment variables
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))
    reload = os.getenv("API_RELOAD", "false").lower() == "true"
    log_level = os.getenv("API_LOG_LEVEL", "info")
    
    logger.info("Evaluated RAG Pipeline with Langfuse and Human Handoff"
)
    logger.info(f"Configuration: host={host}, port={port}, reload={reload}")
    
    uvicorn.run(
        "main.app:app",
        host=host,
        port=port,
        reload=reload,
        log_level=log_level
    )


if __name__ == "__main__":
    main()