"""
tests/integration/test_graph_e2e.py

Full end-to-end test of the Stage 5 always-run path, over real HTTP
(POST /chat -> the compiled LangGraph -> a persisted Conversation/Message
pair), under LLM_PROVIDER=mock (§19 — no real LLM calls, no VCR needed).

Two things are monkeypatched, at two different layers, for two different
reasons:
  1. app.llm.structured_output.get_llm_client — a queued fake client (same
     pattern as test_structured_output.py / test_classify.py) hands back
     exactly the classify -> doc_retrieval -> reflect responses this test
     wants, in order. The real MockLLMClient's keyword-sniffed canned
     responses aren't used here deliberately: its "incident"/"security"
     branch would actually fire for EVERY classify_node call (those two
     words are baked into classify_v1.py's own static OUTPUT_SCHEMA/
     ROLE_INSTRUCTIONS text, present in every prompt regardless of the
     query), which is a real, separate latent bug in mock_client.py worth
     fixing on its own — this test sidesteps it entirely rather than
     depending on it.
  2. app.orchestration.nodes.doc_retrieval.hybrid_search — the disposable
     per-session test database (tests/conftest.py) is freshly migrated and
     EMPTY, so a real hybrid_search() call would always return zero
     results. Patching doc_retrieval's own already-imported reference to
     it with one fixed SearchResult lets this test exercise a genuine
     "evidence retrieved, cited, grounded, respond" path without needing
     a real ingested corpus in the test database.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

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


@pytest.fixture
def patch_llm_client(monkeypatch):
    def _patch(responses: list[str]) -> _QueuedFakeClient:
        fake = _QueuedFakeClient(responses)
        monkeypatch.setattr(structured_output_module, "get_llm_client", lambda: fake)
        return fake

    return _patch


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


@pytest.mark.asyncio
async def test_chat_happy_path_grounded_answer_is_respond_terminal(
    client, support_agent_user, patch_llm_client, patch_hybrid_search_with_one_result, cleanup_conversations
):
    user, password = support_agent_user
    token = await _login(client, user, password)

    patch_llm_client(
        [
            '{"category": "usage", "severity_initial": "Low"}',
            '{"draft_answer": "To reset your password, go to Account Settings and click '
            '\'Reset Password\'.", "cited_source_ids": ["chunk_1"], "evidence_sufficient": true, '
            '"rewritten_query": null}',
            '{"confidence_score": 0.95, "groundedness_flag": true, "confidence_tier": "High"}',
        ]
    )

    resp = await client.post(
        "/chat",
        json={"query": "How do I reset my password?", "customer_id": 1},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 200
    body = resp.json()
    cleanup_conversations.append(body["conversation_id"])

    assert set(body.keys()) == {
        "answer", "category", "severity", "retrieval_mode", "confidence_score",
        "confidence_tier", "sources", "escalated", "flagged_for_review", "trace_id",
        "conversation_id",
        # A4 (frontend integration pass): both already lived in
        # SupportGraphState but were never surfaced in ChatResponse before.
        "retrieval_retry_count", "reflection_loopback_count",
    }
    assert body["answer"]
    assert body["category"] == "usage"
    assert body["confidence_tier"] == "High"
    assert body["confidence_score"] is not None
    assert body["escalated"] is False
    assert body["retrieval_retry_count"] == 0
    assert body["reflection_loopback_count"] == 0
    assert body["sources"] == [
        {
            "type": "chunk",
            "source_document": "Test Doc",
            "section_header": "Account Setup",
            "page_number": 3,
            # table/record_id (Stage 6, sql-type sources) are always present
            # in the serialized response, None for non-sql source types.
            "table": None,
            "record_id": None,
        }
    ]

    # A3 (frontend integration pass): the assistant Message row now persists
    # the full per-turn reasoning trace, not just confidence_tier/sources/
    # trace_id — reopening this conversation must show the same values
    # ChatResponse just returned live, not a stripped-down history view.
    conv_resp = await client.get(f"/conversations/{body['conversation_id']}", headers={"Authorization": f"Bearer {token}"})
    assert conv_resp.status_code == 200
    assistant_message = next(m for m in conv_resp.json()["messages"] if m["role"] == "assistant")
    assert assistant_message["category"] == body["category"]
    assert assistant_message["severity"] == body["severity"]
    assert assistant_message["retrieval_mode"] == body["retrieval_mode"]
    assert assistant_message["confidence_score"] == body["confidence_score"]
    assert assistant_message["flagged_for_review"] == body["flagged_for_review"]


@pytest.mark.asyncio
async def test_chat_strips_inline_citation_markers_from_answer(
    client, support_agent_user, patch_llm_client, patch_hybrid_search_with_one_result, cleanup_conversations
):
    """Regression test for a real bug found via manual QA: doc_retrieval's
    LLM sometimes embeds [chunk_N]/[table_N] citation tags directly in
    draft_answer despite the prompt asking for cited_source_ids only —
    routes_chat.py's _strip_citation_markers() is the deterministic safety
    net that guarantees these never reach the user, in both the live API
    response and the persisted (later reloadable) message content."""
    user, password = support_agent_user
    token = await _login(client, user, password)

    patch_llm_client(
        [
            '{"category": "usage", "severity_initial": "Low"}',
            '{"draft_answer": "Send header X-API-Key: your_key [table_9][chunk_21]. This '
            'resolves the issue [chunk_15].", "cited_source_ids": ["chunk_1"], '
            '"evidence_sufficient": true, "rewritten_query": null}',
            '{"confidence_score": 0.95, "groundedness_flag": true, "confidence_tier": "High"}',
        ]
    )

    resp = await client.post(
        "/chat",
        json={"query": "How do I authenticate?", "customer_id": 1},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 200
    body = resp.json()
    cleanup_conversations.append(body["conversation_id"])

    assert "[table_9]" not in body["answer"]
    assert "[chunk_21]" not in body["answer"]
    assert "[chunk_15]" not in body["answer"]
    assert body["answer"] == "Send header X-API-Key: your_key. This resolves the issue."

    conv_resp = await client.get(
        f"/conversations/{body['conversation_id']}", headers={"Authorization": f"Bearer {token}"}
    )
    assistant_message = next(m for m in conv_resp.json()["messages"] if m["role"] == "assistant")
    assert "[chunk_" not in assistant_message["content"]
    assert "[table_" not in assistant_message["content"]


@pytest.mark.asyncio
async def test_chat_out_of_scope_short_circuits_before_retrieval(
    client, support_agent_user, patch_llm_client, cleanup_conversations
):
    """Layer A (§31): classify_node alone is enough to refuse — doc_retrieval
    is never reached, so only one canned response is queued; if the graph
    incorrectly proceeded past the refusal, the second call would raise
    IndexError on the exhausted queue."""
    user, password = support_agent_user
    token = await _login(client, user, password)

    fake = patch_llm_client(['{"category": "out_of_scope", "severity_initial": "Low"}'])

    resp = await client.post(
        "/chat",
        json={"query": "What's the capital of France?", "customer_id": 1},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 200
    body = resp.json()
    cleanup_conversations.append(body["conversation_id"])

    assert body["category"] == "out_of_scope"
    assert body["sources"] == []
    assert body["answer"]
    assert fake.call_count == 1


@pytest.mark.asyncio
async def test_chat_explicit_human_request_short_circuits_to_escalate_before_retrieval(
    client, support_agent_user, patch_llm_client, monkeypatch, cleanup_conversations, cleanup_escalations
):
    """README §5's 'explicit request for human support' escalation trigger,
    full graph run: classify_node alone (category="usage",
    severity_initial="Low" — an otherwise clean, unescalated RAG path) is
    enough to send this straight to escalate_node — doc_retrieval_node is
    never invoked. Exactly two canned responses are queued (classify, then
    escalate_node's own LLM call — Stage 7 upgraded it from a non-LLM
    formatter to a real agent, §39.3); if the graph incorrectly proceeded
    to doc_retrieval_node, the second LLM call would raise an
    "unidentifiable prompt"-shaped failure rather than matching
    doc_retrieval's schema (same "prove it, don't assume it" technique as
    the out-of-scope test above).

    notify_human is mocked here (same pattern as test_escalation_mcp.py's
    test_notify_human_dispatched_via_background_tasks_not_awaited_inline)
    — this test triggers a real escalation via routes_chat.py's
    BackgroundTasks.add_task(notify_human, ...), which without this mock
    spawns a real MCP subprocess and makes a real Mailtrap send on every
    normal run, not just eval-marked ones. This test's own job is proving
    the escalation routing decision, not exercising notify_human's real
    delivery mechanism (that's test_escalation_mcp.py's job)."""
    monkeypatch.setattr("app.api.routes_chat.notify_human", AsyncMock())

    user, password = support_agent_user
    token = await _login(client, user, password)

    fake = patch_llm_client(
        [
            '{"category": "usage", "severity_initial": "Low", "explicit_human_request": true}',
            '{"escalation_reason": "Customer explicitly requested a human.", '
            '"human_handoff_summary": "Customer asked to speak with a human support agent."}',
        ]
    )

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
    assert "connected" in body["answer"].lower()
    assert fake.call_count == 2


@pytest.mark.asyncio
async def test_chat_requires_authentication(client):
    resp = await client.post("/chat", json={"query": "hello", "customer_id": 1})
    assert resp.status_code in (401, 403)
