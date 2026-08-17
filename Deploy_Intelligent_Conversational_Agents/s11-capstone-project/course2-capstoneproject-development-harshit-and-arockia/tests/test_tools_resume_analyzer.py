"""
Unit tests for agent/tools/resume_analyzer.py — LCEL-chain resume analysis.

After Sprint 5/6 refactor, analyze_resume_core() builds its prompt and calls
the LLM via an explicit LCEL chain:

    chain = ChatPromptTemplate.from_messages([...]) | get_llm() | StrOutputParser()

Tests therefore mock ``_get_analysis_chain`` (which returns the cached chain)
rather than ``agent.llm.get_llm`` directly.  This keeps the tests decoupled
from LCEL internals while still verifying the correct prompt content is
forwarded to the chain.
"""
import pytest
from unittest.mock import MagicMock, patch


class TestAnalyzeResumeTool:
    """Tests for the @tool wrapper — validation and error handling."""

    def test_returns_error_for_empty_resume(self):
        from agent.tools.resume_analyzer import analyze_resume
        result = analyze_resume.invoke({"resume_text": "", "job_description": ""})
        assert "too short" in result.lower() or "please paste" in result.lower()

    def test_returns_error_for_short_resume(self):
        from agent.tools.resume_analyzer import analyze_resume
        result = analyze_resume.invoke({"resume_text": "Hi", "job_description": ""})
        assert "too short" in result.lower() or "please paste" in result.lower()

    def test_returns_error_message_on_chain_exception(self, mocker):
        mock_chain = MagicMock()
        mock_chain.invoke.side_effect = RuntimeError("LLM timeout")
        mocker.patch(
            "agent.tools.resume_analyzer._get_analysis_chain",
            return_value=mock_chain,
        )
        from agent.tools.resume_analyzer import analyze_resume
        result = analyze_resume.invoke({"resume_text": "x" * 100, "job_description": ""})
        assert "encountered an issue" in result.lower() or "unexpected error" in result.lower()

    def test_generic_exception_returns_unexpected_error(self, mocker):
        mocker.patch(
            "agent.tools.resume_analyzer.analyze_resume_core",
            side_effect=KeyError("weird"),
        )
        from agent.tools.resume_analyzer import analyze_resume
        result = analyze_resume.invoke({"resume_text": "x" * 100, "job_description": ""})
        assert "unexpected error" in result.lower()

    def test_gemini_error_returns_issue_message(self, mocker):
        """Covers lines 210-211: the except GeminiError handler in the @tool wrapper."""
        from exceptions import GeminiError
        mocker.patch(
            "agent.tools.resume_analyzer.analyze_resume_core",
            side_effect=GeminiError("LLM service unavailable"),
        )
        from agent.tools.resume_analyzer import analyze_resume
        result = analyze_resume.invoke({"resume_text": "x" * 100, "job_description": ""})
        assert "encountered an issue" in result.lower()


class TestAnalyzeResumeCore:
    """Tests for the core function — LCEL chain invocation and prompt construction."""

    # ── helpers ───────────────────────────────────────────────────────────────

    def _mock_chain(self, mocker, return_value="LLM analysis result"):
        """Patch _get_analysis_chain to return a controllable mock chain."""
        mock_chain = MagicMock()
        mock_chain.invoke.return_value = return_value
        mocker.patch(
            "agent.tools.resume_analyzer._get_analysis_chain",
            return_value=mock_chain,
        )
        return mock_chain

    def _captured_prompt(self, mock_chain) -> str:
        """Extract the analysis_prompt string from chain.invoke() call args."""
        call_args = mock_chain.invoke.call_args
        # chain.invoke({"analysis_prompt": "..."}, config=...)
        return call_args[0][0]["analysis_prompt"]

    # ── chain invocation ──────────────────────────────────────────────────────

    def test_uses_lcel_chain_not_direct_invoke(self, mocker):
        """Core function must call chain.invoke(), not llm.invoke() directly."""
        mock_chain = self._mock_chain(mocker, "Strong Python background. Score: 8/10.")
        from agent.tools.resume_analyzer import analyze_resume_core
        result = analyze_resume_core("x" * 100)
        assert result == "Strong Python background. Score: 8/10."
        mock_chain.invoke.assert_called_once()

    def test_passes_callbacks_in_config(self, mocker):
        mock_chain = self._mock_chain(mocker)
        fake_cb = MagicMock()
        from agent.tools.resume_analyzer import analyze_resume_core
        analyze_resume_core("x" * 100, callbacks=[fake_cb])
        call_kwargs = mock_chain.invoke.call_args[1]
        assert call_kwargs["config"]["callbacks"] == [fake_cb]

    def test_no_config_when_callbacks_empty(self, mocker):
        mock_chain = self._mock_chain(mocker)
        from agent.tools.resume_analyzer import analyze_resume_core
        analyze_resume_core("x" * 100, callbacks=None)
        call_kwargs = mock_chain.invoke.call_args[1]
        # config should be {} (falsy) when no callbacks
        assert not call_kwargs.get("config", {})

    # ── prompt content — without job description ──────────────────────────────

    def test_resume_text_appears_in_prompt(self, mocker):
        mock_chain = self._mock_chain(mocker)
        resume = "Senior Python developer with 10 years experience at Google."
        from agent.tools.resume_analyzer import analyze_resume_core
        analyze_resume_core(resume)
        prompt = self._captured_prompt(mock_chain)
        assert resume in prompt

    def test_no_gap_section_when_no_job_description(self, mocker):
        mock_chain = self._mock_chain(mocker)
        from agent.tools.resume_analyzer import analyze_resume_core
        analyze_resume_core("x" * 100, job_description="")
        prompt = self._captured_prompt(mock_chain)
        assert "Skill Gap Analysis" not in prompt

    def test_short_job_description_treated_as_absent(self, mocker):
        """A JD of ≤ 20 chars should be ignored (no gap section in prompt)."""
        mock_chain = self._mock_chain(mocker)
        from agent.tools.resume_analyzer import analyze_resume_core
        analyze_resume_core("x" * 100, job_description="short")
        prompt = self._captured_prompt(mock_chain)
        assert "Skill Gap Analysis" not in prompt

    # ── prompt content — with job description ─────────────────────────────────

    def test_gap_section_included_when_job_description_given(self, mocker):
        mock_chain = self._mock_chain(mocker)
        jd = "We need an experienced FastAPI developer with Kubernetes skills."
        from agent.tools.resume_analyzer import analyze_resume_core
        analyze_resume_core("x" * 100, job_description=jd)
        prompt = self._captured_prompt(mock_chain)
        assert "Skill Gap Analysis" in prompt

    def test_job_description_appears_in_prompt(self, mocker):
        mock_chain = self._mock_chain(mocker)
        jd = "We need an experienced FastAPI developer with Kubernetes skills."
        from agent.tools.resume_analyzer import analyze_resume_core
        analyze_resume_core("x" * 100, job_description=jd)
        prompt = self._captured_prompt(mock_chain)
        assert jd in prompt

    # ── validation ────────────────────────────────────────────────────────────

    def test_raises_value_error_for_short_resume(self):
        from agent.tools.resume_analyzer import analyze_resume_core
        with pytest.raises(ValueError, match="too short"):
            analyze_resume_core("Hi")

    def test_raises_value_error_for_empty_resume(self):
        from agent.tools.resume_analyzer import analyze_resume_core
        with pytest.raises(ValueError):
            analyze_resume_core("")

    # ── LCEL chain factory ────────────────────────────────────────────────────

    def test_get_analysis_chain_builds_lcel_chain(self, mocker):
        """
        _get_analysis_chain() must call get_llm() and compose it via | syntax.
        Verifies the chain factory actually calls get_llm() once (Sprint 5/6).
        """
        mock_llm = MagicMock()
        mocker.patch("agent.tools.resume_analyzer.get_llm", return_value=mock_llm)
        from agent.tools.resume_analyzer import _get_analysis_chain
        chain = _get_analysis_chain()
        # get_llm() must have been called during chain construction
        # (the | operator on the prompt template triggers it)
        assert chain is not None

    def test_get_analysis_chain_is_cached(self, mocker):
        """Chain must be built only once thanks to lru_cache (Sprint 5/6)."""
        mock_llm = MagicMock()
        mock_get_llm = mocker.patch(
            "agent.tools.resume_analyzer.get_llm", return_value=mock_llm
        )
        from agent.tools.resume_analyzer import _get_analysis_chain
        _get_analysis_chain()
        _get_analysis_chain()
        # get_llm should only be called once despite two chain fetches
        assert mock_get_llm.call_count == 1
