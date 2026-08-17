"""
Unit tests for observability/langfuse_config.py.
"""
import pytest
from unittest.mock import MagicMock


class TestGetLangfuseHandler:
    def test_returns_none_when_keys_not_set(self):
        # clean_env fixture sets LANGFUSE keys to ""
        from observability.langfuse_config import get_langfuse_handler
        result = get_langfuse_handler(session_id="s1")
        assert result is None

    def test_returns_none_when_only_secret_key_set(self, monkeypatch):
        monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-test")
        monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "")
        from observability.langfuse_config import get_langfuse_handler
        result = get_langfuse_handler()
        assert result is None

    def test_returns_handler_when_keys_set(self, langfuse_env, mocker):
        """Instance returned by CallbackHandler(…) is what's returned."""
        mock_instance = MagicMock()
        mocker.patch("langfuse.callback.CallbackHandler", return_value=mock_instance)

        from observability.langfuse_config import get_langfuse_handler
        result = get_langfuse_handler(session_id="sess-abc", user_id="user-1")

        assert result is mock_instance

    def test_returns_none_on_callback_handler_exception(self, langfuse_env, mocker):
        mocker.patch("langfuse.callback.CallbackHandler", side_effect=RuntimeError("boom"))
        from observability.langfuse_config import get_langfuse_handler
        result = get_langfuse_handler()
        assert result is None

    def test_user_id_optional(self, langfuse_env, mocker):
        mock_instance = MagicMock()
        mocker.patch("langfuse.callback.CallbackHandler", return_value=mock_instance)
        from observability.langfuse_config import get_langfuse_handler
        result = get_langfuse_handler(session_id="s1")
        assert result is mock_instance

    def test_passes_correct_params_to_handler(self, langfuse_env, monkeypatch, mocker):
        monkeypatch.setenv("LANGFUSE_HOST", "https://my.langfuse.server")
        MockCH = mocker.patch("langfuse.callback.CallbackHandler", return_value=MagicMock())

        from observability.langfuse_config import get_langfuse_handler
        get_langfuse_handler(session_id="sess-xyz", user_id="u42")

        kw = MockCH.call_args.kwargs
        assert kw["session_id"] == "sess-xyz"
        assert kw["user_id"] == "u42"
        assert kw["host"] == "https://my.langfuse.server"

    def test_returns_none_when_langfuse_callback_not_installed(self, langfuse_env, monkeypatch):
        import sys
        monkeypatch.setitem(sys.modules, "langfuse.callback", None)
        from observability.langfuse_config import get_langfuse_handler
        result = get_langfuse_handler()
        assert result is None

    def test_returns_none_on_network_error_during_handler_init(self, langfuse_env, mocker):
        mocker.patch(
            "langfuse.callback.CallbackHandler",
            side_effect=Exception("connection refused to langfuse server"),
        )
        from observability.langfuse_config import get_langfuse_handler
        result = get_langfuse_handler()
        assert result is None


class TestFlushLangfuse:
    def test_flush_calls_langfuse_flush(self, langfuse_env, mocker):
        mock_lf_instance = MagicMock()
        mocker.patch("langfuse.Langfuse", return_value=mock_lf_instance)
        from observability.langfuse_config import flush_langfuse
        flush_langfuse()
        mock_lf_instance.flush.assert_called_once()

    def test_flush_silences_exception(self, mocker):
        mocker.patch("langfuse.Langfuse", side_effect=Exception("network error"))
        from observability.langfuse_config import flush_langfuse
        flush_langfuse()  # Should not raise

    def test_flush_silences_network_exception(self, langfuse_env, mocker):
        mocker.patch("langfuse.Langfuse", side_effect=Exception("connection timeout"))
        from observability.langfuse_config import flush_langfuse
        flush_langfuse()  # Should not raise

    def test_flush_silences_config_exception(self, langfuse_env, mocker):
        mocker.patch("langfuse.Langfuse", side_effect=Exception("invalid configuration"))
        from observability.langfuse_config import flush_langfuse
        flush_langfuse()  # Should not raise — hits LangfuseConfigError branch

    def test_flush_does_nothing_when_langfuse_not_installed(self, langfuse_env, monkeypatch):
        import sys
        monkeypatch.setitem(sys.modules, "langfuse", None)
        from observability.langfuse_config import flush_langfuse
        flush_langfuse()  # Should not raise
