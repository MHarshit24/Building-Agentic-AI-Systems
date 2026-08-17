"""
tests/integration/test_rbac_violations.py

§24 metric #13 (Unauthorized Data Access — RBAC): 0 violations, run every
CI cycle, not just once. The 3 exact attack surfaces named in §24's own
table:
  1. Cross-agent conversation access
  2. Non-admin /ingest access
  3. Cross-customer SQL access via sql_tools

Each asserts 0 successes — not "usually blocked," a hard 0. All three
reuse already-built defenses (routes_conversations.py's per-conversation
access check, §29; routes_ingest.py's require_admin dependency; sql_tools/
queries.py's whitelisted customer_id-scoped functions) — no new
authorization mechanism is introduced by this file, it only proves the
existing ones hold.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.db.models import Conversation, ConversationStatus
from app.db.session import async_session_maker
from app.sql_tools.queries import get_tickets


async def _login(client, user, password) -> str:
    resp = await client.post("/auth/login", json={"email": user.email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


# ---------------------------------------------------------------------------
# 1. Cross-agent conversation access
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_support_agent_cannot_view_another_agents_conversation(client, make_user, cleanup_conversations):
    """N=5 independent conversations, all owned by agent A; agent B
    attempts to view each one. 0 successes required — a single 200
    anywhere in this loop is the metric failing, not a fluke."""
    agent_a, _ = await make_user()
    agent_b, password_b = await make_user()

    conversation_ids = []
    async with async_session_maker() as session:
        for _ in range(5):
            conversation_id = str(uuid4())
            session.add(
                Conversation(
                    conversation_id=conversation_id,
                    customer_id=1,
                    handled_by_user_id=agent_a.user_id,
                    status=ConversationStatus.open,
                )
            )
            conversation_ids.append(conversation_id)
        await session.commit()
    cleanup_conversations.extend(conversation_ids)

    token_b = await _login(client, agent_b, password_b)

    successes = 0
    for conversation_id in conversation_ids:
        resp = await client.get(
            f"/conversations/{conversation_id}", headers={"Authorization": f"Bearer {token_b}"}
        )
        if resp.status_code == 200:
            successes += 1
        else:
            assert resp.status_code == 404  # per routes_conversations.py: not-yours reads as not-found

    assert successes == 0


@pytest.mark.asyncio
async def test_admin_can_view_any_agents_conversation(client, make_user, admin_user, cleanup_conversations):
    """Sanity counterpart to the test above — §17's own "admins see all"
    note must still hold; this file isn't accidentally over-restricting."""
    agent_a, _ = await make_user()
    admin, admin_password = admin_user

    conversation_id = str(uuid4())
    async with async_session_maker() as session:
        session.add(
            Conversation(
                conversation_id=conversation_id,
                customer_id=1,
                handled_by_user_id=agent_a.user_id,
                status=ConversationStatus.open,
            )
        )
        await session.commit()
    cleanup_conversations.append(conversation_id)

    token_admin = await _login(client, admin, admin_password)
    resp = await client.get(
        f"/conversations/{conversation_id}", headers={"Authorization": f"Bearer {token_admin}"}
    )
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 2. Non-admin /ingest access
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_support_agent_cannot_call_post_ingest(client, support_agent_user):
    user, password = support_agent_user
    token = await _login(client, user, password)

    resp = await client.post(
        "/ingest",
        files={"file": ("doc.pdf", b"%PDF-1.4 fake", "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_support_agent_cannot_call_get_ingest_status(client, support_agent_user):
    user, password = support_agent_user
    token = await _login(client, user, password)

    resp = await client.get("/ingest/some-job-id", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# 3. Cross-customer SQL access via sql_tools
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_tickets_never_returns_another_customers_rows(make_customer, make_ticket):
    """app/sql_tools/queries.py's get_tickets(customer_id) is the only
    whitelisted way account_validation_node ever reaches support_tickets
    — no free-text SQL construction exists (structurally immune to
    injection by design). This proves the customer_id filter itself is
    correct: querying customer A never leaks customer B's rows, across
    several distinct ticket rows on each side, not just one."""
    customer_a = await make_customer()
    customer_b = await make_customer()

    for i in range(3):
        await make_ticket(customer_id=customer_a.customer_id, issue_category=f"cat_a_{i}")
    for i in range(3):
        await make_ticket(customer_id=customer_b.customer_id, issue_category=f"cat_b_{i}")

    tickets_a = await get_tickets(customer_a.customer_id)

    assert len(tickets_a) == 3
    assert all(t["customer_id"] == customer_a.customer_id for t in tickets_a)
    assert not any(t["customer_id"] == customer_b.customer_id for t in tickets_a)
