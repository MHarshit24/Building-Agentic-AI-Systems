"""
app/middleware/request_context.py

Generates request_id automatically for every request (§34) — no
existing middleware (jwt_auth.py, rbac_check.py, rate_limit.py) did this,
so this is the one that does. Also logs request start/end at INFO, per
§34's own level convention.
"""

import logging
import time
import uuid

from fastapi import Request

from app.logging.structured_logger import bind_request_context, log_event, reset_request_context

logger = logging.getLogger(__name__)


async def request_context_middleware(request: Request, call_next):
    # Works around a real slowapi bug (confirmed by reading the installed
    # package's extension.py): swallow_errors=True only protects the rate-
    # CHECK phase (__evaluate_limits) — if the storage backend (Redis) is
    # unreachable, that exception is swallowed, but request.state.
    # view_rate_limit is only ever set on the success path of that same
    # function. The header-injection phase that runs right after
    # unconditionally reads that attribute regardless, so a swallowed
    # Redis outage still crashed every rate-limited endpoint with a 500
    # AttributeError. _inject_headers already treats current_limit=None as
    # "skip header injection" (checked directly in slowapi's source), so
    # seeding this default here — before any route or limiter code runs —
    # makes a Redis outage degrade to "no rate-limit headers", not a 500.
    request.state.view_rate_limit = None

    request_id = str(uuid.uuid4())
    tokens = bind_request_context(request_id=request_id, endpoint=request.url.path)

    start = time.monotonic()
    log_event(logger, "INFO", "request_start", method=request.method, path=request.url.path)

    try:
        response = await call_next(request)
        duration_ms = (time.monotonic() - start) * 1000
        log_event(
            logger,
            "INFO",
            "request_end",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round(duration_ms, 2),
        )
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        # Always reset, even if call_next raised — never leaks this
        # request's context into whatever runs next on this task.
        reset_request_context(tokens)
