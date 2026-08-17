"""
tests/unit/test_reflect_merge_final_answer.py

Pure-logic (no LLM, no I/O) coverage for reflect.py's _merge_final_answer()
— specifically the second real bug fix documented in its own docstring,
found via live manual QA: doc_retrieval_node and account_validation_node
run CONCURRENTLY in genuine Hybrid/Critical mode (LangGraph's Send
fan-out, same superstep), so neither can see the other's own
evidence_sufficient verdict while drafting its own text. Confirmed
directly against a real live trace: a query asking about an active
regional outage got "I don't have enough information to answer that...
[then] Yes. There are currently active incidents..." in one response —
doc_retrieval's own honest "no account context" denial concatenated right
next to account_validation's real, substantive answer.

The first fix (account_context passed into doc_retrieval_node's own
prompt) only covers the SEQUENTIAL SQL-alone-then-retry case — it cannot
help the concurrent case, since doc_retrieval_node's prompt is built
before account_validation_node's result exists in state at all. This
file's fix instead teaches the MERGE step itself to prefer whichever
side's own evidence_sufficient verdict says it actually has something to
say, using the real, non-heuristic signal each node's own structured
output already computes (DocRetrievalOutput.evidence_sufficient /
AccountValidationOutput.evidence_sufficient) — not string-matching a
denial phrase, which would be fragile against paraphrasing.
"""

from __future__ import annotations

from app.orchestration.nodes.reflect import _merge_final_answer


def test_doc_insufficient_account_sufficient_uses_account_narrative_alone():
    """The exact real bug: doc_retrieval honestly has nothing (no account
    context), account_validation has a real answer — must not concatenate
    the denial next to the real answer."""
    state = {
        "final_answer": "I don't have enough information to answer that — the retrieved "
        "documentation does not include any current incident list.",
        "account_narrative": "Yes. There are currently active incidents affecting the APAC "
        "region where this customer is located.",
        "doc_evidence_sufficient": False,
        "account_evidence_sufficient": True,
    }

    result = _merge_final_answer(state)

    assert result == state["account_narrative"]
    assert "I don't have enough information" not in result


def test_account_insufficient_doc_sufficient_uses_doc_answer_alone():
    """Symmetric case: account_validation found nothing (e.g. no matching
    account/incident), doc_retrieval has the real documentation answer."""
    state = {
        "final_answer": "A 429 error means the rate limit was exceeded. Wait 60 seconds and "
        "implement exponential backoff before retrying.",
        "account_narrative": "I don't have an account on file matching this customer ID.",
        "doc_evidence_sufficient": True,
        "account_evidence_sufficient": False,
    }

    result = _merge_final_answer(state)

    assert result == state["final_answer"]
    assert "I don't have an account on file" not in result


def test_both_sufficient_still_concatenates_normally():
    """Unchanged existing behavior — this is the normal, intended Hybrid
    case (both sides have real, complementary content)."""
    state = {
        "final_answer": "The documented Critical response window is 15 minutes.",
        "account_narrative": "Your account has one open Critical ticket (#3).",
        "doc_evidence_sufficient": True,
        "account_evidence_sufficient": True,
    }

    result = _merge_final_answer(state)

    assert result == (
        "The documented Critical response window is 15 minutes.\n\n"
        "Your account has one open Critical ticket (#3)."
    )


def test_both_insufficient_falls_back_to_concatenation_not_special_cased():
    """Both sides honestly say they don't know — redundant, but not
    contradictory, so no special handling needed beyond the existing
    concatenation fallback."""
    state = {
        "final_answer": "I don't have enough information to answer that.",
        "account_narrative": "I don't have an account on file matching this customer ID.",
        "doc_evidence_sufficient": False,
        "account_evidence_sufficient": False,
    }

    result = _merge_final_answer(state)

    assert "I don't have enough information to answer that" in result
    assert "I don't have an account on file matching this customer ID" in result


def test_missing_evidence_sufficient_signals_default_to_concatenation():
    """Defensive: if either signal is simply absent from state (None, not
    False) — e.g. an older checkpoint, or a code path that never sets it —
    must not misfire the new preference logic; falls back to the original
    concatenation behavior exactly as before this fix."""
    state = {
        "final_answer": "Doc answer.",
        "account_narrative": "Account narrative.",
    }

    result = _merge_final_answer(state)

    assert result == "Doc answer.\n\nAccount narrative."


def test_sql_alone_mode_unaffected_no_duplication():
    """Pre-existing behavior, unchanged: SQL-alone mode already writes the
    same text to both final_answer and account_narrative directly — must
    not duplicate it."""
    state = {
        "final_answer": "Your account (Acme Corp) is Active.",
        "account_narrative": "Your account (Acme Corp) is Active.",
        "doc_evidence_sufficient": None,
        "account_evidence_sufficient": True,
    }

    result = _merge_final_answer(state)

    assert result == "Your account (Acme Corp) is Active."


def test_only_account_narrative_present():
    state = {"final_answer": None, "account_narrative": "Your account is Active."}
    assert _merge_final_answer(state) == "Your account is Active."


def test_only_final_answer_present():
    state = {"final_answer": "A 429 error means the rate limit was exceeded.", "account_narrative": None}
    assert _merge_final_answer(state) == "A 429 error means the rate limit was exceeded."
