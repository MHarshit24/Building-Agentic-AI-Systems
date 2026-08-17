"""
app/orchestration/checkpointer.py

Postgres-backed checkpointer lifecycle (§40). Persists in-flight graph
execution state after every node — recovery from a mid-request
crash/redeploy, and the substrate for a future interrupt()-based
human-in-the-loop flow. Keyed by trace_id (§40's own text), not
conversation_id — conversation-level history is a separate concern
already owned by the conversations/messages tables.

Uses langgraph-checkpoint-postgres's AsyncPostgresSaver, which is built
on psycopg/psycopg-pool — a genuinely separate driver and connection
pool from this app's own SQLAlchemy+asyncpg stack (app/db/session.py).
It manages its own tables entirely: AsyncPostgresSaver.setup() creates
them (confirmed via its own docstring: "MUST be called directly by the
user the first time checkpointer is used"), independent of this
project's Alembic migration chain.

AsyncPostgresSaver.from_conn_string() is an async context manager, so
the real checkpointer can only be constructed inside an async lifespan
(app/main.py), never at plain module-import time — that's why the
existing `graph = build_graph()` singleton at the bottom of graph.py
stays checkpointer-less; this is only used for the app's real
request-serving graph, built fresh at FastAPI startup.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver


@asynccontextmanager
async def build_checkpointer(conn_string: str) -> AsyncIterator[AsyncPostgresSaver]:
    async with AsyncPostgresSaver.from_conn_string(conn_string) as checkpointer:
        await checkpointer.setup()
        yield checkpointer
