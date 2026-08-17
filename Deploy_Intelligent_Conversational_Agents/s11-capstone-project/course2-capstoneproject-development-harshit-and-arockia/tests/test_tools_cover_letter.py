"""
Unit tests for agent/tools/cover_letter.py — LLM-based cover letter generator.
"""
import pytest
from unittest.mock import MagicMock, patch


VALID_INPUTS = {
    "resume_text": "Experienced software engineer with 5 years in Python.",
    "job_title": "Senior Backend Engineer",
    "company_name": "Acme Corp",
    "job_description": "We are looking for a Python developer to join our team.",
    "user_name": "Alice Smith",
}


class TestGenerateCoverLetter:
    # ── Input validation ──────────────────────────────────────────────────────

    def test_returns_error_when_resume_too_short(self):
        from agent.tools.cover_letter import generate_cover_letter
        inputs = {**VALID_INPUTS, "resume_text": "Hi"}
        result = generate_cover_letter.invoke(inputs)
        assert "resume text" in result.lower()

    def test_returns_error_when_job_title_missing(self):
        from agent.tools.cover_letter import generate_cover_letter
        inputs = {**VALID_INPUTS, "job_title": ""}
        result = generate_cover_letter.invoke(inputs)
        assert "job title" in result.lower()

    def test_returns_error_when_company_name_missing(self):
        from agent.tools.cover_letter import generate_cover_letter
        inputs = {**VALID_INPUTS, "company_name": ""}
        result = generate_cover_letter.invoke(inputs)
        assert "company name" in result.lower()

    def test_returns_error_when_job_description_too_short(self):
        from agent.tools.cover_letter import generate_cover_letter
        inputs = {**VALID_INPUTS, "job_description": "Short"}
        result = generate_cover_letter.invoke(inputs)
        assert "job description" in result.lower()

    def test_lists_all_missing_fields(self):
        from agent.tools.cover_letter import generate_cover_letter
        result = generate_cover_letter.invoke({
            "resume_text": "",
            "job_title": "",
            "company_name": "",
            "job_description": "",
            "user_name": "Bob",
        })
        assert "resume text" in result.lower()
        assert "job title" in result.lower()
        assert "company name" in result.lower()
        assert "job description" in result.lower()

    # ── Successful generation ─────────────────────────────────────────────────

    def test_calls_llm_with_all_inputs(self):
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "Dear Hiring Manager, I am thrilled..."
        mock_llm.invoke.return_value = mock_response

        with patch("agent.llm.get_llm", return_value=mock_llm):
            from agent.tools.cover_letter import generate_cover_letter
            result = generate_cover_letter.invoke(VALID_INPUTS)

        mock_llm.invoke.assert_called_once()
        prompt_arg = mock_llm.invoke.call_args[0][0]
        assert "Alice Smith" in prompt_arg
        assert "Senior Backend Engineer" in prompt_arg
        assert "Acme Corp" in prompt_arg

    def test_result_contains_job_title_and_company(self):
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "Cover letter body text."
        mock_llm.invoke.return_value = mock_response

        with patch("agent.llm.get_llm", return_value=mock_llm):
            from agent.tools.cover_letter import generate_cover_letter
            result = generate_cover_letter.invoke(VALID_INPUTS)

        assert "Senior Backend Engineer" in result
        assert "Acme Corp" in result

    def test_result_includes_footer_note(self):
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "Letter text."
        mock_llm.invoke.return_value = mock_response

        with patch("agent.llm.get_llm", return_value=mock_llm):
            from agent.tools.cover_letter import generate_cover_letter
            result = generate_cover_letter.invoke(VALID_INPUTS)

        assert "tailored" in result.lower() or "cover letter" in result.lower()

    def test_default_user_name_applicant(self):
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "Letter."
        mock_llm.invoke.return_value = mock_response

        inputs = {k: v for k, v in VALID_INPUTS.items() if k != "user_name"}
        with patch("agent.llm.get_llm", return_value=mock_llm):
            from agent.tools.cover_letter import generate_cover_letter
            generate_cover_letter.invoke(inputs)

        prompt_arg = mock_llm.invoke.call_args[0][0]
        assert "Applicant" in prompt_arg

    # ── Exception handling ────────────────────────────────────────────────────

    def test_returns_error_message_on_llm_exception(self):
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = RuntimeError("API rate limit")

        with patch("agent.llm.get_llm", return_value=mock_llm):
            from agent.tools.cover_letter import generate_cover_letter
            result = generate_cover_letter.invoke(VALID_INPUTS)

        # Tool catches GeminiError and returns a user-friendly message
        assert "encountered an issue" in result.lower() or "unexpected error" in result.lower()

    def test_generic_exception_returns_unexpected_error(self):
        with patch(
            "agent.tools.cover_letter.generate_cover_letter_core",
            side_effect=KeyError("weird"),
        ):
            from agent.tools.cover_letter import generate_cover_letter
            result = generate_cover_letter.invoke(VALID_INPUTS)
        assert "unexpected error" in result.lower()
