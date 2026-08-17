"""
tests/unit/test_conversation_archive.py

L2 coverage (§19) for POST /conversations/{id}/archive and .../unarchive
— production-readiness gap analysis, deletion item 2. Reversible status
transition, not a delete; RBAC matches get_conversation's own existing
assigned-agent-or-admin rule exactly.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
import pytest_asyncio

from app.db.models import Conversation, ConversationStatus
from app.db.session import async_session_maker


async def _login(client, user, password) -> str:
    resp = await client.post("/auth/login", json={"email": user.email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def make_conversation():
    created_ids: list[str] = []

    async def _make_conversation(handled_by_user_id: int, **overrides) -> Conversation:
        conversation_id = str(uuid4())
        defaults = {
            "conversation_id": conversation_id,
            "customer_id": 1,
            "handled_by_user_id": handled_by_user_id,
            "status": ConversationStatus.open,
        }
        defaults.update(overrides)
        async with async_session_maker() as session:
            conversation = Conversation(**defaults)
            session.add(conversation)
            await session.commit()
            await session.refresh(conversation)
            created_ids.append(conversation.conversation_id)
            return conversation

    yield _make_conversation

    if created_ids:
        async with async_session_maker() as session:
            from sqlalchemy import delete

            await session.execute(delete(Conversation).where(Conversation.conversation_id.in_(created_ids)))
            await session.commit()


@pytest.mark.asyncio
async def test_assigned_agent_can_archive_own_conversation(client, support_agent_user, make_conversation):
    user, password = support_agent_user
    token = await _login(client, user, password)
    conversation = await make_conversation(handled_by_user_id=user.user_id)

    resp = await client.post(f"/conversations/{conversation.conversation_id}/archive", headers=_auth_header(token))
    assert resp.status_code == 200
    assert resp.json()["status"] == "archived"


@pytest.mark.asyncio
async def test_different_agent_cannot_archive_conversation_gets_404(
    client, make_user, make_conversation
):
    agent_a, _ = await make_user()
    agent_b, password_b = await make_user()
    conversation = await make_conversation(handled_by_user_id=agent_a.user_id)

    token_b = await _login(client, agent_b, password_b)
    resp = await client.post(f"/conversations/{conversation.conversation_id}/archive", headers=_auth_header(token_b))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_admin_can_archive_any_conversation(client, admin_user, make_user, make_conversation):
    admin, admin_password = admin_user
    agent, _ = await make_user()
    conversation = await make_conversation(handled_by_user_id=agent.user_id)

    token = await _login(client, admin, admin_password)
    resp = await client.post(f"/conversations/{conversation.conversation_id}/archive", headers=_auth_header(token))
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_archived_conversation_excluded_from_default_list_included_with_flag(
    client, support_agent_user, make_conversation
):
    user, password = support_agent_user
    token = await _login(client, user, password)
    conversation = await make_conversation(handled_by_user_id=user.user_id)

    archive_resp = await client.post(
        f"/conversations/{conversation.conversation_id}/archive", headers=_auth_header(token)
    )
    assert archive_resp.status_code == 200

    default_list = await client.get("/conversations", headers=_auth_header(token))
    default_ids = {c["conversation_id"] for c in default_list.json()["conversations"]}
    assert conversation.conversation_id not in default_ids

    full_list = await client.get("/conversations?include_archived=true", headers=_auth_header(token))
    full_ids = {c["conversation_id"] for c in full_list.json()["conversations"]}
    assert conversation.conversation_id in full_ids


@pytest.mark.asyncio
async def test_unarchive_restores_open_status(client, support_agent_user, make_conversation):
    user, password = support_agent_user
    token = await _login(client, user, password)
    conversation = await make_conversation(handled_by_user_id=user.user_id)

    await client.post(f"/conversations/{conversation.conversation_id}/archive", headers=_auth_header(token))

    resp = await client.post(f"/conversations/{conversation.conversation_id}/unarchive", headers=_auth_header(token))
    assert resp.status_code == 200
    assert resp.json()["status"] == "open"


@pytest.mark.asyncio
async def test_unarchive_non_archived_conversation_returns_400(client, support_agent_user, make_conversation):
    user, password = support_agent_user
    token = await _login(client, user, password)
    conversation = await make_conversation(handled_by_user_id=user.user_id, status=ConversationStatus.closed)

    resp = await client.post(f"/conversations/{conversation.conversation_id}/unarchive", headers=_auth_header(token))
    assert resp.status_code == 400
