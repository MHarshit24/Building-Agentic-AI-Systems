"""
FastAPI HTTP application — Vercel serverless entry point.
----------------------------------------------------------
Exposes the Job Placement Agent over standard HTTP/JSON so it can be hosted
on Vercel's serverless platform.  All business logic lives in the agent/,
auth/, and tools/ modules — this file is purely the transport layer.

The gRPC servers (grpc_server.py, grpc_web_server.py) are kept for local /
Streamlit use and are NOT loaded here; they require grpcio which is not
installed in the Vercel runtime.

Endpoints
~~~~~~~~~
  GET  /api/health
  POST /api/auth/token
  POST /api/chat/public
  POST /api/session
  POST /api/chat              🔒  (sync)
  POST /api/chat/async        🔒  (async via .ainvoke — Sprint 2 LO3)
  POST /api/chat/stream           (SSE token stream — Sprint 7)
  POST /api/chat/route            (LCEL router chain — Sprint 5/6)
  POST /api/jobs/search       🔒
  POST /api/resume/analyze    🔒
  POST /api/cover-letter/gen  🔒
  DELETE /api/chat/{id}       🔒
  GET  /api/sessions          🔒

All JSON responses use the ApiResponse envelope (models/responses.py).
"""

import asyncio
import json
import uuid
import logging

from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

import os
from dotenv import load_dotenv
load_dotenv()

# Strip UTF-8 BOM (\ufeff) and stray \r\n that PowerShell piping injects into
# env var values when pushing via `vercel env add` on Windows.
for _k, _v in list(os.environ.items()):
    _c = _v.strip().lstrip('\ufeff')
    if _c != _v:
        os.environ[_k] = _c

from models.schemas import (
    TokenRequest, TokenResponse,
    ChatRequest, ChatResponse,
    JobSearchRequest, JobSearchResponse,
    ResumeAnalysisRequest, ResumeAnalysisResponse,
    CoverLetterRequest, CoverLetterResponse,
    HealthResponse, SessionCreateResponse, SessionClearResponse, SessionsListResponse,
)
from models.responses import ApiResponse
from auth.auth0 import get_current_user, fetch_token, _get_jwks
from agent.job_agent import (
    run_agent,
    run_agent_async,
    stream_agent,
    clear_session,
    list_sessions,
    get_session_history,
)
from agent.router import route_query
from agent.tools.job_search import fetch_job_listings
from agent.tools.resume_analyzer import analyze_resume_core
from agent.tools.cover_letter import generate_cover_letter_core
from exceptions import AppError
from observability.langfuse_config import flush_langfuse, get_langfuse_handler

logger = logging.getLogger(__name__)

# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Job Placement Agent API",
    version="1.0.0",
    description="AI-powered job placement assistant.",
    docs_url="/docs",
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _req_id(request: Request) -> str:
    return request.headers.get("x-request-id", str(uuid.uuid4()))


# ── Global exception handler ──────────────────────────────────────────────────

@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    logger.warning("AppError [%s]: %s", exc.error_code, exc)
    return JSONResponse(
        status_code=exc.http_status,
        content=ApiResponse.fail(
            code=exc.error_code,
            message=str(exc),
            request_id=_req_id(request),
        ).model_dump(),
    )


# ── Startup / Shutdown ────────────────────────────────────────────────────────

@app.on_event("startup")
async def on_startup() -> None:
    """Pre-warm cached singletons in the background so the first request is fast."""
    async def _prewarm():
        try:
            await asyncio.to_thread(_get_jwks)
            logger.info("Pre-warm: Auth0 JWKS loaded.")
        except Exception as exc:
            logger.warning("Pre-warm: JWKS fetch skipped (%s)", exc)
        try:
            from agent.job_agent import _get_agent
            await asyncio.to_thread(_get_agent)
            logger.info("Pre-warm: Agent executor ready.")
        except Exception as exc:
            logger.warning("Pre-warm: Agent build skipped (%s)", exc)
    asyncio.create_task(_prewarm())


@app.on_event("shutdown")
async def on_shutdown() -> None:
    flush_langfuse()


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/api/health", response_model=ApiResponse[HealthResponse])
async def health_check(request: Request):
    return ApiResponse.ok(
        data=HealthResponse(
            status="healthy",
            version="1.0.0",
            message="Job Placement Agent API is running.",
        ),
        request_id=_req_id(request),
    )


@app.post("/api/auth/token", response_model=ApiResponse[TokenResponse])
async def get_token(body: TokenRequest, request: Request):
    token_data = await asyncio.to_thread(fetch_token, body.username, body.password)
    return ApiResponse.ok(
        data=TokenResponse(**token_data),
        request_id=_req_id(request),
    )


@app.post("/api/chat/public", response_model=ApiResponse[ChatResponse])
async def chat_public(body: ChatRequest, request: Request):
    session_id = body.session_id or str(uuid.uuid4())
    response = await run_agent_async(user_message=body.message, session_id=session_id)
    return ApiResponse.ok(
        data=ChatResponse(response=response, session_id=session_id),
        request_id=_req_id(request),
    )


@app.post("/api/session", response_model=ApiResponse[SessionCreateResponse])
async def create_session(request: Request):
    session_id = str(uuid.uuid4())
    get_session_history(session_id)
    logger.info("Session created: %s", session_id)
    return ApiResponse.ok(
        data=SessionCreateResponse(session_id=session_id),
        request_id=_req_id(request),
    )


@app.post("/api/chat", response_model=ApiResponse[ChatResponse])
async def chat(
    body: ChatRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    session_id = body.session_id or str(uuid.uuid4())
    user_id    = current_user.get("sub", "unknown")
    response   = await run_agent_async(
        user_message=body.message,
        session_id=session_id,
        user_id=user_id,
    )
    return ApiResponse.ok(
        data=ChatResponse(response=response, session_id=session_id),
        request_id=_req_id(request),
    )


@app.post("/api/chat/async", response_model=ApiResponse[ChatResponse])
async def chat_async(
    body: ChatRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """
    Async chat endpoint — uses ``.ainvoke()`` so the event loop is never
    blocked while the LLM generates a response.

    Sprint 2, LO3: Execute Asynchronous LLM Calls.
    """
    session_id = body.session_id or str(uuid.uuid4())
    user_id    = current_user.get("sub", "unknown")
    response   = await run_agent_async(
        user_message=body.message,
        session_id=session_id,
        user_id=user_id,
    )
    return ApiResponse.ok(
        data=ChatResponse(response=response, session_id=session_id),
        request_id=_req_id(request),
    )


@app.post("/api/chat/stream")
async def stream_chat(body: ChatRequest, request: Request):
    """
    Server-Sent Events (SSE) streaming endpoint.

    Streams the agent's response token-by-token so the browser can render
    text progressively without waiting for the full reply.

    Sprint 7: Streaming AI Responses with SSE + FastAPI StreamingResponse.

    SSE format per event:
        data: {"token": "<text>", "session_id": "<id>"}\\n\\n
    Final event:
        data: {"done": true, "session_id": "<id>"}\\n\\n
    Error event:
        data: {"error": "<code>", "message": "<detail>"}\\n\\n
    """
    session_id = body.session_id or str(uuid.uuid4())

    async def event_generator():
        try:
            async for token in stream_agent(
                user_message=body.message,
                session_id=session_id,
            ):
                payload = json.dumps({"token": token, "session_id": session_id})
                yield f"data: {payload}\n\n"

            # Signal end-of-stream to the client
            yield f"data: {json.dumps({'done': True, 'session_id': session_id})}\n\n"

        except Exception as exc:
            logger.error("SSE stream error (session=%s): %s", session_id, exc)
            error_payload = json.dumps({"error": "STREAM_ERROR", "message": str(exc)})
            yield f"data: {error_payload}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            # Disable proxy buffering so tokens reach the browser immediately
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/chat/route", response_model=ApiResponse[ChatResponse])
async def chat_route(body: ChatRequest, request: Request):
    """
    LCEL intent-router endpoint — classifies the user's message then dispatches
    it to a specialist chain (job search / resume / cover letter / general).

    Sprint 5/6: Router Chains for Conditional Workflows.

    Returns the specialist chain's response together with the detected intent
    label embedded in the session_id field for transparency.
    """
    session_id = body.session_id or str(uuid.uuid4())
    intent, response = route_query(body.message)
    logger.info("Router endpoint — intent='%s', session=%s", intent, session_id)
    return ApiResponse.ok(
        data=ChatResponse(response=f"[{intent}] {response}", session_id=session_id),
        request_id=_req_id(request),
    )


@app.post("/api/jobs/search", response_model=ApiResponse[JobSearchResponse])
async def search_jobs(
    body: JobSearchRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    session_id = body.session_id or "direct"
    results    = await asyncio.to_thread(fetch_job_listings, body.query, body.location or "")
    return ApiResponse.ok(
        data=JobSearchResponse(results=results, session_id=session_id),
        request_id=_req_id(request),
    )


@app.post("/api/resume/analyze", response_model=ApiResponse[ResumeAnalysisResponse])
async def analyze_resume(
    body: ResumeAnalysisRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    session_id       = body.session_id or "direct"
    langfuse_handler = get_langfuse_handler(session_id=session_id, user_id=current_user.get("sub"))
    callbacks        = [langfuse_handler] if langfuse_handler else []
    try:
        analysis = await asyncio.to_thread(
            analyze_resume_core, body.resume_text, body.job_description or "", callbacks
        )
    finally:
        if langfuse_handler:
            await asyncio.to_thread(langfuse_handler.flush)
    return ApiResponse.ok(
        data=ResumeAnalysisResponse(analysis=analysis, session_id=session_id),
        request_id=_req_id(request),
    )


@app.post("/api/cover-letter/gen", response_model=ApiResponse[CoverLetterResponse])
async def generate_cover_letter(
    body: CoverLetterRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    session_id       = body.session_id or "direct"
    langfuse_handler = get_langfuse_handler(session_id=session_id, user_id=current_user.get("sub"))
    callbacks        = [langfuse_handler] if langfuse_handler else []
    try:
        cover_letter = await asyncio.to_thread(
            generate_cover_letter_core,
            body.resume_text,
            body.job_title,
            body.company_name,
            body.job_description,
            body.user_name or "Applicant",
            callbacks,
        )
    finally:
        if langfuse_handler:
            await asyncio.to_thread(langfuse_handler.flush)
    return ApiResponse.ok(
        data=CoverLetterResponse(cover_letter=cover_letter, session_id=session_id),
        request_id=_req_id(request),
    )


@app.delete("/api/chat/{session_id}", response_model=ApiResponse[SessionClearResponse])
async def clear_chat_session(
    session_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    clear_session(session_id)
    return ApiResponse.ok(
        data=SessionClearResponse(
            message="Session cleared successfully.",
            session_id=session_id,
        ),
        request_id=_req_id(request),
    )


@app.get("/api/sessions", response_model=ApiResponse[SessionsListResponse])
async def get_sessions(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    return ApiResponse.ok(
        data=SessionsListResponse(sessions=list_sessions()),
        request_id=_req_id(request),
    )
