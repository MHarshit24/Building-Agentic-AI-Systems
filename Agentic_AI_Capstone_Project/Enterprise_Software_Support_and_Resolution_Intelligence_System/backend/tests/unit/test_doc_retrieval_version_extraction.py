"""
tests/unit/test_doc_retrieval_version_extraction.py

L1/L2 coverage (§19) for extract_product_version() and its wiring into
doc_retrieval.py's _run_one_attempt() filters dict — production-readiness
gap analysis, item B.5. No LLM/DB involved in the L1 tests; the L2 test
mocks both hybrid_search and call_llm_structured (same monkeypatch-the-
already-imported-reference pattern as test_graph_e2e.py).

_run_one_attempt() no longer takes a category parameter at all (removed
along with the category filter itself — see its own real, evidence-based
comment for why: a full-golden-set investigation found the hard category
pre-filter excluded the correct document 42% of the time it mattered,
including one category value structurally unmatchable against any real
document). product_version remains the only filter this module builds.
"""

from __future__ import annotations

import pytest

import app.orchestration.nodes.doc_retrieval as doc_retrieval_module
from app.orchestration.nodes.doc_retrieval import _run_one_attempt, extract_product_version
from app.schemas.agent_contracts import DocRetrievalOutput

# ---------------------------------------------------------------------------
# L1 — pure function
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "query,expected",
    [
        ("How do I configure OAuth for API v3.5?", "v3.5"),
        ("Is this supported in V3?", "v3"),
        ("We're on v3.5.1, does this apply?", "v3.5.1"),
        ("How do I reset my password?", None),
        ("I have 3.5 million records, is that too many?", None),  # no leading "v" — deliberately not parsed
        ("Ticket #v99 needs attention", "v99"),  # matches the shape; no corpus data exists for it (by design, see docstring)
    ],
)
def test_extract_product_version(query, expected):
    assert extract_product_version(query) == expected


# ---------------------------------------------------------------------------
# L2 — wiring into the filters dict passed to hybrid_search
# ---------------------------------------------------------------------------


@pytest.fixture
def patch_hybrid_search_capture_filters(monkeypatch):
    captured: dict = {}

    async def _fake_hybrid_search(query: str, filters: dict | None = None):
        captured["filters"] = filters
        return []

    monkeypatch.setattr(doc_retrieval_module, "hybrid_search", _fake_hybrid_search)
    return captured


@pytest.fixture
def patch_call_llm_structured(monkeypatch):
    async def _fake_call_llm_structured(prompt, schema, **kwargs):
        return DocRetrievalOutput(
            draft_answer="test answer",
            cited_source_ids=[],
            evidence_sufficient=True,
            rewritten_query=None,
        )

    monkeypatch.setattr(doc_retrieval_module, "call_llm_structured", _fake_call_llm_structured)


@pytest.mark.asyncio
async def test_run_one_attempt_includes_product_version_when_present(
    patch_hybrid_search_capture_filters, patch_call_llm_structured
):
    await _run_one_attempt("How do I configure OAuth for API v3.5?", history=[], scope_note="")

    assert patch_hybrid_search_capture_filters["filters"] == {"product_version": "v3.5"}


@pytest.mark.asyncio
async def test_run_one_attempt_filters_none_when_nothing_extracted(
    patch_hybrid_search_capture_filters, patch_call_llm_structured
):
    await _run_one_attempt("How do I reset my password?", history=[], scope_note="")

    assert patch_hybrid_search_capture_filters["filters"] is None
