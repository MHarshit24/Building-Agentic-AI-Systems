"""
tests/integration/test_no_infinite_loop.py

§5's loop-prevention guarantee, tested adversarially: an LLM that NEVER
produces sufficient/grounded evidence, on every single call, must still
reach a real terminal state (escalate_node -> END) within a bounded
number of steps — not hang, not exceed recursion_limit, not silently
loop forever.

This test also exercises the disposable per-session test database
(tests/conftest.py) genuinely empty, rather than monkeypatching
hybrid_search — an empty corpus is itself a realistic trigger for
"evidence never sufficient," and lets this test double as a real check
that doc_retrieval_node's internal retry and reflect's loop-back both
terminate correctly against real (if empty) retrieval calls, not just
canned ones.

Exact call-count accounting for the queued fake LLM client (7 total),
spelled out so a future change to the loop-prevention logic that breaks
this bound fails loudly here instead of silently regressing:
  1. classify_node                                          (call 1)
  2. doc_retrieval_node, entry 1, attempt 1                  (call 2)
     -> evidence_sufficient=false, top_score=0.0 < threshold,
        retrieval_retry_count(0) < 1, rewritten_query set -> retries
  3. doc_retrieval_node, entry 1, attempt 2 (internal retry)  (call 3)
     -> retrieval_retry_count becomes 1
  4. reflect_node, entry 1                                    (call 4)
     -> groundedness_flag=false, reflection_loopback_count(0) < 1
        -> loops back to doc_retrieval_node
  5. doc_retrieval_node, entry 2 (loop-back re-entry)          (call 5)
     -> reflection_loopback_count becomes 1; retrieval_retry_count is
        already 1, so NO further internal retry this entry (1 < 1 is
        false) — only one attempt
  6. reflect_node, entry 2                                     (call 6)
     -> groundedness_flag=false again, but reflection_loopback_count(1)
        < 1 is false now -> does NOT loop back again; falls through to
        decide_action(effective_severity, confidence_tier="Low") ->
        ("escalate", False) per §6.1's "Low confidence always escalates"
  7. escalate_node                                            (call 7)
     -> Stage 7: escalate_node makes a real LLM call now (§39.3's
        EscalationOutput), unlike Stage 5's minimal, non-LLM version this
        count originally documented (Deviation A) — updated here rather
        than left stale.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest


class _QueuedFakeClient:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.call_count = 0

    async def generate(self, prompt: str, **kwargs: Any) -> str:
        self.call_count += 1
        if not self._responses:
            raise AssertionError(
                f"LLM called an unexpected {self.call_count}th time — the graph did not "
                "terminate within the expected bounded step count."
            )
        return self._responses.pop(0)

    async def generate_vision(self, image_bytes: bytes, prompt: str, **kwargs: Any) -> str:
        raise NotImplementedError("not exercised by this test")


ADVERSARIAL_DOC_RETRIEVAL_RESPONSE = (
    '{"draft_answer": "I do not have enough information to answer that.", '
    '"cited_source_ids": [], "evidence_sufficient": false, '
    '"rewritten_query": "a slightly different phrasing of the same query"}'
)
ADVERSARIAL_REFLECT_RESPONSE = (
    '{"confidence_score": 0.1, "groundedness_flag": false, "confidence_tier": "Low"}'
)


@pytest.mark.asyncio
async def test_always_ungrounded_low_confidence_reaches_escalate_within_bounded_steps(
    client, support_agent_user, monkeypatch, cleanup_conversations, cleanup_escalations
):
    import app.llm.structured_output as structured_output_module

    # notify_human is mocked here (same pattern as test_escalation_mcp.py's
    # test_notify_human_dispatched_via_background_tasks_not_awaited_inline)
    # — this test deliberately escalates, which without this mock spawns a
    # real MCP subprocess and makes a real Mailtrap send via routes_chat.py's
    # BackgroundTasks.add_task(notify_human, ...) on every normal run, not
    # just eval-marked ones. This test's own job is proving bounded
    # termination, not exercising notify_human's real delivery mechanism.
    monkeypatch.setattr("app.api.routes_chat.notify_human", AsyncMock())

    user, password = support_agent_user
    login_resp = await client.post("/auth/login", json={"email": user.email, "password": password})
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]

    fake = _QueuedFakeClient(
        [
            '{"category": "usage", "severity_initial": "Low"}',
            ADVERSARIAL_DOC_RETRIEVAL_RESPONSE,
            ADVERSARIAL_DOC_RETRIEVAL_RESPONSE,
            ADVERSARIAL_REFLECT_RESPONSE,
            ADVERSARIAL_DOC_RETRIEVAL_RESPONSE,
            ADVERSARIAL_REFLECT_RESPONSE,
            '{"escalation_reason": "Low confidence.", "human_handoff_summary": "Adversarial test case."}',
        ]
    )
    monkeypatch.setattr(structured_output_module, "get_llm_client", lambda: fake)

    resp = await client.post(
        "/chat",
        json={"query": "Some query the empty test corpus can never answer", "customer_id": 1},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 200
    body = resp.json()
    cleanup_conversations.append(body["conversation_id"])
    cleanup_escalations.append(body["trace_id"])

    assert body["escalated"] is True
    assert body["confidence_tier"] == "Low"
    assert body["answer"]  # escalate_node's fixed handoff note, or the last draft_answer
    assert fake.call_count == 7, (
        f"expected exactly 7 LLM calls (including escalate_node's own call, Stage 7), got "
        f"{fake.call_count} — either a loop-count guard isn't capping correctly, or the graph "
        "is taking more/fewer steps than this test's documented accounting expects."
    )
