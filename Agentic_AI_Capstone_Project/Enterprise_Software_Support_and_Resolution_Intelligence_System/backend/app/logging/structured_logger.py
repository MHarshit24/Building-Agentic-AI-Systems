"""
app/logging/structured_logger.py

Structured JSON application logging (§34) — distinct from Langfuse
tracing (§15), which traces LLM/agent *decisions* (cost, latency,
confidence per node). This module is for everything Langfuse doesn't
cover: a Postgres connection error, a malformed request, a Redis
timeout, request start/end.

One JSON line per event, not free-text. Every line carries trace_id,
request_id, endpoint, level, event, plus whatever context a call site
adds. request_id and endpoint are populated automatically per-request via
contextvars, set by app/middleware/request_context.py — no call site
threads them through manually. trace_id is bound the same way once a
chat request creates its Langfuse trace (bind_trace_id()), since that
value doesn't exist yet at the top of the request.

configure_logging() attaches this JSON formatting to the ROOT logger, so
every *existing* `logging.getLogger(__name__)` call site already in this
codebase (jwt_handler.py, config.py, etc.) starts emitting structured
JSON for free, without being individually rewritten — a plain
`logger.info("message")` call still works; the message becomes the
"event" field with an empty context.

Log levels are used per §34's own convention: DEBUG (verbose node
entry/exit, off by default in prod), INFO (request start/end, escalation
fired, job completed), WARNING (retry triggered, low-confidence result,
rate limit approached), ERROR (external dependency failure, unhandled
exception).
"""

from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar, Token
from datetime import datetime, timezone
from typing import Any

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
_trace_id: ContextVar[str | None] = ContextVar("trace_id", default=None)
_endpoint: ContextVar[str | None] = ContextVar("endpoint", default=None)


def bind_request_context(
    *, request_id: str | None = None, endpoint: str | None = None
) -> list[tuple[ContextVar, Token]]:
    """Called once per request by the request-id middleware. Returns the
    tokens needed to reset each contextvar at request teardown — never
    leaves stale values for the next request/task to accidentally read.

    Also seeds _trace_id to None here (even though no trace_id is known
    yet this early) purely to capture a reset token for it up front. That
    token's .reset() call discards *whatever* _trace_id holds by request
    end, no matter when or how deep in the call stack bind_trace_id() got
    called later — so a route handler can call bind_trace_id() and never
    think about cleanup itself. This matters concretely, not just in
    theory: verified empirically that httpx's ASGITransport (used
    throughout this project's own test suite) does NOT spawn a fresh
    asyncio Task per request the way a real ASGI server does, so a
    contextvar set with no reset genuinely leaks from one request into
    the next call on the same client — this isn't a hypothetical edge
    case, it's exactly how this codebase's tests would poison each other
    the moment routes_chat.py starts calling bind_trace_id()."""
    tokens: list[tuple[ContextVar, Token]] = []
    if request_id is not None:
        tokens.append((_request_id, _request_id.set(request_id)))
    if endpoint is not None:
        tokens.append((_endpoint, _endpoint.set(endpoint)))
    tokens.append((_trace_id, _trace_id.set(None)))
    return tokens


def reset_request_context(tokens: list[tuple[ContextVar, Token]]) -> None:
    for var, token in tokens:
        var.reset(token)


def get_request_context() -> dict[str, str | None]:
    """Read-only access to the current request's request_id/endpoint —
    needed by app/observability/tracing.py to populate §15's trace-metadata
    fields onto classify_node's span, since those fields live in these
    contextvars, not in SupportGraphState."""
    return {"request_id": _request_id.get(), "endpoint": _endpoint.get()}


def bind_trace_id(trace_id: str) -> None:
    """Called once a Langfuse trace_id exists for the current request
    (e.g. inside routes_chat.py, after graph invocation creates one) so
    every subsequent log line in this request correlates to it, without
    threading trace_id through every call site downstream.

    Deliberately does NOT return its own token — bind_request_context()
    already captured one for _trace_id at request start (see its
    docstring), and that token's reset() at request teardown discards
    whatever this function sets, regardless of when it's called. A
    second, independent token here would be redundant and would tempt a
    future caller into a reset path that isn't actually necessary."""
    _trace_id.set(trace_id)


class _ContextFilter(logging.Filter):
    """Injects the current request/trace/endpoint context (if any) onto
    every LogRecord before it's formatted — this is the actual mechanism
    that makes trace_id/request_id/endpoint "automatic"."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = _request_id.get()
        record.trace_id = _trace_id.get()
        record.endpoint = _endpoint.get()
        return True


class JSONFormatter(logging.Formatter):
    """One JSON line per log record — §34's exact field list."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "event": record.getMessage(),
            "trace_id": getattr(record, "trace_id", None),
            "request_id": getattr(record, "request_id", None),
            "endpoint": getattr(record, "endpoint", None),
            "logger": record.name,
        }
        context = getattr(record, "context", None)
        if context:
            payload["context"] = context
        if record.exc_info and record.exc_info[0] is not None:
            payload["error_type"] = record.exc_info[0].__name__
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


_configured = False


def configure_logging(level: int = logging.INFO) -> None:
    """Idempotent — safe to call more than once (e.g. once from
    app/main.py at import time). Attaches JSON formatting to the root
    logger so every existing logging.getLogger(__name__) call site in
    the codebase gets structured stdout output for free, per §34."""
    global _configured
    root = logging.getLogger()
    root.setLevel(level)

    if _configured:
        return

    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(JSONFormatter())
    handler.addFilter(_ContextFilter())
    root.handlers = [handler]
    _configured = True


def log_event(logger: logging.Logger, level: str, event: str, **context: Any) -> None:
    """Convenience call for new-style structured logging with a free-form
    context dict (§34: node_name, duration_ms, error_type, etc.).
    trace_id/request_id/endpoint are NOT passed here — _ContextFilter
    injects them automatically from whatever request is currently active."""
    numeric_level = logging.getLevelName(level.upper())
    if not isinstance(numeric_level, int):
        numeric_level = logging.INFO
    logger.log(numeric_level, event, extra={"context": context} if context else None)
