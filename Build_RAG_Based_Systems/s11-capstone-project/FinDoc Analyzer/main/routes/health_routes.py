"""
FinDoc Analyzer — GET /api/v1/health
System health and observability endpoint.
Dual .env loader: root .env (secrets) + project .env (config).
health_routes.py: main/routes/health_routes.py
  parents[5] = Building_Agentic_AI_Systems  -> root .env
  parents[2] = FinDoc Analyzer              -> project .env

Uses psycopg2 keyword arguments (not connection strings) for DB check
so special characters in DB_PASSWORD are handled correctly without quote_plus.
"""

import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv
from fastapi import APIRouter, status
from main.models import HealthResponse, ComponentStatus

router = APIRouter()
logger = logging.getLogger(__name__)


def _load_env():
    if "pytest" in sys.modules:
        return
    base_dir = Path(__file__).resolve().parents[5]
    base_env_path = base_dir / ".env"
    if base_env_path.exists():
        load_dotenv(dotenv_path=base_env_path)
    else:
        load_dotenv()
        logger.warning(f"Root .env not found at {base_env_path}")
    _preserved = {
        "DB_PASSWORD":           os.getenv("DB_PASSWORD"),
        "AZURE_OPENAI_API_KEY":  os.getenv("AZURE_OPENAI_API_KEY"),
        "AZURE_OPENAI_ENDPOINT": os.getenv("AZURE_OPENAI_ENDPOINT"),
        "LANGFUSE_PUBLIC_KEY":   os.getenv("LANGFUSE_PUBLIC_KEY"),
        "LANGFUSE_SECRET_KEY":   os.getenv("LANGFUSE_SECRET_KEY"),
        "LANGFUSE_HOST":         os.getenv("LANGFUSE_HOST"),
    }
    proj_dir = Path(__file__).resolve().parents[2]
    proj_env_path = proj_dir / ".env"
    if proj_env_path.exists():
        load_dotenv(dotenv_path=proj_env_path, override=True)
    else:
        load_dotenv()
        logger.warning(f"Project .env not found at {proj_env_path}")
    for key, val in _preserved.items():
        if val:
            os.environ[key] = val
    for var in ["DATABASE_URL", "POSTGRES_URL", "PGHOST", "PGPORT",
                "PGUSER", "PGPASSWORD", "PGDATABASE"]:
        os.environ.pop(var, None)


_load_env()


def _check_postgres() -> ComponentStatus:
    """
    Check PostgreSQL + pgvector using keyword args — NOT a connection string.
    This avoids quote_plus issues with special characters in DB_PASSWORD.
    """
    try:
        import psycopg2
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST",     "localhost"),
            port=os.getenv("DB_PORT",     "5432"),
            dbname=os.getenv("DB_NAME",   "findoc_db"),
            user=os.getenv("DB_USER",     "postgres"),
            password=os.getenv("DB_PASSWORD", ""),
        )
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT version();")
                version = cur.fetchone()[0].split(",")[0]
                cur.execute("SELECT 1 FROM pg_extension WHERE extname = 'vector';")
                pgv = "pgvector ✓" if cur.fetchone() else "pgvector NOT found ✗"
        conn.close()
        return ComponentStatus(status="ok", detail=f"{version} | {pgv}")
    except Exception as e:
        return ComponentStatus(status="error", detail=str(e))


def _check_llm_provider() -> ComponentStatus:
    provider = os.getenv("LLM_PROVIDER", "azure").lower()

    if provider == "anthropic":
        key   = os.getenv("ANTHROPIC_API_KEY")
        model = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
        if key:
            return ComponentStatus(status="ok", detail=f"provider=anthropic model={model}")
        return ComponentStatus(status="error", detail="ANTHROPIC_API_KEY not set")

    elif provider == "openai":
        key   = os.getenv("OPENAI_API_KEY")
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        if key:
            return ComponentStatus(status="ok", detail=f"provider=openai model={model}")
        return ComponentStatus(status="error", detail="OPENAI_API_KEY not set")

    else:  # azure (default)
        api_key  = os.getenv("AZURE_OPENAI_API_KEY")
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        llm_dep  = os.getenv("AZURE_OPENAI_LLM_DEPLOYMENT")
        emb_dep  = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")
        if all([api_key, endpoint, llm_dep, emb_dep]):
            return ComponentStatus(
                status="ok",
                detail=f"provider=azure llm={llm_dep} emb={emb_dep}"
            )
        missing = [k for k, v in {
            "API_KEY":  api_key,
            "ENDPOINT": endpoint,
            "LLM":      llm_dep,
            "EMB":      emb_dep,
        }.items() if not v]
        return ComponentStatus(status="error", detail=f"Missing: {missing}")


def _check_rag_service() -> ComponentStatus:
    try:
        from main.services.rag_service import get_index
        get_index()
        provider = os.getenv("LLM_PROVIDER", "azure")
        return ComponentStatus(
            status="ok",
            detail=f"LlamaIndex index loaded | provider={provider}"
        )
    except Exception as e:
        return ComponentStatus(status="error", detail=str(e))


def _check_guardrails_ai() -> ComponentStatus:
    try:
        from guardrails import Guard
        return ComponentStatus(status="ok", detail="guardrails-ai SDK installed ✓")
    except ImportError:
        return ComponentStatus(
            status="disabled",
            detail=(
                "Not installed — using custom validators (fully functional). "
                "Install: pip install guardrails-ai"
            )
        )


def _check_ragas() -> ComponentStatus:
    try:
        import ragas
        import datasets
        return ComponentStatus(status="ok", detail=f"ragas {ragas.__version__} installed ✓")
    except ImportError as e:
        return ComponentStatus(
            status="disabled",
            detail=f"Not installed ({e}). Install: pip install ragas datasets"
        )


def _check_presidio() -> ComponentStatus:
    try:
        from presidio_analyzer import AnalyzerEngine
        return ComponentStatus(status="ok", detail="presidio-analyzer installed ✓")
    except ImportError:
        return ComponentStatus(
            status="disabled",
            detail=(
                "Not installed. "
                "Install: pip install presidio-analyzer presidio-anonymizer"
            )
        )


def _check_pymupdf() -> ComponentStatus:
    try:
        import fitz
        return ComponentStatus(
            status="ok",
            detail=f"pymupdf {fitz.__version__} ✓ — PDF table extraction active"
        )
    except ImportError:
        return ComponentStatus(
            status="disabled",
            detail="Not installed. Install: pip install pymupdf"
        )


def _check_langfuse() -> ComponentStatus:
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    if public_key and secret_key:
        host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
        return ComponentStatus(status="ok", detail=f"host={host}")
    return ComponentStatus(
        status="disabled",
        detail="LANGFUSE_PUBLIC_KEY / SECRET_KEY not set"
    )


def _check_mcp() -> ComponentStatus:
    hf_token = os.getenv("HF_TOKEN")
    mcp_url  = os.getenv("MCP_SERVER_URL")
    if hf_token and mcp_url:
        return ComponentStatus(status="ok", detail=f"url={mcp_url}")
    missing = [k for k, v in {
        "HF_TOKEN":      hf_token,
        "MCP_SERVER_URL": mcp_url,
    }.items() if not v]
    return ComponentStatus(status="disabled", detail=f"Missing: {missing}")


def _check_yfinance() -> ComponentStatus:
    try:
        import yfinance
        return ComponentStatus(status="ok", detail=f"yfinance {yfinance.__version__} ✓")
    except ImportError:
        return ComponentStatus(
            status="disabled",
            detail="Not installed. Install: pip install yfinance"
        )


def _check_smtp() -> ComponentStatus:
    required = {
        "SMTP_HOST":     os.getenv("SMTP_HOST"),
        "SMTP_USERNAME": os.getenv("SMTP_USERNAME"),
        "SMTP_PASSWORD": os.getenv("SMTP_PASSWORD"),
        "SUPPORT_EMAIL": os.getenv("SUPPORT_EMAIL"),
    }
    missing = [k for k, v in required.items() if not v]
    if not missing:
        return ComponentStatus(
            status="ok",
            detail=f"host={os.getenv('SMTP_HOST')}"
        )
    return ComponentStatus(
        status="disabled",
        detail=f"Missing: {missing} — handoff email notifications disabled"
    )


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="System health check",
    description=(
        "Full component health: DB + pgvector, LLM provider, RAG service, "
        "guardrails-ai, RAGAS, presidio, pymupdf, yfinance, Langfuse, MCP, SMTP. "
        "Critical components: postgresql + llm_provider. "
        "All others are optional enhancements."
    ),
)
async def health_check():
    components = {
        "postgresql":    _check_postgres(),
        "llm_provider":  _check_llm_provider(),
        "rag_service":   _check_rag_service(),
        "guardrails_ai": _check_guardrails_ai(),
        "ragas":         _check_ragas(),
        "presidio_pii":  _check_presidio(),
        "pymupdf_tables": _check_pymupdf(),
        "yfinance":      _check_yfinance(),
        "langfuse":      _check_langfuse(),
        "mcp":           _check_mcp(),
        "smtp_handoff":  _check_smtp(),
    }

    critical         = ["postgresql", "llm_provider"]
    critical_statuses = [components[c].status for c in critical]

    if all(s == "ok" for s in critical_statuses):
        overall = "healthy"
    elif any(s == "error" for s in critical_statuses):
        overall = "unhealthy"
    else:
        overall = "degraded"

    logger.info(f"Health check: {overall}")
    return HealthResponse(
        status=overall,
        service="FinDoc Analyzer",
        version="1.0.0",
        components=components,
    )