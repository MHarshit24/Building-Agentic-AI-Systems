"""
Job Placement Agent — gRPC Server
===================================
Replaces the FastAPI/JSON REST API with a Protocol-Buffer-based gRPC interface.

Every REST endpoint in main.py has a direct 1-to-1 RPC equivalent:

  REST                              gRPC
  ────────────────────────────────  ──────────────────────────
  GET  /api/health                  HealthCheck
  POST /api/auth/token              GetToken
  POST /api/chat/public             ChatPublic
  POST /api/session                 CreateSession
  POST /api/chat              (🔒)  Chat
  POST /api/jobs/search       (🔒)  SearchJobs
  POST /api/resume/analyze    (🔒)  AnalyzeResume
  POST /api/cover-letter/gen  (🔒)  GenerateCoverLetter
  DEL  /api/chat/{id}         (🔒)  ClearSession
  GET  /api/sessions          (🔒)  ListSessions

🔒  Protected RPCs require the call metadata to carry:
      authorization: Bearer <access_token>

    Obtain a token first via GetToken (username + password → Auth0 JWT).

Error mapping (AppError subclass → gRPC StatusCode):
  Auth0CredentialsError  → UNAUTHENTICATED
  Auth0NetworkError      → UNAVAILABLE
  Auth0ConfigError       → INTERNAL
  GeminiRateLimitError   → RESOURCE_EXHAUSTED
  GeminiQuotaExceededError → UNAVAILABLE
  GeminiNetworkError     → UNAVAILABLE
  GeminiConfigError      → INTERNAL
  GeminiInvalidRequestError → INVALID_ARGUMENT
  SerpApiRateLimitError  → RESOURCE_EXHAUSTED
  SerpApiNetworkError    → UNAVAILABLE
  SerpApiConfigError     → INTERNAL
  AgentError / other     → INTERNAL

Usage
-----
Run from src/backend/ after generating the proto stubs:

    python generate_proto.py          # one-time stub generation
    python grpc_server.py             # start gRPC server on :50051

Or import and call serve() programmatically:

    from grpc_server import serve
    serve(host="0.0.0.0", port=50051)
"""
import uuid
import logging
from concurrent import futures
from typing import Optional

import grpc

# Generated protobuf stubs — run generate_proto.py first.
from proto import job_agent_pb2, job_agent_pb2_grpc

from auth.auth0 import verify_token, fetch_token
from agent.job_agent import (
    run_agent,
    clear_session,
    list_sessions,
    get_session_history,
)
from agent.tools.job_search import fetch_job_listings
from agent.tools.resume_analyzer import analyze_resume_core
from agent.tools.cover_letter import generate_cover_letter_core
from exceptions import (
    AppError,
    Auth0CredentialsError,
    Auth0ConfigError,
    Auth0NetworkError,
    GeminiConfigError,
    GeminiRateLimitError,
    GeminiQuotaExceededError,
    GeminiNetworkError,
    GeminiInvalidRequestError,
    SerpApiConfigError,
    SerpApiRateLimitError,
    SerpApiNetworkError,
)

logger = logging.getLogger(__name__)


# ── Error mapping ──────────────────────────────────────────────────────────────

def _map_app_error(exc: AppError) -> tuple[grpc.StatusCode, str]:
    """
    Map a domain AppError to the most appropriate gRPC StatusCode.
    Returns (StatusCode, detail_message).
    """
    if isinstance(exc, Auth0CredentialsError):
        return grpc.StatusCode.UNAUTHENTICATED, str(exc)
    if isinstance(exc, (Auth0NetworkError, GeminiNetworkError, GeminiQuotaExceededError, SerpApiNetworkError)):
        return grpc.StatusCode.UNAVAILABLE, str(exc)
    if isinstance(exc, (Auth0ConfigError, GeminiConfigError, SerpApiConfigError)):
        return grpc.StatusCode.INTERNAL, str(exc)
    if isinstance(exc, (GeminiRateLimitError, SerpApiRateLimitError)):
        return grpc.StatusCode.RESOURCE_EXHAUSTED, str(exc)
    if isinstance(exc, GeminiInvalidRequestError):
        return grpc.StatusCode.INVALID_ARGUMENT, str(exc)
    # AgentError and all other AppError subclasses
    return grpc.StatusCode.INTERNAL, str(exc)


# ── Auth helper ───────────────────────────────────────────────────────────────

def _require_auth(context: grpc.ServicerContext) -> dict:
    """
    Validate the Bearer token from gRPC invocation metadata.

    Expects metadata key ``authorization`` with value ``Bearer <token>``.

    Returns the decoded JWT payload dict on success.
    Calls context.abort() (raising AbortError internally) on failure —
    callers do not need to check the return value for None.
    """
    metadata = dict(context.invocation_metadata())
    auth_header = metadata.get("authorization", "")

    if not auth_header.startswith("Bearer "):
        context.abort(
            grpc.StatusCode.UNAUTHENTICATED,
            "Missing authorization metadata. "
            "Include 'authorization: Bearer <token>' in the gRPC call metadata.",
        )

    token = auth_header[len("Bearer "):]
    try:
        return verify_token(token)
    except AppError as exc:
        code, detail = _map_app_error(exc)
        context.abort(code, detail)

    return {}  # unreachable — context.abort() raises AbortError


# ── Servicer ──────────────────────────────────────────────────────────────────

class JobAgentServicer(job_agent_pb2_grpc.JobAgentServiceServicer):
    """
    gRPC servicer implementing all Job Placement Agent RPCs.

    Public methods (no auth): HealthCheck, GetToken, ChatPublic, CreateSession.
    Protected methods (auth required): all others.
    """

    # ── Public ────────────────────────────────────────────────────────────────

    def HealthCheck(
        self,
        request: job_agent_pb2.HealthRequest,
        context: grpc.ServicerContext,
    ) -> job_agent_pb2.HealthResponse:
        logger.info("gRPC HealthCheck")
        return job_agent_pb2.HealthResponse(
            status="healthy",
            version="1.0.0",
            message="Job Placement Agent gRPC server is running.",
        )

    def GetToken(
        self,
        request: job_agent_pb2.GetTokenRequest,
        context: grpc.ServicerContext,
    ) -> job_agent_pb2.GetTokenResponse:
        if not request.username or not request.password:
            context.abort(
                grpc.StatusCode.INVALID_ARGUMENT,
                "Both 'username' and 'password' are required.",
            )
        try:
            token_data = fetch_token(request.username, request.password)
            return job_agent_pb2.GetTokenResponse(
                access_token=token_data["access_token"],
                token_type=token_data["token_type"],
                expires_in=token_data["expires_in"],
            )
        except AppError as exc:
            code, detail = _map_app_error(exc)
            context.abort(code, detail)

    def ChatPublic(
        self,
        request: job_agent_pb2.ChatRequest,
        context: grpc.ServicerContext,
    ) -> job_agent_pb2.ChatResponse:
        if not request.message:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "'message' is required.")
        session_id = request.session_id or str(uuid.uuid4())
        try:
            response = run_agent(user_message=request.message, session_id=session_id)
            return job_agent_pb2.ChatResponse(response=response, session_id=session_id)
        except AppError as exc:
            code, detail = _map_app_error(exc)
            context.abort(code, detail)

    def CreateSession(
        self,
        request: job_agent_pb2.CreateSessionRequest,
        context: grpc.ServicerContext,
    ) -> job_agent_pb2.CreateSessionResponse:
        session_id = str(uuid.uuid4())
        get_session_history(session_id)  # initialises the in-memory store entry
        logger.info("gRPC CreateSession: %s", session_id)
        return job_agent_pb2.CreateSessionResponse(
            session_id=session_id,
            message="Session created successfully.",
        )

    # ── Protected ─────────────────────────────────────────────────────────────

    def Chat(
        self,
        request: job_agent_pb2.ChatRequest,
        context: grpc.ServicerContext,
    ) -> job_agent_pb2.ChatResponse:
        user = _require_auth(context)
        if not request.message:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "'message' is required.")
        session_id = request.session_id or str(uuid.uuid4())
        user_id    = user.get("sub", "unknown")
        try:
            response = run_agent(
                user_message=request.message,
                session_id=session_id,
                user_id=user_id,
            )
            return job_agent_pb2.ChatResponse(response=response, session_id=session_id)
        except AppError as exc:
            code, detail = _map_app_error(exc)
            context.abort(code, detail)

    def SearchJobs(
        self,
        request: job_agent_pb2.JobSearchRequest,
        context: grpc.ServicerContext,
    ) -> job_agent_pb2.JobSearchResponse:
        _require_auth(context)
        if not request.query:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "'query' is required.")
        session_id = request.session_id or "direct"
        try:
            results = fetch_job_listings(request.query, request.location or "")
            return job_agent_pb2.JobSearchResponse(results=results, session_id=session_id)
        except AppError as exc:
            code, detail = _map_app_error(exc)
            context.abort(code, detail)

    def AnalyzeResume(
        self,
        request: job_agent_pb2.ResumeAnalysisRequest,
        context: grpc.ServicerContext,
    ) -> job_agent_pb2.ResumeAnalysisResponse:
        _require_auth(context)
        if not request.resume_text:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "'resume_text' is required.")
        session_id = request.session_id or "direct"
        try:
            analysis = analyze_resume_core(
                request.resume_text, request.job_description or ""
            )
            return job_agent_pb2.ResumeAnalysisResponse(
                analysis=analysis, session_id=session_id
            )
        except AppError as exc:
            code, detail = _map_app_error(exc)
            context.abort(code, detail)

    def GenerateCoverLetter(
        self,
        request: job_agent_pb2.CoverLetterRequest,
        context: grpc.ServicerContext,
    ) -> job_agent_pb2.CoverLetterResponse:
        _require_auth(context)
        missing = [
            f for f in ("resume_text", "job_title", "company_name", "job_description")
            if not getattr(request, f, None)
        ]
        if missing:
            context.abort(
                grpc.StatusCode.INVALID_ARGUMENT,
                f"Required fields missing: {', '.join(missing)}",
            )
        session_id = request.session_id or "direct"
        try:
            cover_letter = generate_cover_letter_core(
                resume_text=request.resume_text,
                job_title=request.job_title,
                company_name=request.company_name,
                job_description=request.job_description,
                user_name=request.user_name or "Applicant",
            )
            return job_agent_pb2.CoverLetterResponse(
                cover_letter=cover_letter, session_id=session_id
            )
        except AppError as exc:
            code, detail = _map_app_error(exc)
            context.abort(code, detail)

    def ClearSession(
        self,
        request: job_agent_pb2.ClearSessionRequest,
        context: grpc.ServicerContext,
    ) -> job_agent_pb2.ClearSessionResponse:
        _require_auth(context)
        if not request.session_id:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "'session_id' is required.")
        clear_session(request.session_id)
        return job_agent_pb2.ClearSessionResponse(
            message="Session cleared successfully.",
            session_id=request.session_id,
        )

    def ListSessions(
        self,
        request: job_agent_pb2.ListSessionsRequest,
        context: grpc.ServicerContext,
    ) -> job_agent_pb2.ListSessionsResponse:
        _require_auth(context)
        return job_agent_pb2.ListSessionsResponse(sessions=list_sessions())


# ── Server startup ─────────────────────────────────────────────────────────────

def serve(
    host: str = "0.0.0.0",
    port: int = 50051,
    workers: int = 10,
    use_tls: bool = False,
    tls_cert_chain: Optional[str] = None,
    tls_private_key: Optional[str] = None,
) -> None:
    """
    Start the gRPC server (blocking until KeyboardInterrupt or SIGTERM).

    Args:
        host:            Bind address (default 0.0.0.0 — all interfaces).
        port:            Listening port (default 50051).
        workers:         Thread-pool size for concurrent RPC handling.
        use_tls:         Enable TLS. Requires cert_chain and private_key.
        tls_cert_chain:  Path to the PEM certificate chain file.
        tls_private_key: Path to the PEM private key file.
    """
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=workers))
    job_agent_pb2_grpc.add_JobAgentServiceServicer_to_server(
        JobAgentServicer(), server
    )

    address = f"{host}:{port}"

    if use_tls:
        if not tls_cert_chain or not tls_private_key:
            raise ValueError("TLS requires both tls_cert_chain and tls_private_key.")
        with open(tls_cert_chain, "rb") as f:
            cert = f.read()
        with open(tls_private_key, "rb") as f:
            key = f.read()
        credentials = grpc.ssl_server_credentials([(key, cert)])
        server.add_secure_port(address, credentials)
        logger.info("gRPC server (TLS) listening on %s (workers=%d)", address, workers)
    else:
        server.add_insecure_port(address)
        logger.info(
            "gRPC server (insecure) listening on %s (workers=%d) — "
            "use TLS in production",
            address,
            workers,
        )

    server.start()

    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("Shutting down gRPC server…")
        server.stop(grace=5)
        logger.info("gRPC server stopped.")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    from observability.langfuse_config import flush_langfuse

    load_dotenv()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    grpc_port = int(os.getenv("GRPC_PORT", "50051"))
    grpc_workers = int(os.getenv("GRPC_WORKERS", "10"))

    try:
        serve(port=grpc_port, workers=grpc_workers)
    finally:
        flush_langfuse()
