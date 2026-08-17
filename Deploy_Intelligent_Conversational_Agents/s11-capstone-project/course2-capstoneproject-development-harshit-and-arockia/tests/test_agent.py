"""
Unit tests for agent/job_agent.py — session management and agent runner.

Covers:
  run_agent()        — synchronous path
  run_agent_async()  — async path with .ainvoke()  (Sprint 2, LO3)
  stream_agent()     — async generator with .astream_events()  (Sprint 7)
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ── Session management ────────────────────────────────────────────────────────

class TestGetSessionHistory:
    def test_creates_new_session(self):
        from agent.job_agent import get_session_history, _session_store
        _session_store.clear()
        history = get_session_history("new-session")
        assert "new-session" in _session_store

    def test_returns_same_history_for_existing_session(self):
        from agent.job_agent import get_session_history, _session_store
        _session_store.clear()
        h1 = get_session_history("sess-a")
        h2 = get_session_history("sess-a")
        assert h1 is h2

    def test_different_sessions_are_independent(self):
        from agent.job_agent import get_session_history, _session_store
        _session_store.clear()
        h1 = get_session_history("sess-1")
        h2 = get_session_history("sess-2")
        assert h1 is not h2


class TestClearSession:
    def test_removes_existing_session(self):
        from agent.job_agent import get_session_history, clear_session, _session_store
        _session_store.clear()
        get_session_history("to-delete")
        assert "to-delete" in _session_store
        clear_session("to-delete")
        assert "to-delete" not in _session_store

    def test_silently_ignores_missing_session(self):
        from agent.job_agent import clear_session
        clear_session("does-not-exist")  # Should not raise


class TestListSessions:
    def test_returns_all_session_ids(self):
        from agent.job_agent import get_session_history, list_sessions, _session_store
        _session_store.clear()
        get_session_history("s1")
        get_session_history("s2")
        sessions = list_sessions()
        assert "s1" in sessions
        assert "s2" in sessions

    def test_returns_empty_list_when_no_sessions(self):
        from agent.job_agent import list_sessions, _session_store
        _session_store.clear()
        assert list_sessions() == []


# ── run_agent ─────────────────────────────────────────────────────────────────

class TestRunAgent:
    def _make_mock_agent(self, output="Agent reply"):
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = {"output": output}
        return mock_agent

    def test_returns_agent_output(self):
        mock_agent = self._make_mock_agent("Here are some jobs.")

        with patch("agent.job_agent._get_agent", return_value=mock_agent):
            with patch("agent.job_agent.get_langfuse_handler", return_value=None):
                from agent.job_agent import run_agent
                result = run_agent("Find me a job", session_id="s1")

        assert result == "Here are some jobs."

    def test_passes_session_id_in_config(self):
        mock_agent = self._make_mock_agent()

        with patch("agent.job_agent._get_agent", return_value=mock_agent):
            with patch("agent.job_agent.get_langfuse_handler", return_value=None):
                from agent.job_agent import run_agent
                run_agent("Hello", session_id="my-session")

        call_kwargs = mock_agent.invoke.call_args
        config = call_kwargs[1]["config"] if call_kwargs[1] else call_kwargs[0][1]
        assert config["configurable"]["session_id"] == "my-session"

    def test_includes_langfuse_callback_when_handler_available(self):
        mock_agent = self._make_mock_agent()
        mock_handler = MagicMock()

        with patch("agent.job_agent._get_agent", return_value=mock_agent):
            with patch("agent.job_agent.get_langfuse_handler", return_value=mock_handler):
                from agent.job_agent import run_agent
                run_agent("Hi", session_id="s1", user_id="u1")

        call_kwargs = mock_agent.invoke.call_args
        config = call_kwargs[1]["config"] if call_kwargs[1] else call_kwargs[0][1]
        assert mock_handler in config["callbacks"]

    def test_empty_output_returns_fallback_message(self):
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = {"output": ""}

        with patch("agent.job_agent._get_agent", return_value=mock_agent):
            with patch("agent.job_agent.get_langfuse_handler", return_value=None):
                from agent.job_agent import run_agent
                result = run_agent("Hi", session_id="s1")

        assert "sorry" in result.lower() or "couldn't generate" in result.lower()

    def test_returns_error_message_on_exception(self):
        from exceptions import AgentError
        mock_agent = MagicMock()
        mock_agent.invoke.side_effect = RuntimeError("LLM failure")

        with patch("agent.job_agent._get_agent", return_value=mock_agent):
            with patch("agent.job_agent.get_langfuse_handler", return_value=None):
                from agent.job_agent import run_agent
                with pytest.raises(AgentError) as exc_info:
                    run_agent("Hi", session_id="s1")

        assert "unexpected error" in str(exc_info.value).lower()
        assert "LLM failure" in str(exc_info.value)

    def test_raises_app_error_without_wrapping(self):
        from exceptions import GeminiRateLimitError
        mock_agent = MagicMock()
        mock_agent.invoke.side_effect = GeminiRateLimitError("rate limit hit")

        with patch("agent.job_agent._get_agent", return_value=mock_agent):
            with patch("agent.job_agent.get_langfuse_handler", return_value=None):
                from agent.job_agent import run_agent
                with pytest.raises(GeminiRateLimitError):
                    run_agent("Hi", session_id="s1")


# ── _get_agent (lazy singleton) ───────────────────────────────────────────────

class TestGetAgentSingleton:
    def test_builds_agent_on_first_call(self):
        mock_executor = MagicMock()
        mock_runnable = MagicMock()

        with patch("agent.job_agent._build_agent_executor", return_value=mock_executor) as mock_build:
            with patch("agent.job_agent.RunnableWithMessageHistory", return_value=mock_runnable):
                import agent.job_agent as jm
                jm._executor = None
                jm._agent_with_history = None
                result = jm._get_agent()

        mock_build.assert_called_once()
        assert result is mock_runnable

    def test_returns_same_instance_on_subsequent_calls(self):
        mock_executor = MagicMock()
        mock_runnable = MagicMock()

        with patch("agent.job_agent._build_agent_executor", return_value=mock_executor) as mock_build:
            with patch("agent.job_agent.RunnableWithMessageHistory", return_value=mock_runnable):
                import agent.job_agent as jm
                jm._executor = None
                jm._agent_with_history = None
                first  = jm._get_agent()
                second = jm._get_agent()

        assert first is second
        assert mock_build.call_count == 1


# ── run_agent_async (Sprint 2, LO3) ──────────────────────────────────────────

class TestRunAgentAsync:
    """
    run_agent_async() must use .ainvoke() (not .invoke()) and behave
    identically to run_agent() for happy-path and error cases.
    Sprint 2, LO3: Execute Asynchronous LLM Calls.
    """

    def _run(self, coro):
        """Helper: execute a coroutine synchronously via asyncio.run()."""
        return asyncio.run(coro)

    def _make_mock_agent(self, output="Async agent reply"):
        mock_agent = MagicMock()
        mock_agent.ainvoke = AsyncMock(return_value={"output": output})
        return mock_agent

    def test_returns_agent_output(self):
        mock_agent = self._make_mock_agent("Here are async jobs.")

        async def _run():
            with patch("agent.job_agent._get_agent", return_value=mock_agent):
                with patch("agent.job_agent.get_langfuse_handler", return_value=None):
                    from agent.job_agent import run_agent_async
                    return await run_agent_async("Find jobs", session_id="s1")

        assert self._run(_run()) == "Here are async jobs."

    def test_uses_ainvoke_not_invoke(self):
        """Must call .ainvoke(), not .invoke(), on the agent."""
        mock_agent = self._make_mock_agent()

        async def _run():
            with patch("agent.job_agent._get_agent", return_value=mock_agent):
                with patch("agent.job_agent.get_langfuse_handler", return_value=None):
                    from agent.job_agent import run_agent_async
                    await run_agent_async("Hi", session_id="s1")

        self._run(_run())
        mock_agent.ainvoke.assert_called_once()
        mock_agent.invoke.assert_not_called()

    def test_passes_session_id_in_config(self):
        mock_agent = self._make_mock_agent()

        async def _run():
            with patch("agent.job_agent._get_agent", return_value=mock_agent):
                with patch("agent.job_agent.get_langfuse_handler", return_value=None):
                    from agent.job_agent import run_agent_async
                    await run_agent_async("Hello", session_id="async-session")

        self._run(_run())
        call_kwargs = mock_agent.ainvoke.call_args
        config = call_kwargs[1]["config"] if call_kwargs[1] else call_kwargs[0][1]
        assert config["configurable"]["session_id"] == "async-session"

    def test_includes_langfuse_callback_when_available(self):
        mock_agent = self._make_mock_agent()
        mock_handler = MagicMock()

        async def _run():
            with patch("agent.job_agent._get_agent", return_value=mock_agent):
                with patch("agent.job_agent.get_langfuse_handler", return_value=mock_handler):
                    from agent.job_agent import run_agent_async
                    await run_agent_async("Hi", session_id="s1", user_id="u1")

        self._run(_run())
        config = mock_agent.ainvoke.call_args[1]["config"]
        assert mock_handler in config["callbacks"]

    def test_empty_output_returns_fallback_message(self):
        mock_agent = MagicMock()
        mock_agent.ainvoke = AsyncMock(return_value={"output": ""})

        async def _run():
            with patch("agent.job_agent._get_agent", return_value=mock_agent):
                with patch("agent.job_agent.get_langfuse_handler", return_value=None):
                    from agent.job_agent import run_agent_async
                    return await run_agent_async("Hi", session_id="s1")

        result = self._run(_run())
        assert "sorry" in result.lower() or "couldn't generate" in result.lower()

    def test_raises_agent_error_on_unexpected_exception(self):
        from exceptions import AgentError
        mock_agent = MagicMock()
        mock_agent.ainvoke = AsyncMock(side_effect=RuntimeError("async LLM failure"))

        async def _run():
            with patch("agent.job_agent._get_agent", return_value=mock_agent):
                with patch("agent.job_agent.get_langfuse_handler", return_value=None):
                    from agent.job_agent import run_agent_async
                    return await run_agent_async("Hi", session_id="s1")

        with pytest.raises(AgentError, match="unexpected error"):
            self._run(_run())

    def test_propagates_app_error_without_wrapping(self):
        from exceptions import GeminiRateLimitError
        mock_agent = MagicMock()
        mock_agent.ainvoke = AsyncMock(side_effect=GeminiRateLimitError("rate limit"))

        async def _run():
            with patch("agent.job_agent._get_agent", return_value=mock_agent):
                with patch("agent.job_agent.get_langfuse_handler", return_value=None):
                    from agent.job_agent import run_agent_async
                    return await run_agent_async("Hi", session_id="s1")

        with pytest.raises(GeminiRateLimitError):
            self._run(_run())

    def test_flushes_langfuse_handler_after_invoke(self):
        mock_agent = self._make_mock_agent()
        mock_handler = MagicMock()

        async def _run():
            with patch("agent.job_agent._get_agent", return_value=mock_agent):
                with patch("agent.job_agent.get_langfuse_handler", return_value=mock_handler):
                    from agent.job_agent import run_agent_async
                    await run_agent_async("Hi", session_id="s1")

        self._run(_run())
        mock_handler.flush.assert_called_once()


# ── stream_agent (Sprint 7) ───────────────────────────────────────────────────

class TestStreamAgent:
    """
    stream_agent() must be an async generator that yields individual text
    tokens from on_chat_model_stream events, skipping tool-call chunks.
    Sprint 7: Streaming AI Responses.
    """

    def _run(self, coro):
        return asyncio.run(coro)

    def _make_chunk(self, content, tool_call_chunks=None):
        """Build a minimal AIMessageChunk-like mock."""
        chunk = MagicMock()
        chunk.content = content
        chunk.tool_call_chunks = tool_call_chunks or []
        return chunk

    def _make_stream_event(self, event_type, chunk):
        return {"event": event_type, "data": {"chunk": chunk}}

    def _mock_agent_with_events(self, events):
        """Return a mock agent whose astream_events yields the given events."""
        async def _fake_stream(*args, **kwargs):
            for e in events:
                yield e

        mock_agent = MagicMock()
        mock_agent.astream_events = _fake_stream
        return mock_agent

    # ── happy path ────────────────────────────────────────────────────────────

    def test_yields_content_from_chat_model_stream_events(self):
        events = [
            self._make_stream_event("on_chat_model_stream", self._make_chunk("Hello")),
            self._make_stream_event("on_chat_model_stream", self._make_chunk(" world")),
        ]
        mock_agent = self._mock_agent_with_events(events)

        async def _run():
            tokens = []
            with patch("agent.job_agent._get_agent", return_value=mock_agent):
                with patch("agent.job_agent.get_langfuse_handler", return_value=None):
                    from agent.job_agent import stream_agent
                    async for token in stream_agent("Hi", session_id="s1"):
                        tokens.append(token)
            return tokens

        tokens = self._run(_run())
        assert tokens == ["Hello", " world"]

    def test_skips_empty_content_chunks(self):
        """Chunks with empty content (tool-call decisions) must be skipped."""
        events = [
            self._make_stream_event("on_chat_model_stream", self._make_chunk("")),
            self._make_stream_event("on_chat_model_stream", self._make_chunk("Final answer")),
        ]
        mock_agent = self._mock_agent_with_events(events)

        async def _run():
            tokens = []
            with patch("agent.job_agent._get_agent", return_value=mock_agent):
                with patch("agent.job_agent.get_langfuse_handler", return_value=None):
                    from agent.job_agent import stream_agent
                    async for token in stream_agent("Hi", session_id="s1"):
                        tokens.append(token)
            return tokens

        tokens = self._run(_run())
        assert tokens == ["Final answer"]

    def test_skips_chunks_with_tool_call_chunks(self):
        """Chunks that represent tool-call selection must not be yielded."""
        events = [
            self._make_stream_event(
                "on_chat_model_stream",
                self._make_chunk('{"name": "search_jobs"}', tool_call_chunks=[{"id": "1"}]),
            ),
            self._make_stream_event("on_chat_model_stream", self._make_chunk("Here are jobs")),
        ]
        mock_agent = self._mock_agent_with_events(events)

        async def _run():
            tokens = []
            with patch("agent.job_agent._get_agent", return_value=mock_agent):
                with patch("agent.job_agent.get_langfuse_handler", return_value=None):
                    from agent.job_agent import stream_agent
                    async for token in stream_agent("Hi", session_id="s1"):
                        tokens.append(token)
            return tokens

        tokens = self._run(_run())
        assert tokens == ["Here are jobs"]

    def test_skips_non_chat_model_events(self):
        """Only on_chat_model_stream events should produce tokens."""
        events = [
            {"event": "on_tool_start", "data": {}},
            {"event": "on_tool_end",   "data": {}},
            self._make_stream_event("on_chat_model_stream", self._make_chunk("Answer")),
        ]
        mock_agent = self._mock_agent_with_events(events)

        async def _run():
            tokens = []
            with patch("agent.job_agent._get_agent", return_value=mock_agent):
                with patch("agent.job_agent.get_langfuse_handler", return_value=None):
                    from agent.job_agent import stream_agent
                    async for token in stream_agent("Hi", session_id="s1"):
                        tokens.append(token)
            return tokens

        assert self._run(_run()) == ["Answer"]

    def test_yields_nothing_when_no_matching_events(self):
        events = [
            {"event": "on_chain_start",  "data": {}},
            {"event": "on_chain_end",    "data": {}},
        ]
        mock_agent = self._mock_agent_with_events(events)

        async def _run():
            tokens = []
            with patch("agent.job_agent._get_agent", return_value=mock_agent):
                with patch("agent.job_agent.get_langfuse_handler", return_value=None):
                    from agent.job_agent import stream_agent
                    async for token in stream_agent("Hi", session_id="s1"):
                        tokens.append(token)
            return tokens

        assert self._run(_run()) == []

    # ── error handling ────────────────────────────────────────────────────────

    def test_raises_agent_error_on_unexpected_exception(self):
        from exceptions import AgentError

        async def _fail_stream(*args, **kwargs):
            raise RuntimeError("stream broken")
            yield  # make it an async generator

        mock_agent = MagicMock()
        mock_agent.astream_events = _fail_stream

        async def _run():
            with patch("agent.job_agent._get_agent", return_value=mock_agent):
                with patch("agent.job_agent.get_langfuse_handler", return_value=None):
                    from agent.job_agent import stream_agent
                    async for _ in stream_agent("Hi", session_id="s1"):
                        pass

        with pytest.raises(AgentError, match="Streaming failed"):
            self._run(_run())

    def test_propagates_app_error_without_wrapping(self):
        from exceptions import GeminiNetworkError

        async def _fail_stream(*args, **kwargs):
            raise GeminiNetworkError("no connection")
            yield

        mock_agent = MagicMock()
        mock_agent.astream_events = _fail_stream

        async def _run():
            with patch("agent.job_agent._get_agent", return_value=mock_agent):
                with patch("agent.job_agent.get_langfuse_handler", return_value=None):
                    from agent.job_agent import stream_agent
                    async for _ in stream_agent("Hi", session_id="s1"):
                        pass

        with pytest.raises(GeminiNetworkError):
            self._run(_run())

    # ── session & callback wiring ─────────────────────────────────────────────

    def test_passes_session_id_in_config(self):
        captured_config = {}

        async def _capture_stream(*args, **kwargs):
            captured_config.update(kwargs.get("config", {}))
            return
            yield  # async generator

        mock_agent = MagicMock()
        mock_agent.astream_events = _capture_stream

        async def _run():
            with patch("agent.job_agent._get_agent", return_value=mock_agent):
                with patch("agent.job_agent.get_langfuse_handler", return_value=None):
                    from agent.job_agent import stream_agent
                    async for _ in stream_agent("Hi", session_id="stream-sess"):
                        pass

        self._run(_run())
        assert captured_config.get("configurable", {}).get("session_id") == "stream-sess"

    def test_flushes_langfuse_handler_after_streaming(self):
        events = [
            self._make_stream_event("on_chat_model_stream", self._make_chunk("Hi")),
        ]
        mock_agent = self._mock_agent_with_events(events)
        mock_handler = MagicMock()

        async def _run():
            with patch("agent.job_agent._get_agent", return_value=mock_agent):
                with patch("agent.job_agent.get_langfuse_handler", return_value=mock_handler):
                    from agent.job_agent import stream_agent
                    async for _ in stream_agent("Hi", session_id="s1"):
                        pass

        self._run(_run())
        mock_handler.flush.assert_called_once()


# ── _build_agent_executor ─────────────────────────────────────────────────────

class TestBuildAgentExecutor:
    """Tests for the _build_agent_executor() factory (lines 64-89 in job_agent.py)."""

    def test_calls_get_llm_and_returns_executor(self, mocker):
        mock_llm = MagicMock()
        mocker.patch("agent.job_agent.get_llm", return_value=mock_llm)
        mocker.patch("agent.job_agent.create_tool_calling_agent", return_value=MagicMock())
        mock_executor = MagicMock()
        mocker.patch("agent.job_agent.AgentExecutor", return_value=mock_executor)
        mocker.patch("agent.job_agent.ChatPromptTemplate.from_messages", return_value=MagicMock())

        from agent.job_agent import _build_agent_executor
        result = _build_agent_executor()

        assert result is mock_executor

    def test_creates_tool_calling_agent_with_llm_and_tools(self, mocker):
        mock_llm = MagicMock()
        mocker.patch("agent.job_agent.get_llm", return_value=mock_llm)
        mock_create = mocker.patch(
            "agent.job_agent.create_tool_calling_agent", return_value=MagicMock()
        )
        mocker.patch("agent.job_agent.AgentExecutor", return_value=MagicMock())
        mocker.patch("agent.job_agent.ChatPromptTemplate.from_messages", return_value=MagicMock())

        from agent.job_agent import _build_agent_executor
        _build_agent_executor()

        assert mock_create.call_count == 1
        args = mock_create.call_args[0]
        assert args[0] is mock_llm  # first arg is the LLM


# ── Flush exception swallowing ────────────────────────────────────────────────

class TestFlushExceptionSwallowing:
    """
    The finally blocks in run_agent, run_agent_async, and stream_agent swallow
    any exception raised by langfuse_handler.flush() so a monitoring hiccup
    never masks a real error.  These tests exercise lines 172-173, 231-232,
    and 297-298 respectively.
    """

    def test_run_agent_swallows_flush_exception(self):
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = {"output": "reply"}
        mock_handler = MagicMock()
        mock_handler.flush.side_effect = RuntimeError("flush failed")

        with patch("agent.job_agent._get_agent", return_value=mock_agent):
            with patch("agent.job_agent.get_langfuse_handler", return_value=mock_handler):
                from agent.job_agent import run_agent
                result = run_agent("Hi", session_id="s1")

        assert result == "reply"
        mock_handler.flush.assert_called_once()

    def test_run_agent_async_swallows_flush_exception(self):
        mock_agent = MagicMock()
        mock_agent.ainvoke = AsyncMock(return_value={"output": "async reply"})
        mock_handler = MagicMock()
        mock_handler.flush.side_effect = RuntimeError("flush failed")

        async def _run():
            with patch("agent.job_agent._get_agent", return_value=mock_agent):
                with patch("agent.job_agent.get_langfuse_handler", return_value=mock_handler):
                    from agent.job_agent import run_agent_async
                    return await run_agent_async("Hi", session_id="s1")

        result = asyncio.run(_run())
        assert result == "async reply"
        mock_handler.flush.assert_called_once()

    def test_stream_agent_swallows_flush_exception(self):
        chunk = MagicMock()
        chunk.content = "token"
        chunk.tool_call_chunks = []
        event = {"event": "on_chat_model_stream", "data": {"chunk": chunk}}

        async def _fake_stream(*args, **kwargs):
            yield event

        mock_agent = MagicMock()
        mock_agent.astream_events = _fake_stream
        mock_handler = MagicMock()
        mock_handler.flush.side_effect = RuntimeError("flush failed")

        async def _run():
            tokens = []
            with patch("agent.job_agent._get_agent", return_value=mock_agent):
                with patch("agent.job_agent.get_langfuse_handler", return_value=mock_handler):
                    from agent.job_agent import stream_agent
                    async for tok in stream_agent("Hi", session_id="s1"):
                        tokens.append(tok)
            return tokens

        tokens = asyncio.run(_run())
        assert tokens == ["token"]
        mock_handler.flush.assert_called_once()
