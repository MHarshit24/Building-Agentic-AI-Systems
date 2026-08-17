"""
tests/integration/test_escalation_mcp.py

Stage 7 — Escalation Manager's real LLM upgrade (§39.3, §13) and the MCP
notification integration (§7, §12, §36).

---------------------------------------------------------------------------
A real technical finding that shaped this file's design, empirically
confirmed with a throwaway spike before writing the tests below (not
assumed): this project's `client` fixture uses `httpx.AsyncClient(
transport=ASGITransport(app=app))` (in-process, no real socket). Under
ASGITransport, `await client.post(...)` does NOT return until any
FastAPI BackgroundTask scheduled during that request has also finished —
confirmed directly: a minimal FastAPI app with a background task that
awaits an unset asyncio.Event() caused `client.get(...)` to hang until a
5s timeout, never returning early. This is different from a real deployed
server, which flushes the HTTP response to the actual socket and only
then continues running background work.

Consequence: a timing-based "assert the response returns before the
Mailtrap call completes" test would not just be flaky (Stage 6's lesson
with wall-clock concurrency assertions) — it would hang outright, since
there's no ASGITransport-visible moment where the response exists but
the background task hasn't run yet. So the provable claim here shifts
from "observe non-blocking behavior end-to-end" to "verify the code is
STRUCTURED to be non-blocking" (dispatched via
`BackgroundTasks.add_task(...)`, never `await`ed inline) — Starlette's
own background-task execution-order guarantee is already correct and
outside this project's testing responsibility.

Real subprocess isolation (mcp_servers/notification_mcp/server.py runs
as a genuinely separate process once spawned via stdio_client) is the
second reason most tests here call `_send_escalation_email_impl`/
`_log_notification_impl` directly rather than going through the
protocol: `monkeypatch` in this test process has no effect on a
subprocess's own module state. Only one test (marked `eval`) exercises
the real stdio round-trip.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock
from urllib.parse import quote_plus
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from starlette.background import BackgroundTasks

import app.llm.structured_output as structured_output_module
from app.auth.security import hash_password
from app.config import get_settings
from app.db.models import EscalationLog, NotificationLog, NotificationStatus, User, UserRole, is_eligible_for_retry
from app.db.session import async_session_maker
from app.orchestration.nodes.escalate import escalate_node

# ---------------------------------------------------------------------------
# Shared fake LLM client for the full-graph tests below — dispatches by
# schema-unique field-name marker, same technique test_graph_parallel_
# fanout.py (Stage 6) already established. Only classify/escalate markers
# are defined: these tests force the explicit-human-request short-circuit
# (§5), which bypasses doc_retrieval/reflect entirely — if the graph
# incorrectly proceeded past that short-circuit, _identify() raises a
# clean AssertionError rather than silently matching the wrong schema.
# ---------------------------------------------------------------------------

CANNED_CLASSIFY = '{"category": "usage", "severity_initial": "Low", "explicit_human_request": true}'
CANNED_ESCALATE = (
    '{"escalation_reason": "Low confidence.", '
    '"human_handoff_summary": "Customer asked X, system was unsure."}'
)
MARKERS = [
    ("human_handoff_summary", "escalate"),
    ("severity_initial", "classify"),
]


class _RoutedFakeClient:
    def __init__(self) -> None:
        self.call_counts: dict[str, int] = {}

    def _identify(self, prompt: str) -> str:
        lowered = prompt.lower()
        for marker, name in MARKERS:
            if marker in lowered:
                return name
        raise AssertionError(f"could not identify which node this prompt belongs to: {prompt[:200]!r}")

    async def generate(self, prompt: str, **kwargs: Any) -> str:
        name = self._identify(prompt)
        self.call_counts[name] = self.call_counts.get(name, 0) + 1
        return CANNED_CLASSIFY if name == "classify" else CANNED_ESCALATE

    async def generate_vision(self, image_bytes: bytes, prompt: str, **kwargs: Any) -> str:
        raise NotImplementedError("not exercised by this test")


@pytest.fixture
def patch_llm_client(monkeypatch):
    def _patch() -> _RoutedFakeClient:
        fake = _RoutedFakeClient()
        monkeypatch.setattr(structured_output_module, "get_llm_client", lambda: fake)
        return fake

    return _patch


async def _login(client, user, password) -> str:
    resp = await client.post("/auth/login", json={"email": user.email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


# ---------------------------------------------------------------------------
# 1. Non-blocking dispatch — structural proof, not a timing race (see
#    module docstring for why).
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_notify_human_dispatched_via_background_tasks_not_awaited_inline(
    client, support_agent_user, patch_llm_client, monkeypatch, cleanup_conversations, cleanup_escalations
):
    calls = []
    original_add_task = BackgroundTasks.add_task

    def recording_add_task(self, func, *args, **kwargs):
        calls.append((func, args, kwargs))
        return original_add_task(self, func, *args, **kwargs)

    monkeypatch.setattr(BackgroundTasks, "add_task", recording_add_task)

    fast_notify = AsyncMock()
    monkeypatch.setattr("app.api.routes_chat.notify_human", fast_notify)

    user, password = support_agent_user
    token = await _login(client, user, password)
    patch_llm_client()

    resp = await client.post(
        "/chat",
        json={"query": "Can you connect me with a human support agent?", "customer_id": 1},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 200
    body = resp.json()
    cleanup_conversations.append(body["conversation_id"])
    cleanup_escalations.append(body["trace_id"])
    assert body["escalated"] is True

    assert len(calls) == 1, f"expected exactly one BackgroundTasks.add_task call, got {len(calls)}"
    func, args, kwargs = calls[0]
    assert func is fast_notify, "notify_human must be passed to add_task, not awaited inline"
    assert kwargs["reason"] == "Low confidence."
    assert kwargs["summary"] == "Customer asked X, system was unsure."
    assert "escalation_id" in kwargs
    assert "ticket_context" in kwargs
    fast_notify.assert_awaited_once()


# ---------------------------------------------------------------------------
# 2. escalate_node's own LLM call — component test, not the full graph.
# ---------------------------------------------------------------------------


class _QueuedFakeClient:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.call_count = 0
        self.last_kwargs: dict[str, Any] = {}

    async def generate(self, prompt: str, **kwargs: Any) -> str:
        self.call_count += 1
        self.last_kwargs = kwargs
        return self._responses.pop(0)

    async def generate_vision(self, image_bytes: bytes, prompt: str, **kwargs: Any) -> str:
        raise NotImplementedError("not exercised by this test")


@pytest.fixture
def patch_queued_llm_client(monkeypatch):
    def _patch(responses: list[str]) -> _QueuedFakeClient:
        fake = _QueuedFakeClient(responses)
        monkeypatch.setattr(structured_output_module, "get_llm_client", lambda: fake)
        return fake

    return _patch


@pytest.mark.asyncio
async def test_escalate_node_passes_through_llm_output(patch_queued_llm_client):
    fake = patch_queued_llm_client(
        ['{"escalation_reason": "Critical severity.", "human_handoff_summary": "Outage reported."}']
    )
    state = {
        "query": "Production is down",
        "chat_history": [],
        "category": "incident",
        "severity_initial": "Critical",
        "severity_final": None,
        "confidence_tier": None,
        "confidence_score": None,
        "groundedness_flag": None,
        "retrieval_mode": "Critical",
        "explicit_human_request": False,
        "final_answer": None,
        "retrieval_retry_count": 0,
        "reflection_loopback_count": 0,
    }

    result = await escalate_node(state)

    assert result["escalation_reason"] == "Critical severity."
    assert result["human_handoff_summary"] == "Outage reported."
    assert result["escalation_flag"] is True
    assert result["notification_sent"] is False
    assert fake.last_kwargs.get("reasoning_effort") == "low"
    # No prior draft_answer existed -> falls back to the fixed customer-facing text.
    assert "escalated to a human support specialist" in result["final_answer"]


@pytest.mark.asyncio
async def test_escalate_node_keeps_existing_draft_as_customer_facing_answer(patch_queued_llm_client):
    """final_answer, when one already exists (e.g. doc_retrieval's own
    draft, judged Low-confidence by reflect), is NOT overwritten by
    escalate_node — see module docstring in escalate.py for why."""
    patch_queued_llm_client(
        ['{"escalation_reason": "Low confidence.", "human_handoff_summary": "See draft."}']
    )
    state = {
        "query": "How do I do X?",
        "chat_history": [],
        "category": "usage",
        "severity_initial": "Low",
        "severity_final": None,
        "confidence_tier": "Low",
        "confidence_score": 0.4,
        "groundedness_flag": False,
        "retrieval_mode": "RAG",
        "explicit_human_request": False,
        "final_answer": "I don't have enough information to answer that.",
        "retrieval_retry_count": 1,
        "reflection_loopback_count": 1,
    }

    result = await escalate_node(state)

    assert result["final_answer"] == "I don't have enough information to answer that."


@pytest.mark.asyncio
async def test_escalate_node_falls_back_internally_on_structured_output_failure(patch_queued_llm_client):
    """Exhausts call_llm_structured's own bounded retry (two malformed
    responses) -> escalate_node must catch this ITSELF (it is not
    wrapped in graph.py's generic _guard_structured_output, see that
    module's docstring for why) and fall back to fixed text, never
    propagate the exception."""
    patch_queued_llm_client(["not json", "still not json"])
    state = {
        "query": "Something went wrong",
        "chat_history": [],
        "category": "usage",
        "severity_initial": "Low",
        "severity_final": None,
        "confidence_tier": "Low",
        "confidence_score": 0.3,
        "groundedness_flag": False,
        "retrieval_mode": "RAG",
        "explicit_human_request": False,
        "final_answer": None,
        "retrieval_retry_count": 0,
        "reflection_loopback_count": 0,
    }

    result = await escalate_node(state)  # must not raise

    assert result["escalation_flag"] is True
    assert result["escalation_reason"]
    assert result["human_handoff_summary"]
    assert result["final_answer"]  # never empty, even on internal LLM failure


# ---------------------------------------------------------------------------
# 3. MCP server tool implementations, called directly (no subprocess, no
#    protocol) — see module docstring for why this is most of the coverage.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_escalation_email_impl_success(monkeypatch):
    from mcp_servers.notification_mcp import server

    monkeypatch.setattr(server, "send_email", AsyncMock(return_value=True))

    result = await server._send_escalation_email_impl(
        escalation_id=1,
        ticket_context={"category": "usage", "severity_final": "Low", "query": "test"},
        reason="test reason",
        summary="test summary",
    )

    assert result == {"success": True}
    server.send_email.assert_awaited_once()


@pytest.mark.asyncio
async def test_send_escalation_email_impl_failure_propagates_as_false(monkeypatch):
    from mcp_servers.notification_mcp import server

    monkeypatch.setattr(server, "send_email", AsyncMock(return_value=False))

    result = await server._send_escalation_email_impl(
        escalation_id=1, ticket_context={}, reason="r", summary="s"
    )

    assert result == {"success": False}


@pytest.mark.asyncio
async def test_log_notification_impl_writes_real_row(support_agent_user, make_escalation):
    from mcp_servers.notification_mcp.server import _log_notification_impl

    user, _ = support_agent_user
    escalation = await make_escalation(handled_by_user_id=user.user_id)

    await _log_notification_impl(escalation_id=escalation.escalation_id, channel="email", status="sent")

    async with async_session_maker() as db:
        result = await db.execute(
            select(NotificationLog).where(NotificationLog.escalation_id == escalation.escalation_id)
        )
        row = result.scalar_one()
    assert row.channel == "email"
    assert row.status == NotificationStatus.sent


# ---------------------------------------------------------------------------
# 4. Retry-eligibility — pure logic (§36 scope split: this stage builds the
#    decision, not the scheduled execution — see runbook.md).
# ---------------------------------------------------------------------------


class TestIsEligibleForRetry:
    def test_failed_is_eligible(self):
        assert is_eligible_for_retry("failed") is True

    def test_sent_is_not_eligible(self):
        assert is_eligible_for_retry("sent") is False

    def test_failed_permanently_is_not_eligible(self):
        assert is_eligible_for_retry("failed_permanently") is False


# ---------------------------------------------------------------------------
# 4b. _tool_call_succeeded() — found via a manual smoke test, not a unit
#     test, which is exactly the gap this test closes: this FastMCP
#     version does NOT populate CallToolResult.structuredContent for a
#     tool returning a plain dict (confirmed via a direct diagnostic
#     call) — the real {"success": ...} JSON lives in content[0].text
#     instead. Without this fix every real send success was misread as
#     "failed". These tests pin both response shapes so a future SDK
#     version that changes which one is populated is caught here, not
#     silently misread again in production.
# ---------------------------------------------------------------------------


class TestToolCallSucceeded:
    def test_reads_from_structured_content_when_present(self):
        from mcp.types import CallToolResult

        from app.mcp_client.notification_client import _tool_call_succeeded

        result = CallToolResult(content=[], structuredContent={"success": True}, isError=False)
        assert _tool_call_succeeded(result) is True

    def test_falls_back_to_text_content_when_structured_content_is_none(self):
        from mcp.types import CallToolResult, TextContent

        from app.mcp_client.notification_client import _tool_call_succeeded

        result = CallToolResult(
            content=[TextContent(type="text", text='{"success": true}')],
            structuredContent=None,
            isError=False,
        )
        assert _tool_call_succeeded(result) is True

    def test_false_when_text_content_says_false(self):
        from mcp.types import CallToolResult, TextContent

        from app.mcp_client.notification_client import _tool_call_succeeded

        result = CallToolResult(
            content=[TextContent(type="text", text='{"success": false}')],
            structuredContent=None,
            isError=False,
        )
        assert _tool_call_succeeded(result) is False

    def test_false_when_is_error(self):
        from mcp.types import CallToolResult, TextContent

        from app.mcp_client.notification_client import _tool_call_succeeded

        result = CallToolResult(
            content=[TextContent(type="text", text='{"success": true}')],
            structuredContent={"success": True},
            isError=True,
        )
        assert _tool_call_succeeded(result) is False


# ---------------------------------------------------------------------------
# 5. Real end-to-end: actual subprocess, actual MCP protocol round-trip,
#    actual Mailtrap sandbox SMTP send. Not PR-blocking CI (§19 L4/L5 tier).
#
# Real bug found during Stage 8's own verification, fixed here rather than
# left in place: mcp_servers/notification_mcp/server.py runs as a genuinely
# separate OS process (spawned by notify_human() via stdio_client) that
# independently re-runs app/config.py's _load_env() from scratch — it does
# NOT inherit this test session's in-memory DB_NAME redirection to the
# disposable `_test` database. Confirmed empirically two ways:
#   1. MCP's own stdio_client() computes the subprocess's env as
#      get_default_environment() (a curated safe allowlist — PATH, TEMP,
#      USERNAME, etc. — confirmed by reading mcp/client/stdio/__init__.py)
#      whenever StdioServerParameters.env is None, which notification_
#      client.py's _SERVER_PARAMS leaves unset. That allowlist excludes
#      DB_NAME entirely.
#   2. Even passing DB_NAME through explicitly wouldn't help: spawning a
#      subprocess with DB_NAME pre-set in its env and letting
#      app.config._load_env() run confirms it resolves back to the real
#      dev db_name regardless — the project .env load uses
#      load_dotenv(..., override=True), so an inherited test-DB value gets
#      overwritten right back to the real one.
# So the subprocess always writes its NotificationLog row against the real
# dev database, never the disposable test one — matching how every other
# standalone entry point in this project (alembic/env.py, scripts/
# seed_synthetic_data.py) already behaves: a fresh, real .env load, no
# test-DB awareness. This test now follows that same convention instead of
# fighting it: it creates its own User + EscalationLog rows directly in
# the real dev database (not via support_agent_user/make_escalation, which
# both write to the disposable test DB — an escalation_id from there has
# no meaning in the dev DB's own escalation_log table, and would only
# "work" by accident if the two independently-sequenced tables' next
# auto-increment IDs happened to collide), then verifies and cleans up
# all three rows against that same real dev database afterward.
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def real_dev_db_session_maker():
    """Mirrors tests/integration/test_hybrid_search.py's own
    `_use_real_dev_database` fixture exactly (same construction, same
    reasoning) — the established pattern in this suite for the rare case
    where a test genuinely needs the real dev database, not the disposable
    per-session one. Function-scoped for the same reason that fixture is:
    asyncpg connections are bound to the event loop they were opened
    under, and pytest-asyncio gives each test its own loop by default."""
    settings = get_settings()
    dev_db_name = settings.db_name.removesuffix("_test")
    password = quote_plus(settings.db_password)
    dev_url = f"postgresql+asyncpg://{settings.db_user}:{password}@{settings.db_host}:{settings.db_port}/{dev_db_name}"

    dev_engine = create_async_engine(dev_url, echo=False, future=True, pool_pre_ping=True)
    dev_session_maker = async_sessionmaker(bind=dev_engine, class_=AsyncSession, expire_on_commit=False, autoflush=False)
    yield dev_session_maker
    await dev_engine.dispose()


@pytest.mark.asyncio
async def test_real_dev_db_session_maker_targets_a_different_database_than_the_test_session(
    real_dev_db_session_maker,
):
    """Regression test for the actual bug, not just the expensive
    end-to-end symptom: confirms real_dev_db_session_maker's engine is
    bound to a genuinely different database than this test session's own
    async_session_maker (the disposable `_test`-suffixed one) — the exact
    distinction the MCP subprocess bug hinges on. Deliberately NOT
    eval-marked: no real API/subprocess/Mailtrap call needed to prove this,
    just two real Postgres connections confirming their own database name,
    so this runs in every normal CI pass and would fail loudly if this
    fixture were ever "simplified" back to reusing the test-session
    async_session_maker (silently reintroducing the original bug)."""
    async with real_dev_db_session_maker() as dev_db:
        dev_name_result = await dev_db.execute(select(func.current_database()))
        dev_db_name = dev_name_result.scalar_one()

    async with async_session_maker() as test_db:
        test_name_result = await test_db.execute(select(func.current_database()))
        test_db_name = test_name_result.scalar_one()

    assert dev_db_name != test_db_name
    assert test_db_name.endswith("_test")
    assert dev_db_name == test_db_name.removesuffix("_test")


@pytest.mark.eval
@pytest.mark.asyncio
async def test_notify_human_real_subprocess_and_mailtrap_round_trip(real_dev_db_session_maker):
    from app.mcp_client.notification_client import notify_human

    # Real User + EscalationLog rows in the REAL dev database — the
    # subprocess's own NotificationLog insert references escalation_id
    # against that same database's escalation_log table, so the row it
    # points at must actually exist there (see block comment above).
    async with real_dev_db_session_maker() as db:
        user = User(
            email=f"stage8-mcp-eval-{uuid4().hex[:12]}@test.local",
            password_hash=hash_password("Test-Passw0rd!"),
            role=UserRole.support_agent,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

        escalation = EscalationLog(
            trace_id=f"trace_{uuid4().hex[:12]}",
            handled_by_user_id=user.user_id,
            ticket_context_json={"query": "real end-to-end test"},
            reason="test escalation",
        )
        db.add(escalation)
        await db.commit()
        await db.refresh(escalation)

    try:
        await notify_human(
            escalation_id=escalation.escalation_id,
            ticket_context={"category": "usage", "severity_final": "Low", "query": "real end-to-end test"},
            reason="real end-to-end test",
            summary="This is a real Mailtrap sandbox send from test_escalation_mcp.py.",
        )

        async with real_dev_db_session_maker() as db:
            result = await db.execute(
                select(NotificationLog).where(NotificationLog.escalation_id == escalation.escalation_id)
            )
            row = result.scalar_one()
        assert row.status == NotificationStatus.sent
    finally:
        # Child rows before parent (notification_log.escalation_id has no
        # ON DELETE CASCADE — same ordering as conftest.py's make_escalation
        # teardown), then the user, against the real dev database.
        async with real_dev_db_session_maker() as db:
            await db.execute(delete(NotificationLog).where(NotificationLog.escalation_id == escalation.escalation_id))
            await db.execute(delete(EscalationLog).where(EscalationLog.escalation_id == escalation.escalation_id))
            await db.execute(delete(User).where(User.user_id == user.user_id))
            await db.commit()
