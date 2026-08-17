"""
Unit tests for agent/router.py — LCEL RunnableBranch intent router.

Sprint 5/6: Router Chains for Conditional Workflows.

The router consists of two LCEL stages:
  1. classify_chain  — ChatPromptTemplate | LLM | StrOutputParser
  2. RunnableBranch  — routes to a specialist chain based on the intent label

Tests isolate each stage by patching _get_classify_chain and RunnableBranch
so that the routing logic can be verified without live LLM calls.
"""
import pytest
from unittest.mock import MagicMock, patch


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_classify_chain(intent: str):
    """Return a mock classify chain that always returns ``intent``."""
    mock_chain = MagicMock()
    mock_chain.invoke.return_value = intent
    return mock_chain


def _make_branch(response: str):
    """Return a mock RunnableBranch whose .invoke() returns ``response``."""
    mock_branch = MagicMock()
    mock_branch.invoke.return_value = response
    return mock_branch


# ── route_query ───────────────────────────────────────────────────────────────

class TestRouteQuery:
    """
    Tests for the public route_query(query) -> (intent, response) function.
    Each test patches _get_classify_chain and RunnableBranch to control
    what the LLM "decides" without making real API calls.
    """

    def test_returns_tuple_of_intent_and_response(self, mocker):
        mocker.patch(
            "agent.router._get_classify_chain",
            return_value=_make_classify_chain("general"),
        )
        mocker.patch("agent.router.RunnableBranch", return_value=_make_branch("Hello!"))
        from agent.router import route_query
        result = route_query("Hi there")
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_returns_detected_intent_as_first_element(self, mocker):
        mocker.patch(
            "agent.router._get_classify_chain",
            return_value=_make_classify_chain("job_search"),
        )
        mocker.patch("agent.router.RunnableBranch", return_value=_make_branch("Jobs found"))
        from agent.router import route_query
        intent, _ = route_query("Find Python jobs in NYC")
        assert intent == "job_search"

    def test_returns_branch_response_as_second_element(self, mocker):
        mocker.patch(
            "agent.router._get_classify_chain",
            return_value=_make_classify_chain("resume_analysis"),
        )
        mocker.patch("agent.router.RunnableBranch", return_value=_make_branch("Resume score: 8/10"))
        from agent.router import route_query
        _, response = route_query("Analyze my resume")
        assert response == "Resume score: 8/10"

    def test_job_search_intent_detected(self, mocker):
        mocker.patch(
            "agent.router._get_classify_chain",
            return_value=_make_classify_chain("job_search"),
        )
        mocker.patch("agent.router.RunnableBranch", return_value=_make_branch("..."))
        from agent.router import route_query
        intent, _ = route_query("I'm looking for data engineer jobs in London")
        assert intent == "job_search"

    def test_resume_intent_detected(self, mocker):
        mocker.patch(
            "agent.router._get_classify_chain",
            return_value=_make_classify_chain("resume_analysis"),
        )
        mocker.patch("agent.router.RunnableBranch", return_value=_make_branch("..."))
        from agent.router import route_query
        intent, _ = route_query("Can you review my resume?")
        assert intent == "resume_analysis"

    def test_cover_letter_intent_detected(self, mocker):
        mocker.patch(
            "agent.router._get_classify_chain",
            return_value=_make_classify_chain("cover_letter"),
        )
        mocker.patch("agent.router.RunnableBranch", return_value=_make_branch("..."))
        from agent.router import route_query
        intent, _ = route_query("Write me a cover letter for a senior engineer role at Google")
        assert intent == "cover_letter"

    def test_general_intent_is_default(self, mocker):
        mocker.patch(
            "agent.router._get_classify_chain",
            return_value=_make_classify_chain("general"),
        )
        mocker.patch("agent.router.RunnableBranch", return_value=_make_branch("Hello!"))
        from agent.router import route_query
        intent, _ = route_query("Hi, how are you?")
        assert intent == "general"

    def test_classify_chain_receives_query(self, mocker):
        mock_classify = _make_classify_chain("general")
        mocker.patch("agent.router._get_classify_chain", return_value=mock_classify)
        mocker.patch("agent.router.RunnableBranch", return_value=_make_branch("ok"))
        from agent.router import route_query
        route_query("What can you do?")
        call_args = mock_classify.invoke.call_args[0][0]
        assert call_args["query"] == "What can you do?"

    def test_branch_receives_query_and_intent(self, mocker):
        mock_branch = _make_branch("job response")
        mocker.patch(
            "agent.router._get_classify_chain",
            return_value=_make_classify_chain("job_search"),
        )
        mocker.patch("agent.router.RunnableBranch", return_value=mock_branch)
        from agent.router import route_query
        route_query("Find me jobs")
        call_args = mock_branch.invoke.call_args[0][0]
        assert call_args["query"] == "Find me jobs"
        assert call_args["intent"] == "job_search"

    def test_callbacks_forwarded_to_classify_chain(self, mocker):
        mock_classify = _make_classify_chain("general")
        mocker.patch("agent.router._get_classify_chain", return_value=mock_classify)
        mocker.patch("agent.router.RunnableBranch", return_value=_make_branch("ok"))
        fake_cb = MagicMock()
        from agent.router import route_query
        route_query("Hi", callbacks=[fake_cb])
        config = mock_classify.invoke.call_args[1].get("config", {})
        assert fake_cb in config.get("callbacks", [])

    def test_whitespace_stripped_from_intent(self, mocker):
        """route_query calls .strip() on the classifier output before returning."""
        mocker.patch(
            "agent.router._get_classify_chain",
            return_value=_make_classify_chain("  job_search  "),
        )
        mocker.patch("agent.router.RunnableBranch", return_value=_make_branch("..."))
        from agent.router import route_query
        intent, _ = route_query("Find jobs")
        # route_query strips whitespace from the classifier's raw output
        assert intent == "job_search"


# ── get_router_pipeline ───────────────────────────────────────────────────────

class TestGetRouterPipeline:
    """
    Tests for the cached get_router_pipeline() factory.
    Verifies the pipeline is built, cached, and accepts a {"query"} input.
    """

    def test_returns_a_runnable(self, mocker):
        """Pipeline must be a non-None object (Runnable)."""
        mock_llm = MagicMock()
        mocker.patch("agent.router.get_llm", return_value=mock_llm)
        from agent.router import get_router_pipeline
        pipeline = get_router_pipeline()
        assert pipeline is not None

    def test_is_cached_across_calls(self, mocker):
        """The same pipeline object is returned on every call (lru_cache)."""
        mock_llm = MagicMock()
        mocker.patch("agent.router.get_llm", return_value=mock_llm)
        from agent.router import get_router_pipeline
        p1 = get_router_pipeline()
        p2 = get_router_pipeline()
        # Both calls must return the exact same cached object
        assert p1 is p2


# ── _get_classify_chain ───────────────────────────────────────────────────────

class TestGetClassifyChain:
    """
    Tests for the classify-chain factory.
    Sprint 5/6: ChatPromptTemplate | LLM | StrOutputParser.
    """

    def test_returns_a_non_none_chain(self, mocker):
        mock_llm = MagicMock()
        mocker.patch("agent.router.get_llm", return_value=mock_llm)
        from agent.router import _get_classify_chain
        chain = _get_classify_chain()
        assert chain is not None

    def test_chain_is_cached(self, mocker):
        mock_llm = MagicMock()
        mock_get_llm = mocker.patch("agent.router.get_llm", return_value=mock_llm)
        from agent.router import _get_classify_chain
        c1 = _get_classify_chain()
        c2 = _get_classify_chain()
        assert c1 is c2
        assert mock_get_llm.call_count == 1


# ── intent label constants ────────────────────────────────────────────────────

class TestIntentLabels:
    """Verify the exported intent constant strings are correct."""

    def test_job_search_label(self):
        from agent.router import INTENT_JOB_SEARCH
        assert INTENT_JOB_SEARCH == "job_search"

    def test_resume_label(self):
        from agent.router import INTENT_RESUME
        assert INTENT_RESUME == "resume_analysis"

    def test_cover_letter_label(self):
        from agent.router import INTENT_COVER_LETTER
        assert INTENT_COVER_LETTER == "cover_letter"

    def test_general_label(self):
        from agent.router import INTENT_GENERAL
        assert INTENT_GENERAL == "general"
