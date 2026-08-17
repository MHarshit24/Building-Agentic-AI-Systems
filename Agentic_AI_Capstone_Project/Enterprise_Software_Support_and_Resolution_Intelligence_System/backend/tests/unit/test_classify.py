"""
tests/unit/test_classify.py

L2 component test (§19) for classify_node: a fake queued LLM client
(same pattern as test_structured_output.py) stands in for the real
Azure client, so this asserts classify_node's own wiring — prompt
assembly, call_llm_structured usage, and the state-update shape — not
real model behavior.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.llm import structured_output as structured_output_module
from app.orchestration.nodes.classify import classify_node


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
def patch_llm_client(monkeypatch):
    def _patch(responses: list[str]) -> _QueuedFakeClient:
        fake = _QueuedFakeClient(responses)
        monkeypatch.setattr(structured_output_module, "get_llm_client", lambda: fake)
        return fake

    return _patch


@pytest.mark.asyncio
async def test_classify_node_returns_category_and_severity(patch_llm_client):
    fake = patch_llm_client(['{"category": "billing", "severity_initial": "Medium"}'])

    state = {"query": "Why was I charged twice this month?", "chat_history": []}
    result = await classify_node(state)

    assert result == {"category": "billing", "severity_initial": "Medium", "explicit_human_request": False}
    assert fake.call_count == 1
    assert fake.last_kwargs.get("reasoning_effort") == "minimal"


@pytest.mark.asyncio
async def test_classify_node_out_of_scope(patch_llm_client):
    patch_llm_client(['{"category": "out_of_scope", "severity_initial": "Low"}'])

    state = {"query": "What's the capital of France?", "chat_history": []}
    result = await classify_node(state)

    assert result["category"] == "out_of_scope"


@pytest.mark.asyncio
async def test_classify_node_writes_only_its_own_fields(patch_llm_client):
    patch_llm_client(['{"category": "usage", "severity_initial": "Low"}'])

    state = {"query": "How do I reset my password?", "chat_history": []}
    result = await classify_node(state)

    assert set(result.keys()) == {"category", "severity_initial", "explicit_human_request"}


@pytest.mark.asyncio
async def test_classify_node_passes_through_explicit_human_request_true(patch_llm_client):
    """README §5's 'explicit request for human support' escalation trigger:
    classify_node must pass ClassificationOutput.explicit_human_request
    straight through into its state write, same pattern as category/
    severity_initial — this only tests the pass-through wiring, not
    whether a real model would set it correctly for this query (that's
    what classify_v1.py's few-shot examples are for, verified separately
    against a real model, not a canned fake client)."""
    patch_llm_client(
        ['{"category": "usage", "severity_initial": "Low", "explicit_human_request": true}']
    )

    state = {"query": "Can you connect me with a human support agent?", "chat_history": []}
    result = await classify_node(state)

    assert result["explicit_human_request"] is True


@pytest.mark.asyncio
async def test_classify_node_passes_through_explicit_human_request_false(patch_llm_client):
    patch_llm_client(
        ['{"category": "usage", "severity_initial": "Medium", "explicit_human_request": false}']
    )

    state = {"query": "This is really frustrating, nothing works.", "chat_history": []}
    result = await classify_node(state)

    assert result["explicit_human_request"] is False


@pytest.mark.asyncio
async def test_classify_node_explicit_human_request_defaults_false_when_omitted(patch_llm_client):
    """ClassificationOutput.explicit_human_request has a Python-level
    default (agent_contracts.py) precisely so canned responses that
    predate this field — like this one — still validate; Azure's own
    strict-mode schema still forces a real model to always return it."""
    patch_llm_client(['{"category": "billing", "severity_initial": "Medium"}'])

    state = {"query": "Why was I charged twice this month?", "chat_history": []}
    result = await classify_node(state)

    assert result["explicit_human_request"] is False
