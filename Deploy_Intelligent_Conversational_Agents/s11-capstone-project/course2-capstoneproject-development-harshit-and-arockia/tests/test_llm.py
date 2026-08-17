"""
Unit tests for agent/llm.py — LLM factory with lru_cache.
"""
import pytest
from unittest.mock import MagicMock


class TestGetLlm:
    def test_raises_without_api_key(self, monkeypatch):
        from exceptions import GeminiConfigError
        monkeypatch.setenv("GEMINI_API_KEY", "")
        from agent.llm import get_llm
        with pytest.raises(GeminiConfigError, match="GEMINI_API_KEY"):
            get_llm()

    def test_returns_chatopenai_instance(self, mocker):
        mock_llm = MagicMock()
        MockChat = mocker.patch("langchain_openai.ChatOpenAI", return_value=mock_llm)

        from agent.llm import get_llm
        result = get_llm()

        assert result is mock_llm
        MockChat.assert_called_once()
        call_kwargs = MockChat.call_args.kwargs
        assert call_kwargs["api_key"] == "test-gemini-key"
        assert call_kwargs["model"] == "gemini-test-model"

    def test_uses_default_model_when_env_missing(self, monkeypatch, mocker):
        monkeypatch.delenv("GEMINI_MODEL_NAME", raising=False)
        mock_llm = MagicMock()
        MockChat = mocker.patch("langchain_openai.ChatOpenAI", return_value=mock_llm)

        from agent.llm import get_llm
        get_llm()

        call_kwargs = MockChat.call_args.kwargs
        assert call_kwargs["model"] == "gemini-2.0-flash"

    def test_result_is_cached(self, mocker):
        mock_llm = MagicMock()
        MockChat = mocker.patch("langchain_openai.ChatOpenAI", return_value=mock_llm)

        from agent.llm import get_llm
        first  = get_llm()
        second = get_llm()

        assert first is second
        # ChatOpenAI should only have been constructed once despite two calls
        assert MockChat.call_count == 1

    def test_base_url_configurable(self, monkeypatch, mocker):
        monkeypatch.setenv("GEMINI_BASE_URL", "https://custom.api.com/v1/")
        mock_llm = MagicMock()
        MockChat = mocker.patch("langchain_openai.ChatOpenAI", return_value=mock_llm)

        from agent.llm import get_llm
        get_llm()

        call_kwargs = MockChat.call_args.kwargs
        assert call_kwargs["base_url"] == "https://custom.api.com/v1/"


# ── invoke_llm ────────────────────────────────────────────────────────────────

class TestInvokeLlm:
    def test_propagates_app_error_from_llm(self, mocker):
        """AppError raised by llm.invoke() must propagate without re-wrapping."""
        from exceptions import GeminiConfigError
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = GeminiConfigError("bad key")
        mocker.patch("agent.llm.get_llm", return_value=mock_llm)

        from agent.llm import invoke_llm
        with pytest.raises(GeminiConfigError):
            invoke_llm("test prompt")

    def test_returns_response_content_on_success(self, mocker):
        mock_llm = MagicMock()
        mock_resp = MagicMock()
        mock_resp.content = "Hello, world!"
        mock_llm.invoke.return_value = mock_resp
        mocker.patch("agent.llm.get_llm", return_value=mock_llm)

        from agent.llm import invoke_llm
        result = invoke_llm("prompt")
        assert result == "Hello, world!"


# ── _translate_llm_error (heuristic string matching) ─────────────────────────

class TestTranslateLlmError:
    """
    _translate_llm_error is called via invoke_llm when the LLM raises a
    non-AppError exception.  We patch get_llm to return a mock that raises
    the target exception so the full call path is exercised.
    """

    def _make_llm(self, exc, mocker):
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = exc
        mocker.patch("agent.llm.get_llm", return_value=mock_llm)

    def test_rate_limit_message_raises_rate_limit_error(self, mocker):
        from exceptions import GeminiRateLimitError
        self._make_llm(RuntimeError("rate limit exceeded"), mocker)
        from agent.llm import invoke_llm
        with pytest.raises(GeminiRateLimitError):
            invoke_llm("p")

    def test_429_in_message_raises_rate_limit_error(self, mocker):
        from exceptions import GeminiRateLimitError
        self._make_llm(RuntimeError("HTTP 429 received"), mocker)
        from agent.llm import invoke_llm
        with pytest.raises(GeminiRateLimitError):
            invoke_llm("p")

    def test_quota_message_raises_quota_exceeded_error(self, mocker):
        from exceptions import GeminiQuotaExceededError
        self._make_llm(RuntimeError("quota exhausted"), mocker)
        from agent.llm import invoke_llm
        with pytest.raises(GeminiQuotaExceededError):
            invoke_llm("p")

    def test_authentication_message_raises_config_error(self, mocker):
        from exceptions import GeminiConfigError
        self._make_llm(RuntimeError("authentication failed"), mocker)
        from agent.llm import invoke_llm
        with pytest.raises(GeminiConfigError):
            invoke_llm("p")

    def test_401_in_message_raises_config_error(self, mocker):
        from exceptions import GeminiConfigError
        self._make_llm(RuntimeError("received 401 Unauthorized"), mocker)
        from agent.llm import invoke_llm
        with pytest.raises(GeminiConfigError):
            invoke_llm("p")

    def test_permission_message_raises_config_error(self, mocker):
        from exceptions import GeminiConfigError
        self._make_llm(RuntimeError("permission denied"), mocker)
        from agent.llm import invoke_llm
        with pytest.raises(GeminiConfigError):
            invoke_llm("p")

    def test_connection_message_raises_network_error(self, mocker):
        from exceptions import GeminiNetworkError
        self._make_llm(RuntimeError("connection refused"), mocker)
        from agent.llm import invoke_llm
        with pytest.raises(GeminiNetworkError):
            invoke_llm("p")

    def test_503_in_message_raises_network_error(self, mocker):
        from exceptions import GeminiNetworkError
        self._make_llm(RuntimeError("service returned 503"), mocker)
        from agent.llm import invoke_llm
        with pytest.raises(GeminiNetworkError):
            invoke_llm("p")

    def test_bad_request_message_raises_invalid_request_error(self, mocker):
        from exceptions import GeminiInvalidRequestError
        self._make_llm(RuntimeError("bad request: param invalid"), mocker)
        from agent.llm import invoke_llm
        with pytest.raises(GeminiInvalidRequestError):
            invoke_llm("p")

    def test_unknown_message_raises_generic_gemini_error(self, mocker):
        from exceptions import GeminiError
        self._make_llm(RuntimeError("something completely unexpected"), mocker)
        from agent.llm import invoke_llm
        with pytest.raises(GeminiError):
            invoke_llm("p")

    def test_invoke_reraises_if_translate_does_not_raise(self, mocker):
        """Covers line 102: the bare ``raise`` after _translate_llm_error()."""
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = RuntimeError("original error")
        mocker.patch("agent.llm.get_llm", return_value=mock_llm)
        # Patch _translate_llm_error to return without raising
        mocker.patch("agent.llm._translate_llm_error")

        from agent.llm import invoke_llm
        with pytest.raises(RuntimeError, match="original error"):
            invoke_llm("p")


# ── _translate_llm_error — ImportError fallback ───────────────────────────────

class TestTranslateLlmErrorImportError:
    """Covers lines 120-121: when openai is not importable, _oa is set to None."""

    def test_import_error_falls_back_to_string_matching(self, mocker):
        from exceptions import GeminiRateLimitError
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = RuntimeError("rate limit exceeded")
        mocker.patch("agent.llm.get_llm", return_value=mock_llm)
        # Simulate openai being unimportable
        mocker.patch.dict("sys.modules", {"openai": None})

        from agent.llm import invoke_llm
        with pytest.raises(GeminiRateLimitError):
            invoke_llm("p")


# ── _translate_llm_error — openai SDK isinstance branches ────────────────────

class TestTranslateLlmErrorOpenaiSDK:
    """
    Covers lines 125, 130, 135, 140, 145, 151, 156 — the isinstance checks
    inside _translate_llm_error that run when the openai SDK is importable.

    We install a fake ``openai`` module in sys.modules with minimal exception
    classes so that ``import openai as _oa`` inside _translate_llm_error
    uses our fake types, and ``isinstance(exc, _oa.SomeError)`` returns True.
    """

    def _install_fake_openai(self, mocker):
        """Register a fake openai module with the required exception classes."""
        import types

        class _Base(Exception):
            pass

        class RateLimitError(_Base):
            pass

        class AuthenticationError(_Base):
            pass

        class PermissionDeniedError(_Base):
            pass

        class NotFoundError(_Base):
            pass

        class APIConnectionError(_Base):
            pass

        class APITimeoutError(_Base):
            pass

        class InternalServerError(_Base):
            pass

        class BadRequestError(_Base):
            pass

        fake_oa = types.ModuleType("openai")
        fake_oa.RateLimitError = RateLimitError
        fake_oa.AuthenticationError = AuthenticationError
        fake_oa.PermissionDeniedError = PermissionDeniedError
        fake_oa.NotFoundError = NotFoundError
        fake_oa.APIConnectionError = APIConnectionError
        fake_oa.APITimeoutError = APITimeoutError
        fake_oa.InternalServerError = InternalServerError
        fake_oa.BadRequestError = BadRequestError

        mocker.patch.dict("sys.modules", {"openai": fake_oa})
        return fake_oa

    def _make_llm(self, exc, mocker):
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = exc
        mocker.patch("agent.llm.get_llm", return_value=mock_llm)

    def test_rate_limit_error_raises_gemini_rate_limit(self, mocker):
        from exceptions import GeminiRateLimitError
        fake_oa = self._install_fake_openai(mocker)
        self._make_llm(fake_oa.RateLimitError("too many requests"), mocker)
        from agent.llm import invoke_llm
        with pytest.raises(GeminiRateLimitError):
            invoke_llm("p")

    def test_authentication_error_raises_gemini_config_error(self, mocker):
        from exceptions import GeminiConfigError
        fake_oa = self._install_fake_openai(mocker)
        self._make_llm(fake_oa.AuthenticationError("bad key"), mocker)
        from agent.llm import invoke_llm
        with pytest.raises(GeminiConfigError):
            invoke_llm("p")

    def test_permission_denied_error_raises_gemini_config_error(self, mocker):
        from exceptions import GeminiConfigError
        fake_oa = self._install_fake_openai(mocker)
        self._make_llm(fake_oa.PermissionDeniedError("no permission"), mocker)
        from agent.llm import invoke_llm
        with pytest.raises(GeminiConfigError):
            invoke_llm("p")

    def test_not_found_error_raises_gemini_config_error(self, mocker):
        from exceptions import GeminiConfigError
        fake_oa = self._install_fake_openai(mocker)
        self._make_llm(fake_oa.NotFoundError("model not found"), mocker)
        from agent.llm import invoke_llm
        with pytest.raises(GeminiConfigError):
            invoke_llm("p")

    def test_api_connection_error_raises_gemini_network_error(self, mocker):
        from exceptions import GeminiNetworkError
        fake_oa = self._install_fake_openai(mocker)
        self._make_llm(fake_oa.APIConnectionError("connection refused"), mocker)
        from agent.llm import invoke_llm
        with pytest.raises(GeminiNetworkError):
            invoke_llm("p")

    def test_api_timeout_error_raises_gemini_network_error(self, mocker):
        from exceptions import GeminiNetworkError
        fake_oa = self._install_fake_openai(mocker)
        self._make_llm(fake_oa.APITimeoutError("timed out"), mocker)
        from agent.llm import invoke_llm
        with pytest.raises(GeminiNetworkError):
            invoke_llm("p")

    def test_internal_server_error_raises_gemini_network_error(self, mocker):
        from exceptions import GeminiNetworkError
        fake_oa = self._install_fake_openai(mocker)
        self._make_llm(fake_oa.InternalServerError("server error"), mocker)
        from agent.llm import invoke_llm
        with pytest.raises(GeminiNetworkError):
            invoke_llm("p")

    def test_bad_request_error_raises_gemini_invalid_request_error(self, mocker):
        from exceptions import GeminiInvalidRequestError
        fake_oa = self._install_fake_openai(mocker)
        self._make_llm(fake_oa.BadRequestError("bad request"), mocker)
        from agent.llm import invoke_llm
        with pytest.raises(GeminiInvalidRequestError):
            invoke_llm("p")
