"""
tests/integration/test_chat_stream.py

L2/L3 coverage (§19) for POST /chat/stream — A6, frontend integration
pass. Confirms:
  1. The SSE stream emits one `event: node` frame per graph node actually
     executed, terminated by one `event: done` frame.
  2. That `done` payload is behaviorally identical to what POST /chat
     returns for the same input (modulo trace_id/conversation_id, which
     are inherently fresh per call) — the actual proof that
     _persist_and_finalize()'s extraction didn't change behavior.
  3. A6 plan's flagged empirical risk #1: for Hybrid/Critical mode's
     concurrent Send fan-out (doc_retrieval_node + account_validation_node),
     both nodes' events reach the client as separate `event: node` frames
     regardless of whether LangGraph batches them into one `step` dict or
     two — routes_chat.py's `_chat_event_stream` iterates `step.items()`
     either way, so this test proves the observable frontend-facing
     outcome holds, which is the property that actually matters.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

import app.llm.structured_output as structured_output_module
import app.orchestration.nodes.doc_retrieval as doc_retrieval_module
from app.retrieval.vector_search import SearchResult


class _QueuedFakeClient:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.call_count = 0

    async def generate(self, prompt: str, **kwargs: Any) -> str:
        self.call_count += 1
        return self._responses.pop(0)

    async def generate_vision(self, image_bytes: bytes, prompt: str, **kwargs: Any) -> str:
        raise NotImplementedError("not exercised by this test")


class _RoutedFakeClient:
    """Same dispatch-by-prompt-marker technique as
    test_graph_parallel_fanout.py's own fake — needed once two nodes can
    call generate() concurrently, since call order isn't deterministic."""

    MARKERS = [
        ("cited_source_ids", "doc_retrieval"),
        ("narrative", "account_validation"),
        ("severity_reasoning", "incident_severity"),
        ("groundedness_flag", "reflect"),
        ("severity_initial", "classify"),
    ]

    def __init__(self, classify_response: str, canned: dict[str, str]) -> None:
        self._classify_response = classify_response
        self._canned = canned
        self.call_counts: dict[str, int] = {name: 0 for _, name in self.MARKERS}

    def _identify(self, prompt: str) -> str:
        lowered = prompt.lower()
        for marker, name in self.MARKERS:
            if marker in lowered:
                return name
        raise AssertionError(f"could not identify which node this prompt belongs to: {prompt[:200]!r}")

    async def generate(self, prompt: str, **kwargs: Any) -> str:
        name = self._identify(prompt)
        self.call_counts[name] += 1
        if name == "classify":
            return self._classify_response
        return self._canned[name]

    async def generate_vision(self, image_bytes: bytes, prompt: str, **kwargs: Any) -> str:
        raise NotImplementedError("not exercised by this test")


@pytest.fixture
def patch_hybrid_search_with_one_result(monkeypatch):
    async def _fake_hybrid_search(query: str, filters: dict | None = None):
        return [
            SearchResult(
                asset_type="chunk",
                asset_row_id=1,
                text="To reset your password, go to Account Settings and click 'Reset Password'.",
                source_document="Test Doc",
                section_header="Account Setup",
                page_number=3,
                product_version=None,
                category="usage",
                score=0.5,
            )
        ]

    monkeypatch.setattr(doc_retrieval_module, "hybrid_search", _fake_hybrid_search)


async def _login(client, user, password) -> str:
    resp = await client.post("/auth/login", json={"email": user.email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


async def _collect_sse_events(client, headers: dict, json_body: dict) -> list[tuple[str, dict]]:
    """Minimal hand-rolled SSE frame parser — same shape a fetch()-based
    frontend client parses (A6 plan: no EventSource, no client library)."""
    events: list[tuple[str, dict]] = []
    event_name: str | None = None
    data_lines: list[str] = []

    async with client.stream("POST", "/chat/stream", json=json_body, headers=headers) as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        async for line in resp.aiter_lines():
            if line.startswith("event:"):
                event_name = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                data_lines.append(line.split(":", 1)[1].strip())
            elif line == "":
                if event_name is not None:
                    data = json.loads("".join(data_lines)) if data_lines else {}
                    events.append((event_name, data))
                event_name, data_lines = None, []
    return events


@pytest.mark.asyncio
async def test_chat_stream_emits_node_events_then_done_matching_unary_chat(
    client, support_agent_user, patch_hybrid_search_with_one_result, cleanup_conversations, monkeypatch
):
    user, password = support_agent_user
    token = await _login(client, user, password)
    headers = {"Authorization": f"Bearer {token}"}

    canned_responses = [
        '{"category": "usage", "severity_initial": "Low"}',
        '{"draft_answer": "To reset your password, go to Account Settings and click '
        '\'Reset Password\'.", "cited_source_ids": ["chunk_1"], "evidence_sufficient": true, '
        '"rewritten_query": null}',
        '{"confidence_score": 0.95, "groundedness_flag": true, "confidence_tier": "High"}',
    ]

    # Streamed call.
    fake_stream = _QueuedFakeClient(list(canned_responses))
    monkeypatch.setattr(structured_output_module, "get_llm_client", lambda: fake_stream)
    events = await _collect_sse_events(
        client, headers, {"query": "How do I reset my password?", "customer_id": 1}
    )

    node_names = [data["node"] for name, data in events if name == "node"]
    for expected_node in ("classify_node", "router_node", "doc_retrieval_node", "reflect_node", "respond_node"):
        assert expected_node in node_names, f"expected {expected_node!r} among streamed node events, got {node_names}"

    assert events[-1][0] == "done"
    stream_body = events[-1][1]
    cleanup_conversations.append(stream_body["conversation_id"])

    assert stream_body["answer"]
    assert stream_body["category"] == "usage"
    assert stream_body["confidence_tier"] == "High"
    assert stream_body["escalated"] is False
    assert stream_body["retrieval_retry_count"] == 0
    assert stream_body["reflection_loopback_count"] == 0

    # Unary call, identical canned responses (fresh queue), for equivalence.
    fake_unary = _QueuedFakeClient(list(canned_responses))
    monkeypatch.setattr(structured_output_module, "get_llm_client", lambda: fake_unary)
    unary_resp = await client.post(
        "/chat",
        json={"query": "How do I reset my password?", "customer_id": 1},
        headers=headers,
    )
    assert unary_resp.status_code == 200
    unary_body = unary_resp.json()
    cleanup_conversations.append(unary_body["conversation_id"])

    # Identical in every field except the two that are inherently
    # per-call-unique (trace_id, conversation_id) — this is the actual
    # proof that extracting _persist_and_finalize() didn't change behavior.
    ignore = {"trace_id", "conversation_id"}
    assert {k: v for k, v in stream_body.items() if k not in ignore} == {
        k: v for k, v in unary_body.items() if k not in ignore
    }


@pytest.mark.asyncio
async def test_chat_stream_hybrid_mode_emits_both_concurrent_branch_events(
    client, support_agent_user, make_customer, patch_hybrid_search_with_one_result, cleanup_conversations, monkeypatch
):
    """A6 plan's flagged empirical risk #1, resolved: whether LangGraph's
    astream(stream_mode="updates") batches the Send-fanned doc_retrieval_node
    + account_validation_node pair into one `step` dict or yields them
    separately, both node names must still reach the client as their own
    `event: node` frame."""
    user, password = support_agent_user
    token = await _login(client, user, password)
    customer = await make_customer(company_name="Acme Corp")
    headers = {"Authorization": f"Bearer {token}"}

    fake = _RoutedFakeClient(
        classify_response='{"category": "incident", "severity_initial": "High", "explicit_human_request": false}',
        canned={
            "doc_retrieval": (
                '{"draft_answer": "This looks related to a known incident.", '
                '"cited_source_ids": ["chunk_1"], "evidence_sufficient": true, "rewritten_query": null}'
            ),
            # cited_record_ids must reference the real customer_id — frontend
            # integration pass: sql sources are now filtered by this, same
            # mechanism doc_retrieval already used for chunk/table/diagram.
            "account_validation": (
                '{"narrative": "Your account is active.", '
                f'"cited_record_ids": ["customers_{customer.customer_id}"], '
                '"evidence_sufficient": true}'
            ),
            "incident_severity": '{"severity_final": "High", "severity_reasoning": "Matches an active incident."}',
            "reflect": '{"confidence_score": 0.9, "groundedness_flag": true, "confidence_tier": "High"}',
        },
    )

    import app.llm.structured_output as so_module

    original_get_client = so_module.get_llm_client
    so_module.get_llm_client = lambda: fake
    try:
        events = await _collect_sse_events(
            client,
            headers,
            {"query": "Is my performance issue related to a known incident?", "customer_id": customer.customer_id},
        )
    finally:
        so_module.get_llm_client = original_get_client

    node_names = [data["node"] for name, data in events if name == "node"]
    assert "doc_retrieval_node" in node_names
    assert "account_validation_node" in node_names

    assert events[-1][0] == "done"
    done_body = events[-1][1]
    cleanup_conversations.append(done_body["conversation_id"])
    assert done_body["retrieval_mode"] == "Hybrid"
    sql_sources = [s for s in done_body["sources"] if s["type"] == "sql"]
    chunk_sources = [s for s in done_body["sources"] if s["type"] == "chunk"]
    assert sql_sources, "expected at least one sql-type source — account_validation_node's branch never ran"
    assert chunk_sources, "expected at least one chunk-type source — doc_retrieval_node's branch never ran"


@pytest.mark.asyncio
async def test_chat_stream_requires_authentication(client):
    resp = await client.post("/chat/stream", json={"query": "hello", "customer_id": 1})
    assert resp.status_code in (401, 403)
