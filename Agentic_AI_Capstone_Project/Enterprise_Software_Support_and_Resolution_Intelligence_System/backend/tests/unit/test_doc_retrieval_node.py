"""
tests/unit/test_doc_retrieval_node.py

Regression coverage for two real bugs found via manual QA (frontend
testing session) and fixed in doc_retrieval.py/doc_retrieval_v1.py — both
pure-Python/prompt-shape fixes, no real LLM behavior change to verify,
unlike the classify_v1.py/account_validation_v1.py fixes covered
elsewhere with real-call regression tests.

Bug 1 — stale "Route" badge: retrieval_mode is set once by router_node
right after classify_node and never touched again. A query originally
routed "SQL" whose SQL-alone answer reflect_node judges ungrounded loops
back to doc_retrieval_node (the ONLY way doc_retrieval_node ever runs for
an originally-SQL-routed query) — real documentation evidence gets
fetched and cited, but the UI kept showing "Route: SQL". Fixed by having
doc_retrieval_node promote retrieval_mode to "Hybrid" specifically when
it's re-entered (confidence_score already set, i.e. reflect_node already
ran once) with retrieval_mode=="SQL" in state — the one condition that
uniquely identifies this fallback path.

Bug 2 — self-contradictory final answers: doc_retrieval_node's own draft
overwrites final_answer unconditionally, blind to any account_narrative
already computed by account_validation_node earlier in the same request
(SQL-alone mode, before the reflect-loopback retry). reflect.py's
_merge_final_answer() then naively concatenates the fresh (denial) draft
with the stale (correct) narrative, producing "I don't have enough
information... [correct answer]" in one response. Fixed by passing
account_narrative into doc_retrieval_node's own prompt as account_context
when present, so its draft stops issuing a blanket "I don't have account
access" denial that later gets contradicted by real account data shown
right next to it.
"""

from __future__ import annotations

from typing import Any

import pytest

import app.orchestration.nodes.doc_retrieval as doc_retrieval_module
from app.orchestration.nodes.doc_retrieval import doc_retrieval_node
from app.prompts.doc_retrieval_v1 import ACCOUNT_CONTEXT_NOTE, build_prompt
from app.schemas.agent_contracts import DocRetrievalOutput


def _base_state(**overrides) -> dict:
    state: dict = {
        "query": "What is this customer's SLA level and account status?",
        "chat_history": [],
        "retrieval_retry_count": 0,
        "reflection_loopback_count": 0,
        "retrieval_mode": "SQL",
        "confidence_score": None,
        "account_narrative": None,
    }
    state.update(overrides)
    return state


@pytest.fixture
def patch_doc_retrieval_dependencies(monkeypatch):
    """Mocks every I/O dependency doc_retrieval_node touches: hybrid_search
    (no real corpus query), call_llm_structured (no real LLM call, and
    captures the prompt actually built so account_context wiring can be
    asserted), and embed_text (raises ValueError -> Layer B scope check
    fails open, same "no embedded corpus yet" path already covered by
    doc_retrieval.py's own docstring — avoids needing to also fake
    get_cached_centroid/is_in_scope for a check unrelated to either bug
    under test here)."""
    captured: dict[str, Any] = {}

    async def _fake_hybrid_search(query: str, filters: dict | None = None):
        return []

    async def _fake_embed_text(text: str):
        raise ValueError("no embedded corpus in this test")

    async def _fake_call_llm_structured(prompt, schema, **kwargs):
        captured["prompt"] = prompt
        return DocRetrievalOutput(
            draft_answer="I don't have enough information to answer that.",
            cited_source_ids=[],
            evidence_sufficient=True,
            rewritten_query=None,
        )

    monkeypatch.setattr(doc_retrieval_module, "hybrid_search", _fake_hybrid_search)
    monkeypatch.setattr(doc_retrieval_module, "embed_text", _fake_embed_text)
    monkeypatch.setattr(doc_retrieval_module, "call_llm_structured", _fake_call_llm_structured)
    return captured


# ---------------------------------------------------------------------------
# Bug 1 — retrieval_mode promotion on the SQL-origin loopback re-entry
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sql_origin_loopback_promotes_retrieval_mode_to_hybrid(patch_doc_retrieval_dependencies):
    """The exact real scenario: retrieval_mode="SQL", confidence_score
    already set by a prior reflect_node pass (i.e. this is a loopback
    re-entry, not doc_retrieval_node's first run) -> Route badge must
    reflect that real RAG evidence was also fetched."""
    state = _base_state(retrieval_mode="SQL", confidence_score=0.4)

    result = await doc_retrieval_node(state)

    assert result["retrieval_mode"] == "Hybrid"


@pytest.mark.asyncio
async def test_fresh_sql_mode_entry_does_not_promote_retrieval_mode(patch_doc_retrieval_dependencies):
    """Defensive edge, not a real graph path (SQL mode never includes
    doc_retrieval_node in its initial fan-out) but worth pinning: a FRESH
    call (confidence_score still None) must never promote, since that's
    not the loopback condition the fix targets."""
    state = _base_state(retrieval_mode="SQL", confidence_score=None)

    result = await doc_retrieval_node(state)

    assert "retrieval_mode" not in result


@pytest.mark.asyncio
async def test_rag_origin_loopback_does_not_touch_retrieval_mode(patch_doc_retrieval_dependencies):
    """A RAG-mode query looping back to doc_retrieval_node is just a
    same-node retry, not a mode change — must stay a no-op."""
    state = _base_state(retrieval_mode="RAG", confidence_score=0.4)

    result = await doc_retrieval_node(state)

    assert "retrieval_mode" not in result


@pytest.mark.asyncio
async def test_hybrid_origin_loopback_does_not_touch_retrieval_mode(patch_doc_retrieval_dependencies):
    """Hybrid/Critical already include doc_retrieval_node in their initial
    fan-out — a loopback re-entry there is a same-mode retry too."""
    state = _base_state(retrieval_mode="Hybrid", confidence_score=0.4)

    result = await doc_retrieval_node(state)

    assert "retrieval_mode" not in result


# ---------------------------------------------------------------------------
# Bug 2 — account_narrative passed through as prompt context
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_account_narrative_is_forwarded_into_the_prompt_when_present(patch_doc_retrieval_dependencies):
    """Deliberate design choice, not a gap: doc_retrieval_node forwards
    account_narrative's mere PRESENCE (truthy check), not its actual text
    content — this agent's job stays strictly "answer from docs only," so
    it gets told account data exists elsewhere (to stop it denying access
    to it) without being shown the narrative itself, which would risk it
    mixing account facts into a doc-only draft. ACCOUNT_CONTEXT_NOTE
    appearing in the built prompt is therefore the correct thing to
    assert, not the narrative's own text."""
    state = _base_state(
        retrieval_mode="SQL",
        confidence_score=0.4,
        account_narrative="Your account (Gamma Retail) is on the Basic SLA level and Trial status.",
    )

    await doc_retrieval_node(state)

    prompt = patch_doc_retrieval_dependencies["prompt"]
    assert ACCOUNT_CONTEXT_NOTE in prompt


@pytest.mark.asyncio
async def test_no_account_context_note_when_account_narrative_absent(patch_doc_retrieval_dependencies):
    state = _base_state(retrieval_mode="RAG", confidence_score=None, account_narrative=None)

    await doc_retrieval_node(state)

    prompt = patch_doc_retrieval_dependencies["prompt"]
    assert ACCOUNT_CONTEXT_NOTE not in prompt


# ---------------------------------------------------------------------------
# L1 — build_prompt's own account_context branch, no I/O at all
# ---------------------------------------------------------------------------


def test_build_prompt_includes_account_context_note_when_present():
    messages = build_prompt(
        static_ctx={},
        dynamic_ctx={
            "query": "What is this customer's SLA level?",
            "history": [],
            "evidence": "(no evidence retrieved)",
            "account_context": "Your account is on the Basic SLA level.",
        },
    )
    dynamic_content = messages[1]["content"]
    assert ACCOUNT_CONTEXT_NOTE in dynamic_content


def test_build_prompt_omits_account_context_note_when_absent():
    messages = build_prompt(
        static_ctx={},
        dynamic_ctx={
            "query": "What is the API rate limit for the Free tier?",
            "history": [],
            "evidence": "(no evidence retrieved)",
            "account_context": None,
        },
    )
    dynamic_content = messages[1]["content"]
    assert ACCOUNT_CONTEXT_NOTE not in dynamic_content
