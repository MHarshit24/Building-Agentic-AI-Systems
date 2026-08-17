from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI


def _load_env():
    """
    Two-step env loading pattern:
    - Root .env loaded first for secrets: AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, DB_PASSWORD
    - Project .env loaded second with override=True for deployment names, DB config, etc.
    - Secrets preserved so project .env can never overwrite them.
    - All DB connection vars from root .env are wiped before project .env loads,
      so previous-assignment Azure PostgreSQL values cannot leak in.
    """
    if "pytest" in sys.modules:
        return

    # This file: <project>/main/app.py -> parents[3] = repo root
    base_env_path = Path(__file__).resolve().parents[3] / ".env"
    if base_env_path.exists():
        load_dotenv(dotenv_path=base_env_path)
    else:
        load_dotenv()

    # Preserve secrets before project .env load
    db_password = os.getenv("DB_PASSWORD")
    azure_api_key = os.getenv("AZURE_OPENAI_API_KEY")
    azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")

    # Wipe ALL DB connection vars from root .env before loading project .env
    # so previous-assignment Azure PostgreSQL values cannot leak into this project
    for var in [
        "DATABASE_URL", "POSTGRES_URL",
        "PGHOST", "PGPORT", "PGUSER", "PGPASSWORD", "PGDATABASE",
        "DB_USER", "DB_HOST", "DB_NAME", "DB_PORT", "DB_TABLE_NAME",
    ]:
        os.environ.pop(var, None)

    # This file: <project>/main/app.py -> parents[1] = project root
    proj_env_path = Path(__file__).resolve().parents[1] / ".env"
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


# Load env as early as possible
_load_env()

# Simple logging setup (can be controlled via LOG_LEVEL env var)
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

# Configure LlamaIndex globally for this app
from llama_index.core import Settings
from llama_index.llms.azure_openai import AzureOpenAI
from llama_index.embeddings.azure_openai import AzureOpenAIEmbedding

_llm_deployment = os.getenv("AZURE_OPENAI_LLM_DEPLOYMENT")
_embed_deployment = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")
_api_key = os.getenv("AZURE_OPENAI_API_KEY")
_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
_api_version = os.getenv("AZURE_OPENAI_API_VERSION")

# Configure models only when env vars are present (so the app can import without secrets)
if _llm_deployment and _api_key and _endpoint and _api_version:
    Settings.llm = AzureOpenAI(
        model="gpt-4o-mini",
        deployment_name=_llm_deployment,
        api_key=_api_key,
        azure_endpoint=_endpoint,
        api_version=_api_version,
    )
else:
    print("⚠ Azure OpenAI LLM not configured (missing AZURE_OPENAI_* env vars)")

if _embed_deployment and _api_key and _endpoint and _api_version:
    Settings.embed_model = AzureOpenAIEmbedding(
        model="text-embedding-3-small",
        deployment_name=_embed_deployment,
        api_key=_api_key,
        azure_endpoint=_endpoint,
        api_version=_api_version,
    )
else:
    print("⚠ Azure OpenAI embedding not configured (missing AZURE_OPENAI_* env vars)")

# Global guardrails validator (reused across requests)
from main.service.guardrails import GuardrailsValidator

_global_validator = GuardrailsValidator()
print("✓ Guardrails validator initialized")

# Import routers after globals are configured
from main.routes import ingestion_router, query_router

app = FastAPI(
    title="Investment Advisor RAG",
    description="Fusion Retrieval (BM25+Vector+RRF) + Guardrails (PII redaction, input blocking, non-toxic/professional responses)",
    version="0.1.0",
    openapi_version="3.0.3"
)

from fastapi.openapi.utils import get_openapi


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    try:
        upload_schema = (
            schema["components"]["schemas"]
            ["Body_upload_api_ingestion_upload_post"]
            ["properties"]["files"]["items"]
        )

        upload_schema.pop("contentMediaType", None)

        upload_schema["format"] = "binary"

    except Exception as e:
        print(f"OpenAPI patch skipped: {e}")

    app.openapi_schema = schema
    return schema


app.openapi = custom_openapi

app.include_router(ingestion_router)
app.include_router(query_router)


def get_validator() -> GuardrailsValidator:
    return _global_validator


@app.get("/")
async def root():
    return {
        "message": "Investment Advisor RAG",
        "endpoints": {
            "ingest_upload": "/api/ingestion/upload",
            "query": "/api/query",
            "docs": "/docs",
        },
    }