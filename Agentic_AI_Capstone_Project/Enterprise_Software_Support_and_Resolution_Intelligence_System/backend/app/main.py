import asyncio
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.routes_health import router as health_router
from app.api.routes_auth import router as auth_router
from app.api.routes_chat import router as chat_router
from app.api.routes_conversations import router as conversations_router
from app.api.routes_customers import router as customers_router
from app.api.routes_documents import router as documents_router
from app.api.routes_ingest import router as ingest_router
from app.api.routes_metrics import router as metrics_router
from app.api.routes_users import router as users_router
from app.config import get_settings
from app.llm.provider_resolution import resolve_llm_provider
from app.logging.structured_logger import configure_logging
from app.middleware.rate_limit import limiter
from app.middleware.request_context import request_context_middleware
from app.orchestration.checkpointer import build_checkpointer
from app.orchestration.graph import build_graph

# §40's checkpointer (psycopg's async driver) cannot run under Windows'
# default ProactorEventLoop — confirmed empirically (psycopg.InterfaceError
# at connect time). Switching to SelectorEventLoopPolicy is safe here: the
# MCP notification client's own stdio subprocess spawning (Stage 7,
# app/mcp_client/notification_client.py) already has a documented,
# built-in fallback for exactly this case — mcp.os.win32.utilities.
# create_windows_process() catches subprocess creation's NotImplementedError
# under SelectorEventLoop and transparently falls back to sync
# subprocess.Popen + thread-bridged I/O. Must be set before any event loop
# is created, hence at module import time.
#
# This alone is NOT sufficient for the real uvicorn dev server, though —
# confirmed by reading uvicorn's source: its own "asyncio" loop factory
# (uvicorn.loops.asyncio.asyncio_loop_factory) hard-codes
# asyncio.ProactorEventLoop on win32 and constructs the loop via
# asyncio.run(..., loop_factory=...), which bypasses this policy entirely
# (Python 3.12+ behavior). Start the dev server with app/win_loop.py's
# factory explicitly: `uvicorn app.main:app --loop app.win_loop:loop_factory`.
# This policy line still matters for every OTHER entry point that doesn't
# go through uvicorn's Config (pytest, plain scripts importing app.main).
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Structured JSON logging (§34) — configured once, before the app starts
# handling requests, so every logging.getLogger(__name__) call site in
# the codebase emits structured output from the first request onward.
configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """§40: builds the real Postgres-backed checkpointer and the app's
    real request-serving graph at startup, stored on app.state.graph.
    graph.py's own module-level `graph = build_graph()` singleton (no
    checkpointer) is untouched and still what every test imports directly
    — this app.state.graph is only reachable through a real request, via
    routes_chat.py's request.app.state.graph lookup. Tests that build the
    ASGI app without running this lifespan (this project's own test
    client uses ASGITransport, which does not trigger it) simply never
    see app.state.graph set, and routes_chat.py falls back to the
    module-level graph in that case.

    resolve_llm_provider() (provider_fallback_plan.md) runs first and
    mutates settings.llm_provider in place on the cached Settings
    instance — same technique app/config.py's own
    _apply_calibrated_thresholds() already uses — so get_llm_client()
    (app/llm/azure_client.py) picks up the resolved provider ("azure" or
    "groq") for every call made afterward, with no other code path aware
    this happened. Raises and refuses to start if neither the Azure tier
    nor the full Groq+Gemini fallback tier is reachable — never silently
    falls back to MockLLMClient, a test-only concept."""
    settings = get_settings()
    settings.llm_provider = await resolve_llm_provider(settings)
    async with build_checkpointer(settings.checkpointer_conn_string) as checkpointer:
        app.state.graph = build_graph(checkpointer=checkpointer)
        yield


app = FastAPI(
    title="Enterprise Software Support & Resolution Intelligence System",
    lifespan=lifespan,
)

# CORS — added immediately after app creation (FastAPI's own documented
# convention) so preflight OPTIONS requests are answered by this middleware
# directly and never reach rate-limited/authenticated route handlers.
# Allowed origins are env-driven (settings.cors_allowed_origins) so the
# Vercel deployment URL can be added later without a code change.
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# SlowAPI integration
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# request_id generation + request start/end logging, automatic for every
# request (§34) — no call site threads request_id through manually.
app.middleware("http")(request_context_middleware)

# Register health routes
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(conversations_router)
app.include_router(customers_router)
app.include_router(documents_router)
app.include_router(ingest_router)
app.include_router(metrics_router)
app.include_router(users_router)