"""Responsible for the application entry point and startup wiring."""

import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routers import health, plans
from app.config import get_settings
from app.orchestrator.checkpointer import get_checkpointer
from app.orchestrator.graph_builder import PlanningOrchestrator

_ERROR_CODES_BY_STATUS = {
    404: "NOT_FOUND",
    422: "VALIDATION_ERROR",
    502: "UPSTREAM_ERROR",
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # The checkpointer owns a single open SQLite connection for the app's
    # whole lifetime — opened here once rather than per-request.
    async with get_checkpointer() as checkpointer:
        app.state.orchestrator = PlanningOrchestrator(checkpointer=checkpointer)
        yield


app = FastAPI(title="Autonomous Event Planning Team", lifespan=lifespan)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """Stamps every request with an ID so the same value can appear in both
    the success and error envelope shapes returned below."""
    request.state.request_id = str(uuid.uuid4())
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    return response


# Registered after request_id_middleware so it wraps as the outermost layer
# (Starlette makes the most-recently-added middleware outermost) — CORS
# headers must be present on every response, including error responses, for
# a cross-origin frontend (e.g. Vercel) to read them at all.
_cors_origins = get_settings().cors_allowed_origins.strip()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if _cors_origins == "*" else [o.strip() for o in _cors_origins.split(",") if o.strip()],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _envelope(request: Request, status_code: int, message) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "data": None,
            "error": {
                "code": _ERROR_CODES_BY_STATUS.get(status_code, "HTTP_ERROR"),
                "message": message,
            },
            "request_id": getattr(request.state, "request_id", str(uuid.uuid4())),
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return _envelope(request, exc.status_code, exc.detail)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    message = "; ".join(
        f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}" for error in exc.errors()
    )
    return _envelope(request, 422, message)


app.include_router(health.router)
app.include_router(plans.router)
