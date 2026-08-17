"""
tests/integration/test_chat_exception_handling.py

Regression test for a real, confirmed gap named in README §37: unlike
POST /chat/stream (a real try/except around its SSE generator, converts
any failure into a clean "error" frame), the non-streaming POST /chat
had NO protection at all -- a real graph-execution failure (LLM API
outage, rate limit, any other unhandled exception) surfaced as a raw,
undifferentiated FastAPI 500. Fixed in app/api/routes_chat.py::chat()
with a try/except around active_graph.ainvoke(), converting any failure
into a clean 503 with a client-safe message, matching the streaming
path's own philosophy (never leave the client with an opaque crash).

No real LLM call here -- the module-level `graph` singleton's own
ainvoke() is monkeypatched to raise directly, isolating this test to the
one thing it's actually verifying (the exception handler), same
"patch the seam, not the whole stack" pattern test_graph_e2e.py already
uses for hybrid_search.
"""

from __future__ import annotations

import pytest

import app.api.routes_chat as routes_chat_module


async def _login(client, user, password) -> str:
    resp = await client.post("/auth/login", json={"email": user.email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_chat_returns_503_not_a_raw_500_on_graph_failure(client, support_agent_user, monkeypatch):
    user, password = support_agent_user
    token = await _login(client, user, password)

    async def _raise(*args, **kwargs):
        raise RuntimeError("simulated real LLM API outage")

    monkeypatch.setattr(routes_chat_module._fallback_graph, "ainvoke", _raise)

    resp = await client.post(
        "/chat",
        json={"query": "hello", "customer_id": 1},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 503
    body = resp.json()
    assert "detail" in body
    assert "temporarily unavailable" in body["detail"].lower()
    # The client-facing message must never leak the real internal exception text.
    assert "simulated real LLM API outage" not in body["detail"]
