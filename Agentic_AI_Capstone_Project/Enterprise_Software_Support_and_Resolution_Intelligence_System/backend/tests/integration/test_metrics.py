"""
tests/integration/test_metrics.py

L2 coverage (§19) for GET /metrics (app/api/routes_metrics.py) — closes a
real, confirmed gap: this endpoint had zero test coverage of any kind
before this file (grepped the whole suite for "routes_metrics"/"/metrics"
— no hits). Targets the Langfuse-sourced latency/cost path, which has
had two real, confirmed bugs found and fixed in succession (see tracing.
py's safe_query_trace_metrics docstring for the full history: first a
missing filter "type" discriminator, then — the more fundamental one —
querying the wrong Langfuse API entirely, aggregating the terminal node
spans' own near-zero duration/cost instead of the real per-request totals
that live on client.api.trace.list()'s own trace.latency/trace.total_cost
fields). This file pins down the CURRENT (trace-level) data shape with a
regression test so a future change doesn't silently reintroduce either
failure mode.

Full HTTP-level integration test (real test DB, real test client) rather
than a unit test against the route function directly — the behavior under
test is the interaction between three independent data sources (a faked
Langfuse response, real seeded `messages` rows, a real `evaluation_runs`
row), which is exactly what the endpoint's own job is to combine.

Redis caching (routes_metrics.py's 30s snapshot cache) is disabled for
every test here via the autouse fixture below — routes_metrics.py does
`from app.cache.redis_cache import cache_get, cache_set`, a local binding
per this project's own established import pattern, so it must be patched
on the routes_metrics module object, not on app.cache.redis_cache. Without
this, the first test in the file would poison every later test's response
for 30 real seconds.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import delete

import app.api.routes_metrics as routes_metrics_module
import app.observability.tracing as tracing_module
from app.db.models import Conversation, ConversationStatus, EvaluationRun, Message
from app.db.session import async_session_maker


async def _login(client, user, password) -> str:
    resp = await client.post("/auth/login", json={"email": user.email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def _disable_metrics_cache(monkeypatch):
    async def _no_cache_get(key):
        return None

    async def _no_cache_set(key, value, *, ttl_seconds=None):
        return None

    monkeypatch.setattr(routes_metrics_module, "cache_get", _no_cache_get)
    monkeypatch.setattr(routes_metrics_module, "cache_set", _no_cache_set)


@pytest_asyncio.fixture
async def make_conversation():
    created_ids: list[str] = []

    async def _make_conversation(handled_by_user_id: int, **overrides) -> Conversation:
        defaults = {
            "conversation_id": str(uuid4()),
            "customer_id": 1,
            "handled_by_user_id": handled_by_user_id,
            "status": ConversationStatus.open,
        }
        defaults.update(overrides)
        async with async_session_maker() as session:
            conversation = Conversation(**defaults)
            session.add(conversation)
            await session.commit()
            await session.refresh(conversation)
            created_ids.append(conversation.conversation_id)
            return conversation

    yield _make_conversation

    if created_ids:
        async with async_session_maker() as session:
            await session.execute(delete(Message).where(Message.conversation_id.in_(created_ids)))
            await session.execute(delete(Conversation).where(Conversation.conversation_id.in_(created_ids)))
            await session.commit()


async def _make_message(conversation_id: str, **overrides) -> Message:
    defaults = {
        "conversation_id": conversation_id,
        "role": "assistant",
        "content": "test response",
        "trace_id": f"trace_{uuid4().hex[:12]}",
        "escalation_flag": False,
    }
    defaults.update(overrides)
    async with async_session_maker() as session:
        message = Message(**defaults)
        session.add(message)
        await session.commit()
        await session.refresh(message)
        return message


@pytest_asyncio.fixture
async def cleanup_evaluation_runs():
    run_ids: list[int] = []
    yield run_ids
    if run_ids:
        async with async_session_maker() as session:
            await session.execute(delete(EvaluationRun).where(EvaluationRun.run_id.in_(run_ids)))
            await session.commit()


@pytest.mark.asyncio
async def test_metrics_computes_percentiles_and_cost_from_real_trace_records(
    client, support_agent_user, make_conversation, monkeypatch
):
    """Pins down the CURRENT data shape (client.api.trace.list()'s own
    per-trace latency-in-seconds/total_cost fields, aggregated locally by
    routes_metrics.py's own _percentile()) after two real, confirmed bugs
    in this path — see tracing.py's safe_query_trace_metrics docstring
    for the full history. Four fake traces with hand-computable nearest-
    rank percentiles: latencies [1,2,3,4]s -> p50=index 2=3.0s=3000ms,
    p95=index 3=4.0s=4000ms; costs sum to 0.10."""
    user, password = support_agent_user
    conversation = await make_conversation(handled_by_user_id=user.user_id)
    await _make_message(conversation.conversation_id, role="assistant")
    await _make_message(conversation.conversation_id, role="assistant")
    await _make_message(conversation.conversation_id, role="user")  # must be excluded from ticket_count

    def _fake_safe_query_trace_metrics(*, names, from_timestamp, to_timestamp):
        return [
            {"latency": 1.0, "total_cost": 0.01},
            {"latency": 2.0, "total_cost": 0.02},
            {"latency": 3.0, "total_cost": 0.03},
            {"latency": 4.0, "total_cost": 0.04},
        ]

    monkeypatch.setattr(tracing_module, "safe_query_trace_metrics", _fake_safe_query_trace_metrics)

    token = await _login(client, user, password)
    resp = await client.get("/metrics", headers=_auth_header(token))

    assert resp.status_code == 200
    body = resp.json()
    assert body["latency_ms"]["p50"] == pytest.approx(3000.0)
    assert body["latency_ms"]["p95"] == pytest.approx(4000.0)
    assert body["cost_per_ticket_usd"] == pytest.approx(0.10 / 2)  # 2 assistant messages, not 3


@pytest.mark.asyncio
async def test_metrics_escalation_rate_computed_from_local_messages_not_langfuse(
    client, support_agent_user, make_conversation, monkeypatch
):
    user, password = support_agent_user
    conversation = await make_conversation(handled_by_user_id=user.user_id)
    await _make_message(conversation.conversation_id, escalation_flag=True)
    await _make_message(conversation.conversation_id, escalation_flag=False)
    await _make_message(conversation.conversation_id, escalation_flag=False)

    monkeypatch.setattr(tracing_module, "safe_query_trace_metrics", lambda **kwargs: None)

    token = await _login(client, user, password)
    resp = await client.get("/metrics", headers=_auth_header(token))

    assert resp.status_code == 200
    assert resp.json()["escalation_rate"] == pytest.approx(1 / 3)


@pytest.mark.asyncio
async def test_metrics_degrades_latency_and_cost_to_null_when_langfuse_unavailable(
    client, support_agent_user, make_conversation, monkeypatch
):
    """safe_query_trace_metrics returning None (client down, network
    error — see its own docstring) must degrade GET /metrics to its
    local-DB-only fields, never a 500."""
    user, password = support_agent_user
    conversation = await make_conversation(handled_by_user_id=user.user_id)
    await _make_message(conversation.conversation_id)

    monkeypatch.setattr(tracing_module, "safe_query_trace_metrics", lambda **kwargs: None)

    token = await _login(client, user, password)
    resp = await client.get("/metrics", headers=_auth_header(token))

    assert resp.status_code == 200
    body = resp.json()
    assert body["latency_ms"]["p50"] is None
    assert body["latency_ms"]["p95"] is None
    assert body["cost_per_ticket_usd"] is None
    assert body["escalation_rate"] is not None  # local DB path unaffected


@pytest.mark.asyncio
async def test_metrics_eval_fields_are_null_when_no_evaluation_run_exists(
    client, support_agent_user, monkeypatch
):
    monkeypatch.setattr(tracing_module, "safe_query_trace_metrics", lambda **kwargs: None)

    token = await _login(client, *support_agent_user)
    resp = await client.get("/metrics", headers=_auth_header(token))

    assert resp.status_code == 200
    body = resp.json()
    assert body["last_eval_run_at"] is None
    assert body["task_success_rate"] is None
    assert body["faithfulness"] is None


@pytest.mark.asyncio
async def test_metrics_reports_the_most_recent_evaluation_run_not_an_older_one(
    client, support_agent_user, monkeypatch, cleanup_evaluation_runs
):
    monkeypatch.setattr(tracing_module, "safe_query_trace_metrics", lambda **kwargs: None)
    now = datetime.now(timezone.utc)

    async with async_session_maker() as session:
        older = EvaluationRun(
            run_at=now - timedelta(days=1), sample_size=50, task_success_rate=0.5, faithfulness=0.5
        )
        newer = EvaluationRun(run_at=now, sample_size=50, task_success_rate=0.95, faithfulness=0.9)
        session.add_all([older, newer])
        await session.commit()
        await session.refresh(older)
        await session.refresh(newer)
        cleanup_evaluation_runs.extend([older.run_id, newer.run_id])

    token = await _login(client, *support_agent_user)
    resp = await client.get("/metrics", headers=_auth_header(token))

    assert resp.status_code == 200
    body = resp.json()
    assert body["task_success_rate"] == 0.95
    assert body["faithfulness"] == 0.9
