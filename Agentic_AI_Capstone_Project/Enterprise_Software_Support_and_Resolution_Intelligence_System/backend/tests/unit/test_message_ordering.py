"""
tests/unit/test_message_ordering.py

Regression coverage for a real, confirmed bug: message history ordering
was sorted by created_at ALONE, with no tie-breaker. _persist_and_finalize()
(routes_chat.py) inserts a turn's user and assistant Message rows in the
same transaction, and Message.created_at's server_default=func.now()
returns Postgres's transaction timestamp — identical for every statement
in that transaction, not a fresh per-row clock read. Ties under
`ORDER BY created_at` are NOT guaranteed to resolve in insertion order —
confirmed as the real cause of a reported frontend symptom ("the answer
displayed before the query, only in some chats, not all" — exactly the
signature of an unresolved sort tie, not a frontend rendering bug).

Fix: both real call sites (routes_chat.py's _load_chat_history, routes_
conversations.py's get_conversation) now sort by
(created_at, message_id) — message_id is a real, deterministic
secondary key since it's an autoincrement PK assigned in insertion order.

These tests construct the exact failure condition directly (two messages
with an IDENTICAL created_at, simulating same-transaction inserts) rather
than relying on real wall-clock timing racing to reproduce the tie.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import delete

from app.api.routes_chat import _load_chat_history
from app.db.models import Conversation, ConversationStatus, Message
from app.db.session import async_session_maker


async def _login(client, user, password) -> str:
    resp = await client.post("/auth/login", json={"email": user.email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def make_conversation_with_tied_messages():
    """Inserts a conversation with a user message followed by an assistant
    message, both given the exact SAME created_at — the real condition
    _persist_and_finalize() produces via Postgres's transaction-timestamp
    semantics, reproduced directly rather than raced against wall-clock
    timing."""
    created_ids: list[str] = []

    async def _make(handled_by_user_id: int) -> str:
        conversation_id = str(uuid4())
        tied_timestamp = datetime.now(timezone.utc)
        async with async_session_maker() as session:
            session.add(
                Conversation(
                    conversation_id=conversation_id,
                    customer_id=1,
                    handled_by_user_id=handled_by_user_id,
                    status=ConversationStatus.open,
                )
            )
            session.add(
                Message(
                    conversation_id=conversation_id,
                    role="user",
                    content="What is my account status?",
                    trace_id=f"trace_{uuid4().hex[:12]}",
                    created_at=tied_timestamp,
                )
            )
            session.add(
                Message(
                    conversation_id=conversation_id,
                    role="assistant",
                    content="Your account is Active.",
                    trace_id=f"trace_{uuid4().hex[:12]}",
                    created_at=tied_timestamp,
                )
            )
            await session.commit()
        created_ids.append(conversation_id)
        return conversation_id

    yield _make

    if created_ids:
        async with async_session_maker() as session:
            await session.execute(delete(Message).where(Message.conversation_id.in_(created_ids)))
            await session.execute(delete(Conversation).where(Conversation.conversation_id.in_(created_ids)))
            await session.commit()


@pytest.mark.asyncio
async def test_load_chat_history_orders_user_before_assistant_despite_tied_created_at(
    support_agent_user, make_conversation_with_tied_messages
):
    user, _ = support_agent_user
    conversation_id = await make_conversation_with_tied_messages(user.user_id)

    async with async_session_maker() as db:
        history = await _load_chat_history(db, conversation_id)

    assert [turn["role"] for turn in history] == ["user", "assistant"]


@pytest.mark.asyncio
async def test_get_conversation_orders_user_before_assistant_despite_tied_created_at(
    client, support_agent_user, make_conversation_with_tied_messages
):
    user, password = support_agent_user
    conversation_id = await make_conversation_with_tied_messages(user.user_id)

    token = await _login(client, user, password)
    resp = await client.get(f"/conversations/{conversation_id}", headers=_auth_header(token))

    assert resp.status_code == 200
    roles = [m["role"] for m in resp.json()["messages"]]
    assert roles == ["user", "assistant"], (
        f"expected [user, assistant], got {roles} — created_at sort-tie regression?"
    )
