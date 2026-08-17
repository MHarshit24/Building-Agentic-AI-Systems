"""
FinDoc Analyzer — FastAPI application.
Two main endpoints: POST /api/v1/ingest, POST /api/v1/query
Plus:               GET  /api/v1/health

Lifespan includes DB preflight check so startup fails fast
if PostgreSQL or pgvector is not reachable.
"""

import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from main.config import setup_logging
from main.routes.ingest_routes import router as ingest_router
from main.routes.query_routes  import router as query_router
from main.routes.health_routes import router as health_router
from main.services.rag_service import initialize_services

setup_logging()
logger = logging.getLogger(__name__)


def _preflight_db_check():
    """
    Verify PostgreSQL + pgvector are reachable before serving requests.
    Logs a warning but does NOT crash the server — services initialize
    lazily on first request if preflight fails.
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
                cur.execute("SELECT 1 FROM pg_extension WHERE extname = 'vector';")
                pgv = cur.fetchone()
                if pgv:
                    logger.info("DB preflight: PostgreSQL ✓ | pgvector ✓")
                else:
                    logger.warning("DB preflight: PostgreSQL ✓ | pgvector NOT FOUND — run: CREATE EXTENSION vector;")
        conn.close()
    except Exception as e:
        logger.warning(f"DB preflight failed (will retry on first request): {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: DB preflight + RAG service init. Shutdown: log."""
    logger.info("=" * 60)
    logger.info("FinDoc Analyzer starting up...")
    logger.info("=" * 60)

    # DB preflight — fast check before heavy model loading
    _preflight_db_check()

    # Initialize RAG services (LLM + embeddings + vector index)
    try:
        initialize_services()
        logger.info("All services initialized successfully")
    except Exception as e:
        logger.error(f"Service initialization warning: {e}")
        logger.info("Services will initialize on first request")

    yield
    logger.info("FinDoc Analyzer shutting down...")


app = FastAPI(
    title="FinDoc Analyzer – Financial Report Intelligence System",
    description=(
        "AI-powered financial document analysis using LlamaIndex RAG, "
        "pgvector, SQL/Hybrid query routing, Guardrails (Presidio PII), "
        "Langfuse evaluation, yfinance MCP integration, and Human Handoff."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Two main endpoints + health ───────────────────────────────────
app.include_router(ingest_router, prefix="/api/v1", tags=["Ingestion"])
app.include_router(query_router,  prefix="/api/v1", tags=["Query"])
app.include_router(health_router, prefix="/api/v1", tags=["Health"])


@app.get("/")
async def root():
    return {
        "message": "FinDoc Analyzer – Financial Report Intelligence System",
        "version": "1.0.0",
        "endpoints": {
            "ingest": "POST /api/v1/ingest",
            "query":  "POST /api/v1/query",
            "health": "GET  /api/v1/health",
            "docs":   "/docs",
        },
    }