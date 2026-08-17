"""Checkpoint store used by the LangGraph orchestrator to persist
EventPlanState after every node."""

from contextlib import asynccontextmanager

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from app.config import get_settings


@asynccontextmanager
async def get_checkpointer():
    """Yields an open AsyncSqliteSaver for the app's lifetime. Used from
    app/main.py's startup/shutdown lifespan, not called per-request."""
    database_url = get_settings().database_url
    sqlite_path = database_url.removeprefix("sqlite:///")
    async with AsyncSqliteSaver.from_conn_string(sqlite_path) as checkpointer:
        yield checkpointer