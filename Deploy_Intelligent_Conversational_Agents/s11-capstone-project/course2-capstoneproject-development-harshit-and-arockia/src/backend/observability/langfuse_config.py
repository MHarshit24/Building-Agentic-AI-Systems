"""
Langfuse Observability Configuration
--------------------------------------
Provides a LangChain CallbackHandler for tracing agent runs.

Langfuse is **optional** — both functions gracefully degrade when:
  - Credentials are not configured (LANGFUSE_SECRET_KEY / LANGFUSE_PUBLIC_KEY missing)
  - The langfuse package is not installed
  - The Langfuse server is unreachable

Errors are logged as domain-specific LangfuseError subclasses so they appear
clearly in logs without crashing the application.
"""
import os
import logging
from functools import lru_cache
from typing import Optional

from exceptions import LangfuseConfigError, LangfuseNetworkError

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _langfuse_setup():
    """
    Validate credentials and import CallbackHandler once per process.
    Returns (CallbackHandler, secret_key, public_key, host) or None.
    Cached so env-var reads and package imports happen only once.
    """
    secret_key = os.getenv("LANGFUSE_SECRET_KEY", "").strip()
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY", "").strip()
    host       = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com").strip()

    if not secret_key or not public_key:
        missing = [k for k, v in {"LANGFUSE_SECRET_KEY": secret_key, "LANGFUSE_PUBLIC_KEY": public_key}.items() if not v]
        logger.warning("Langfuse credentials not set (%s). Observability disabled.", ", ".join(missing))
        return None

    try:
        from langfuse.langchain import CallbackHandler
        return CallbackHandler, secret_key, public_key, host
    except ImportError as exc:
        logger.warning("langfuse package not installed (%s). Run: pip install langfuse", exc)
        return None


def get_langfuse_handler(
    session_id: str = "default",
    user_id: Optional[str] = None,
):
    """
    Return a Langfuse LangChain CallbackHandler for the given session.

    Credentials and package import are checked only once (cached). Per-request
    overhead is limited to instantiating the CallbackHandler with the session ID.

    Returns None when Langfuse is not configured or unavailable.
    """
    setup = _langfuse_setup()
    if setup is None:
        return None

    CallbackHandler, secret_key, public_key, host = setup
    try:
        handler = CallbackHandler(
            secret_key=secret_key,
            public_key=public_key,
            host=host,
            session_id=session_id,
            user_id=user_id,
            trace_name="job-placement-agent",
            tags=["job-agent", "langchain"],
        )
        logger.debug("Langfuse handler initialised for session: %s", session_id)
        return handler

    except Exception as exc:
        msg = str(exc).lower()
        if "connection" in msg or "timeout" in msg or "unreachable" in msg:
            err = LangfuseNetworkError(f"Could not connect to Langfuse at '{host}': {exc}")
        else:
            err = LangfuseConfigError(f"Failed to initialise Langfuse handler: {exc}")
        logger.error("%s: %s — tracing disabled for session %s", type(err).__name__, err, session_id, exc_info=True)
        return None


def flush_langfuse() -> None:
    """
    Flush any pending Langfuse events to the server.
    Should be called during application shutdown.

    Errors are logged but never raised — a failed flush must not prevent
    a clean shutdown.
    """
    secret_key = os.getenv("LANGFUSE_SECRET_KEY", "").strip()
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY", "").strip()
    host       = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com").strip()

    if not secret_key or not public_key:
        return  # Langfuse not configured — nothing to flush

    try:
        from langfuse import Langfuse
        lf = Langfuse(secret_key=secret_key, public_key=public_key, host=host)
        lf.flush()
        logger.info("Langfuse events flushed successfully.")

    except ImportError:
        pass  # Package not installed — nothing to flush

    except Exception as exc:
        msg = str(exc).lower()
        if "connection" in msg or "timeout" in msg:
            err = LangfuseNetworkError(f"Langfuse flush failed — network error: {exc}")
        else:
            err = LangfuseConfigError(f"Langfuse flush failed: {exc}")
        logger.error(
            "%s during shutdown flush: %s",
            type(err).__name__, err,
            exc_info=True,
        )
