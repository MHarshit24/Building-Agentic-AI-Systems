"""
tests/unit/test_structured_output.py

L2 component tests (§19) for call_llm_structured(): first-call success,
retry-then-success, retry-then-fail. A dedicated fake client (not
MockLLMClient) is used so each scenario controls exactly what comes back
on the first vs. second call — no real LLM calls anywhere in this file.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel

from app.llm import structured_output as structured_output_module
from app.llm.structured_output import StructuredOutputError, call_llm_structured


class _DemoSchema(BaseModel):
    category: str
    confidence: float


class _QueuedFakeClient:
    """Returns each queued response in order, one per generate() call —
    lets a test dictate exactly what the first vs. retried call returns."""

    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.call_count = 0

    async def generate(self, prompt: str, **kwargs: Any) -> str:
        self.call_count += 1
        return self._responses.pop(0)

    async def generate_vision(self, image_bytes: bytes, prompt: str, **kwargs: Any) -> str:
        raise NotImplementedError("not exercised by these tests")


@pytest.fixture
def patch_llm_client(monkeypatch):
    def _patch(responses: list[str]) -> _QueuedFakeClient:
        fake = _QueuedFakeClient(responses)
        monkeypatch.setattr(structured_output_module, "get_llm_client", lambda: fake)
        return fake

    return _patch


@pytest.mark.asyncio
async def test_first_call_success(patch_llm_client):
    fake = patch_llm_client(['{"category": "incident", "confidence": 0.9}'])

    result = await call_llm_structured("classify this", _DemoSchema)

    assert result == _DemoSchema(category="incident", confidence=0.9)
    assert fake.call_count == 1


@pytest.mark.asyncio
async def test_retry_then_success(patch_llm_client):
    fake = patch_llm_client(
        [
            "I think this is an incident",  # malformed — not JSON at all
            '{"category": "incident", "confidence": 0.75}',  # valid on retry
        ]
    )

    result = await call_llm_structured("classify this", _DemoSchema)

    assert result == _DemoSchema(category="incident", confidence=0.75)
    assert fake.call_count == 2


@pytest.mark.asyncio
async def test_retry_then_fail_raises_structured_output_error(patch_llm_client):
    fake = patch_llm_client(
        [
            "not json either time",
            "still not valid json",
        ]
    )

    with pytest.raises(StructuredOutputError) as exc_info:
        await call_llm_structured("classify this", _DemoSchema)

    assert fake.call_count == 2
    assert exc_info.value.raw_output == "still not valid json"
    assert exc_info.value.validation_error is not None
