"""
tests/unit/test_structured_logger.py

L1 tests (§19) for structured JSON logging (§34) — no LLM, no DB. Confirms
a logged event is valid, parseable JSON with the required fields present,
and that request context (request_id/endpoint) is auto-injected via
contextvars rather than needing to be passed at each call site.
"""

from __future__ import annotations

import io
import json
import logging

import pytest

from app.logging import structured_logger as structured_logger_module
from app.logging.structured_logger import (
    JSONFormatter,
    _ContextFilter,
    bind_request_context,
    bind_trace_id,
    log_event,
    reset_request_context,
)
from app.main import app

REQUIRED_FIELDS = {"trace_id", "request_id", "endpoint", "level", "event"}

# ---------------------------------------------------------------------------
# Throwaway probe route (same pattern as test_auth.py's admin_probe):
# stands in for what routes_chat.py will eventually do — call
# bind_trace_id() partway through handling a request — so the
# request_context_middleware -> bind_trace_id() -> teardown path can be
# exercised over real HTTP without routes_chat.py existing yet.
# ---------------------------------------------------------------------------


@app.get("/_test_only/trace_probe")
async def _trace_probe(value: str | None = None):
    if value:
        bind_trace_id(value)
    return {"trace_id": structured_logger_module._trace_id.get()}


def _logger_with_capturing_handler(name: str) -> tuple[logging.Logger, io.StringIO]:
    """A dedicated logger + in-memory handler using the real JSONFormatter
    and _ContextFilter, isolated from the root logger / pytest's own log
    capturing so the captured text is exactly one formatted JSON line."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JSONFormatter())
    handler.addFilter(_ContextFilter())

    logger = logging.getLogger(name)
    logger.handlers = [handler]
    logger.propagate = False
    logger.setLevel(logging.DEBUG)
    return logger, stream


def test_log_event_emits_valid_json_with_required_fields():
    logger, stream = _logger_with_capturing_handler("test.structured_logger.basic")

    log_event(logger, "INFO", "escalation_fired", severity="Critical", confidence=0.42)

    line = stream.getvalue().strip()
    parsed = json.loads(line)  # raises if not valid JSON

    assert REQUIRED_FIELDS.issubset(parsed.keys())
    assert parsed["level"] == "INFO"
    assert parsed["event"] == "escalation_fired"
    assert parsed["context"] == {"severity": "Critical", "confidence": 0.42}


def test_request_context_is_auto_injected_not_passed_by_caller():
    logger, stream = _logger_with_capturing_handler("test.structured_logger.context")

    tokens = bind_request_context(request_id="req-abc123", endpoint="/chat")
    try:
        log_event(logger, "INFO", "node_entry", node_name="classify")
    finally:
        reset_request_context(tokens)

    parsed = json.loads(stream.getvalue().strip())
    assert parsed["request_id"] == "req-abc123"
    assert parsed["endpoint"] == "/chat"
    # trace_id was never bound in this test — must be absent, not fabricated
    assert parsed["trace_id"] is None


def test_request_context_resets_after_request(monkeypatch):
    logger, stream = _logger_with_capturing_handler("test.structured_logger.reset")

    tokens = bind_request_context(request_id="req-should-not-leak", endpoint="/ingest")
    reset_request_context(tokens)

    log_event(logger, "INFO", "after_reset")

    parsed = json.loads(stream.getvalue().strip())
    assert parsed["request_id"] is None
    assert parsed["endpoint"] is None


def test_plain_logging_call_still_produces_valid_json():
    """A pre-existing, un-migrated `logger.info("message")` call site
    (the style already used in jwt_handler.py, config.py, etc.) must
    still emit valid structured JSON once JSONFormatter is attached —
    that's the whole point of not needing to rewrite every call site."""
    logger, stream = _logger_with_capturing_handler("test.structured_logger.plain")

    logger.warning("Redis is unreachable, skipping JWT blacklist check")

    parsed = json.loads(stream.getvalue().strip())
    assert parsed["level"] == "WARNING"
    assert parsed["event"] == "Redis is unreachable, skipping JWT blacklist check"
    assert "context" not in parsed


@pytest.mark.asyncio
async def test_middleware_sets_request_id_header(client):
    resp = await client.get("/health")
    assert "X-Request-ID" in resp.headers
    # A real UUID4 string, not a placeholder
    import uuid

    uuid.UUID(resp.headers["X-Request-ID"])


# ---------------------------------------------------------------------------
# bind_trace_id() — asymmetric-cleanup review (see structured_logger.py's
# bind_request_context() docstring for the full reasoning). Confirmed
# empirically before fixing: httpx's ASGITransport does NOT give each
# request its own asyncio Task the way a real ASGI server does, so a
# contextvar set with no reset genuinely leaks from one request into the
# next call on the same client — not just a theoretical risk.
# ---------------------------------------------------------------------------


def test_bind_trace_id_sets_a_value_the_filter_picks_up():
    logger, stream = _logger_with_capturing_handler("test.structured_logger.trace_id")

    tokens = bind_request_context(request_id="req-1", endpoint="/chat")
    try:
        bind_trace_id("lf_abc123")
        log_event(logger, "INFO", "reflect_complete", confidence_tier="High")
    finally:
        reset_request_context(tokens)

    parsed = json.loads(stream.getvalue().strip())
    assert parsed["trace_id"] == "lf_abc123"


def test_reset_request_context_discards_trace_id_bound_after_it(monkeypatch):
    """The core guarantee: bind_request_context()'s token for _trace_id is
    captured BEFORE any value exists, so resetting it discards whatever
    bind_trace_id() sets later in the request — regardless of when, or
    how deep in the call stack, that happens. bind_trace_id() itself
    needs no token of its own for this to hold."""
    logger, stream = _logger_with_capturing_handler("test.structured_logger.trace_reset")

    tokens = bind_request_context(request_id="req-2", endpoint="/chat")
    bind_trace_id("lf_should_not_survive_reset")
    reset_request_context(tokens)

    log_event(logger, "INFO", "after_request_teardown")

    parsed = json.loads(stream.getvalue().strip())
    assert parsed["trace_id"] is None
    assert parsed["request_id"] is None


@pytest.mark.asyncio
async def test_trace_id_does_not_leak_across_sequential_requests(client):
    """Regression test for the leak demonstrated during review: without
    this fix, a trace_id bound while handling one request was still
    visible to the next request made through the same AsyncClient."""
    first = await client.get(
        "/_test_only/trace_probe", params={"value": "trace-from-request-1"}
    )
    assert first.json()["trace_id"] == "trace-from-request-1"

    second = await client.get("/_test_only/trace_probe")
    assert second.json()["trace_id"] is None
