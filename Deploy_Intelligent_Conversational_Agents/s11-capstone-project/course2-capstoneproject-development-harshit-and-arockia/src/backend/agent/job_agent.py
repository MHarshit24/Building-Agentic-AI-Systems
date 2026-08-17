"""
Job Placement Agent — LangChain Agent with Tool Calling & Session Memory
------------------------------------------------------------------------
Uses:
  - ChatOpenAI (Gemini via OpenAI-compatible API)
  - create_tool_calling_agent + AgentExecutor
  - RunnableWithMessageHistory for per-session conversation memory
  - Langfuse CallbackHandler for full observability

Async support (Sprint 2, LO3)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
``run_agent_async()``  — awaitable variant using ``.ainvoke()``
``stream_agent()``     — async generator using ``.astream_events()``; yields
                         individual text tokens for SSE delivery (Sprint 7).
"""
import logging
from typing import AsyncGenerator, Optional

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.chat_history import InMemoryChatMessageHistory as ChatMessageHistory

from agent.llm import get_llm
from agent.prompts import SYSTEM_PROMPT
from agent.tools.job_search import search_jobs
from agent.tools.resume_analyzer import analyze_resume
from agent.tools.cover_letter import generate_cover_letter
from observability.langfuse_config import get_langfuse_handler
from exceptions import AgentError, AppError

logger = logging.getLogger(__name__)

# ── In-memory session store  (resets when the server restarts) ──────────────
_session_store: dict[str, ChatMessageHistory] = {}


def get_session_history(session_id: str) -> ChatMessageHistory:
    """Return (or create) the ChatMessageHistory for a given session."""
    if session_id not in _session_store:
        _session_store[session_id] = ChatMessageHistory()
        logger.debug(f"New session created: {session_id}")
    return _session_store[session_id]


def clear_session(session_id: str) -> None:
    """Delete the conversation history for a session."""
    if session_id in _session_store:
        del _session_store[session_id]
        logger.info(f"Session cleared: {session_id}")


def list_sessions() -> list[str]:
    """Return all active session IDs."""
    return list(_session_store.keys())


# ── Agent construction ───────────────────────────────────────────────────────
def _build_agent_executor() -> AgentExecutor:
    """
    Instantiate the LangChain tool-calling agent.
    Called once at module load; the result is re-used across all requests.
    """
    llm = get_llm()
    tools = [search_jobs, analyze_resume, generate_cover_letter]

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_PROMPT),
            # Populated by RunnableWithMessageHistory
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            # Populated by AgentExecutor for intermediate tool steps
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
    )

    agent = create_tool_calling_agent(llm, tools, prompt)

    executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        max_iterations=6,
        handle_parsing_errors=True,
        return_intermediate_steps=False,
    )
    logger.info("AgentExecutor built successfully.")
    return executor


# Lazy-initialised singletons — built on the first request, not at import time.
# This avoids cold-start failures on serverless platforms (Vercel) where the LLM
# client must not be instantiated until all env vars are available.
_executor: Optional[AgentExecutor] = None
_agent_with_history = None


def _get_agent():
    """Return the agent (creates it on first call)."""
    global _executor, _agent_with_history
    if _executor is None:
        _executor = _build_agent_executor()
        _agent_with_history = RunnableWithMessageHistory(
            _executor,
            get_session_history,
            input_messages_key="input",
            history_messages_key="chat_history",
        )
    return _agent_with_history


# ── Public interface ─────────────────────────────────────────────────────────
def run_agent(
    user_message: str,
    session_id: str = "default",
    user_id: Optional[str] = None,
) -> str:
    """
    Run the Job Placement Agent for a given user message.

    Args:
        user_message: The user's latest chat input.
        session_id:   Identifies the conversation (persisted in-process).
        user_id:      Optional Auth0 user sub; forwarded to Langfuse traces.

    Returns:
        The agent's textual response.
    """
    langfuse_handler = get_langfuse_handler(session_id=session_id, user_id=user_id)

    callbacks = []
    if langfuse_handler:
        callbacks.append(langfuse_handler)

    config = {
        "configurable": {"session_id": session_id},
        "callbacks": callbacks,
    }

    logger.info(f"Agent invoked — session={session_id}, message_len={len(user_message)}")

    try:
        result = _get_agent().invoke(
            {"input": user_message},
            config=config,
        )
        output = result.get("output", "")
        if not output:
            return "I'm sorry, I couldn't generate a response. Please try again."
        return output

    except AppError:
        # Domain exceptions (GeminiRateLimitError, GeminiConfigError, Auth0Error, …)
        # carry their own http_status and error_code — let the global handler format
        # the ApiResponse and return the correct HTTP status to the client.
        raise

    except Exception as exc:
        logger.error("Agent error (session=%s): %s", session_id, exc, exc_info=True)
        raise AgentError(
            f"The agent encountered an unexpected error: {exc}"
        ) from exc

    finally:
        # Flush Langfuse traces immediately after each invocation.
        # On serverless platforms (Vercel) the process is killed after the
        # request completes, so the normal shutdown-event flush never runs.
        if langfuse_handler:
            try:
                langfuse_handler.flush()
            except Exception:
                pass  # never let a flush failure mask a real error


# ── Async interface (Sprint 2, LO3) ─────────────────────────────────────────

async def run_agent_async(
    user_message: str,
    session_id: str = "default",
    user_id: Optional[str] = None,
) -> str:
    """
    Async variant of ``run_agent`` — uses ``.ainvoke()`` so the FastAPI event
    loop is never blocked while waiting for the LLM response.

    Sprint 2, LO3: Execute Asynchronous LLM Calls with ``.ainvoke()``.

    Args:
        user_message: The user's latest chat input.
        session_id:   Identifies the conversation (persisted in-process).
        user_id:      Optional Auth0 user sub; forwarded to Langfuse traces.

    Returns:
        The agent's textual response.
    """
    langfuse_handler = get_langfuse_handler(session_id=session_id, user_id=user_id)
    callbacks = [langfuse_handler] if langfuse_handler else []
    config = {
        "configurable": {"session_id": session_id},
        "callbacks": callbacks,
    }

    logger.info(
        "Async agent invoked — session=%s, message_len=%d",
        session_id, len(user_message),
    )

    try:
        # .ainvoke() is the async counterpart of .invoke() — it awaits the LLM
        # call without blocking the event loop (Sprint 2, LO3).
        result = await _get_agent().ainvoke({"input": user_message}, config=config)
        output = result.get("output", "")
        return output or "I'm sorry, I couldn't generate a response. Please try again."

    except AppError:
        raise

    except Exception as exc:
        logger.error(
            "Async agent error (session=%s): %s", session_id, exc, exc_info=True
        )
        raise AgentError(
            f"The agent encountered an unexpected error: {exc}"
        ) from exc

    finally:
        if langfuse_handler:
            try:
                langfuse_handler.flush()
            except Exception:
                pass


async def stream_agent(
    user_message: str,
    session_id: str = "default",
    user_id: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """
    Async generator that streams the agent's response token-by-token.

    Uses ``.astream_events()`` (LangChain v0.2+) to receive individual tokens
    as they are generated by the LLM.  Only final-answer tokens are yielded —
    intermediate tool-call chunks (which carry no ``content``) are skipped.

    Sprint 7: Streaming AI Responses — consumed by the SSE endpoint
    ``POST /api/chat/stream`` via ``StreamingResponse``.

    Yields:
        Individual text tokens (str) from the agent's final response.
    """
    langfuse_handler = get_langfuse_handler(session_id=session_id, user_id=user_id)
    callbacks = [langfuse_handler] if langfuse_handler else []
    config = {
        "configurable": {"session_id": session_id},
        "callbacks": callbacks,
    }

    logger.info(
        "Stream agent invoked — session=%s, message_len=%d",
        session_id, len(user_message),
    )

    try:
        async for event in _get_agent().astream_events(
            {"input": user_message},
            config=config,
            version="v1",
        ):
            # "on_chat_model_stream" fires for every token the LLM emits.
            # When the LLM is deciding which tool to call, it emits structured
            # JSON chunks whose `.content` is empty — skip those.
            # Final-answer tokens have non-empty `.content` and no tool_call_chunks.
            if event["event"] == "on_chat_model_stream":
                chunk = event["data"].get("chunk")
                if (
                    chunk
                    and chunk.content
                    and not getattr(chunk, "tool_call_chunks", None)
                ):
                    yield chunk.content

    except AppError:
        raise

    except Exception as exc:
        logger.error(
            "Stream agent error (session=%s): %s", session_id, exc, exc_info=True
        )
        raise AgentError(f"Streaming failed: {exc}") from exc

    finally:
        if langfuse_handler:
            try:
                langfuse_handler.flush()
            except Exception:
                pass
