"""
tests/integration/test_tracing_eval.py

Real, non-CI verification for Stage 8's core claim: a trace genuinely
lands in Langfuse, not just "no exception was raised while attempting to
send it" (§19 L4/L5 tier, mirrors Stage 7's real-Mailtrap eval test and
Stage 4's real-embedding-API eval tests). Silent failure is the exact
failure mode this stage was built defensively against — every wrapper in
tracing.py could catch and log an exception while still producing zero
real observations server-side, and no purely-mocked test can distinguish
that from success. This makes one real POST /chat call (real Azure
OpenAI, real Langfuse), then reads the trace back via Langfuse's own
REST API (client.api.trace.get) and asserts real observations exist.

A second, non-eval test in this file verifies the Postgres checkpointer
(§40) actually persists real graph execution — cheap and deterministic
(no paid API calls, just the disposable test Postgres this whole suite
already requires), so it runs in normal CI.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

import app.llm.structured_output as structured_output_module
import app.orchestration.nodes.doc_retrieval as doc_retrieval_module
from app.config import get_settings
from app.llm.azure_client import AzureLLMClient
from app.observability import tracing
from app.orchestration.checkpointer import build_checkpointer
from app.orchestration.graph import GRAPH_RECURSION_LIMIT, build_graph
from app.retrieval.vector_search import SearchResult


async def _login(client, user, password) -> str:
    resp = await client.post("/auth/login", json={"email": user.email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


_TERMINAL_SPAN_NAMES = {"respond", "escalate", "out_of_scope_refusal"}


async def _poll_for_trace(trace_id: str, *, attempts: int = 8, initial_delay: float = 1.5):
    """Langfuse's own ingestion is async even after flush() returns — a
    fixed sleep would either be too short (flaky) or wastefully long.
    Retries with backoff until the trace is readable via the REST API,
    matching this project's "prove convergence, don't guess a sleep"
    discipline (Stage 6).

    Real bug fix, found via a real failure in this project's own combined-
    suite coverage run: the original stopping condition was `if result.
    observations: return result` — ANY non-empty observations list, not
    necessarily a COMPLETE one. Langfuse's ingestion is eventually
    consistent and can deliver spans progressively, so this returned early
    with a real, non-empty but partial set (classify/router/doc_retrieval/
    hybrid_search/reflect — confirmed from the actual failing run's own
    observed_names) that never included a terminal node, because the
    terminal span simply hadn't landed yet when this function stopped
    polling. "Any observations exist" is too weak a signal for "the trace
    is done" — checking for a terminal node specifically (respond/escalate/
    out_of_scope_refusal, the one guaranteed to appear exactly once no
    matter which real path the graph took) is the actual convergence
    condition this function's own docstring already claims to check for.
    attempts/initial_delay also raised (6→8, 1.0s→1.5s, ~21s total budget
    → ~90s) since the real failing run's own request took 36s end-to-end
    before polling even started — the old budget had no margin left."""
    client = tracing.get_client()
    delay = initial_delay
    last_exc: Exception | None = None
    last_result = None
    for _ in range(attempts):
        try:
            result = client.api.trace.get(trace_id)
            last_result = result
            observed_names = {obs.name for obs in result.observations}
            if observed_names & _TERMINAL_SPAN_NAMES:
                return result
        except Exception as exc:  # noqa: BLE001 - genuinely "not landed yet", not a code bug
            last_exc = exc
        await asyncio.sleep(delay)
        delay *= 1.5
    observed = {obs.name for obs in last_result.observations} if last_result else set()
    raise AssertionError(
        f"Trace {trace_id} never showed a terminal span ({_TERMINAL_SPAN_NAMES}) via "
        f"client.api.trace.get() after {attempts} attempts — last observed span names: "
        f"{observed or '(none)'} (last error: {last_exc})"
    )


@pytest.mark.eval
@pytest.mark.asyncio
async def test_chat_trace_lands_in_langfuse_with_real_observations(
    client, support_agent_user, monkeypatch, cleanup_conversations, cleanup_escalations
):
    """Real end-to-end: no LLM/hybrid_search mocking (the whole point is
    exercising the real langfuse.openai-wrapped Azure client + real
    tracing.traced() spans). hybrid_search still runs for real too — the
    disposable test DB is empty, so it legitimately returns zero results;
    that's a real, valid path (low/no evidence), not a test artifact —
    which means this query can genuinely escalate for real.

    notify_human is mocked here (same pattern as test_escalation_mcp.py's
    test_notify_human_dispatched_via_background_tasks_not_awaited_inline)
    even though this whole test is already eval-marked: this test's job is
    proving the trace lands in Langfuse, not proving notify_human's real
    delivery mechanism (that's test_escalation_mcp.py's own eval-marked
    test) — without this mock, an eval run of this file could also make an
    undocumented, uncosted-for-in-this-file's-own-docstring real Mailtrap
    send whenever the empty-evidence path escalates."""
    monkeypatch.setattr(structured_output_module, "get_llm_client", lambda: AzureLLMClient())
    monkeypatch.setattr("app.api.routes_chat.notify_human", AsyncMock())

    user, password = support_agent_user
    token = await _login(client, user, password)

    resp = await client.post(
        "/chat",
        json={"query": "How do I reset my account password?", "customer_id": 1},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 200
    body = resp.json()
    cleanup_conversations.append(body["conversation_id"])

    trace_id = body["trace_id"]
    assert trace_id and not trace_id.startswith("trace_")  # a real langfuse.create_trace_id(), not the UUID fallback
    cleanup_escalations.append(trace_id)  # in case this real query escalated — matches EscalationLog.trace_id

    result = await _poll_for_trace(trace_id)

    observed_names = {obs.name for obs in result.observations}
    # classify always runs; the response is terminal at either respond,
    # escalate, or out_of_scope_refusal — whichever real path the LLM
    # actually took, at least one of these three closes the trace.
    assert "classify" in observed_names
    assert observed_names & {"respond", "escalate", "out_of_scope_refusal"}
    assert len(result.observations) >= 2  # more than just classify alone


@pytest.mark.asyncio
async def test_checkpointer_persists_real_graph_execution(monkeypatch):
    """§40: after a real .ainvoke() against a graph built with a real
    AsyncPostgresSaver, a real checkpoint row must be retrievable by
    thread_id — proving .setup() created genuinely usable tables, not
    just that it ran without throwing. Uses a fake LLM client / fake
    hybrid_search (same pattern as test_graph_e2e.py) since this test is
    only about the checkpointer, not about exercising real LLM calls."""

    class _FakeClient:
        def __init__(self, responses):
            self._responses = list(responses)

        async def generate(self, prompt, **kwargs):
            return self._responses.pop(0)

        async def generate_vision(self, image_bytes, prompt, **kwargs):
            raise NotImplementedError

    fake = _FakeClient(
        [
            '{"category": "usage", "severity_initial": "Low"}',
            '{"draft_answer": "Go to Account Settings.", "cited_source_ids": ["chunk_1"], '
            '"evidence_sufficient": true, "rewritten_query": null}',
            '{"confidence_score": 0.9, "groundedness_flag": true, "confidence_tier": "High"}',
        ]
    )
    monkeypatch.setattr(structured_output_module, "get_llm_client", lambda: fake)

    async def _fake_hybrid_search(query, filters=None):
        # A real evidence hit, not an empty list — with zero evidence,
        # reflect_node correctly forces a real retrieval retry (unrelated
        # to Stage 8), which would need extra queued responses here. This
        # matches test_graph_e2e.py's own working fixture for the same
        # reason.
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

    trace_id = tracing.safe_create_trace_id()
    settings = get_settings()

    async with build_checkpointer(settings.checkpointer_conn_string) as checkpointer:
        checkpointed_graph = build_graph(checkpointer=checkpointer)

        initial_state = {
            "query": "How do I reset my password?",
            "chat_history": [],
            "customer_id": 1,
            "handled_by_user_id": 1,
            "category": None,
            "conversation_id": "test-conv-checkpointer",
            "severity_initial": None,
            "severity_final": None,
            "retrieval_mode": None,
            "explicit_human_request": False,
            "retrieved_chunks": [],
            "retrieved_tables": [],
            "retrieved_diagrams": [],
            "sql_results": [],
            "confidence_score": None,
            "confidence_tier": None,
            "groundedness_flag": None,
            "retrieval_retry_count": 0,
            "reflection_loopback_count": 0,
            "escalation_flag": False,
            "flagged_for_review": False,
            "notification_sent": False,
            "escalation_reason": None,
            "human_handoff_summary": None,
            "final_answer": None,
            "sources": [],
            "trace_id": trace_id,
        }

        await checkpointed_graph.ainvoke(
            initial_state,
            config={"recursion_limit": GRAPH_RECURSION_LIMIT, "configurable": {"thread_id": trace_id}},
        )

        checkpoint_tuple = await checkpointer.aget_tuple({"configurable": {"thread_id": trace_id}})

    assert checkpoint_tuple is not None
    assert checkpoint_tuple.checkpoint is not None
