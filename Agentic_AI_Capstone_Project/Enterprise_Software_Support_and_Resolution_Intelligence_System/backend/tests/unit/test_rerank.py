"""
tests/unit/test_rerank.py

Regression test for a real, disclosed gap closed during the LLM-fallback
correctness audit (README §37): app/retrieval/rerank.py never passed
reasoning_effort at all, unlike every other real LLM call site in this
codebase (§13's explicit per-node tuning discipline). Confirmed to cause
no failure on either provider, but left every real rerank call untuned.
Fixed by adding REASONING_EFFORT = "low" (same tier doc_retrieval_node
uses). This test only verifies the fix's plumbing (call_llm_structured
is monkeypatched, no real LLM call) -- real behavior over Groq 120b was
separately verified with a live call during the audit itself.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import app.retrieval.rerank as rerank_module
from app.retrieval.rerank import RerankResponse, rerank
from app.retrieval.vector_search import SearchResult


def _make_result(row_id: int, text: str) -> SearchResult:
    return SearchResult(
        asset_type="chunk", asset_row_id=row_id, text=text,
        source_document="doc", section_header=None, page_number=1,
        product_version=None, category=None, score=0.5,
    )


@pytest.mark.asyncio
async def test_rerank_passes_reasoning_effort_low(monkeypatch):
    captured_kwargs = {}

    async def fake_call_llm_structured(prompt, schema, **kwargs):
        captured_kwargs.update(kwargs)
        return RerankResponse(rankings=[{"index": 0, "relevance_score": 9}, {"index": 1, "relevance_score": 2}])

    monkeypatch.setattr(rerank_module, "call_llm_structured", fake_call_llm_structured)
    monkeypatch.setattr(rerank_module, "get_settings", lambda: SimpleNamespace(llm_provider="azure"))

    results = [_make_result(1, "relevant"), _make_result(2, "irrelevant")]
    await rerank("some query", results, top_n=2)

    assert captured_kwargs.get("reasoning_effort") == "low"
