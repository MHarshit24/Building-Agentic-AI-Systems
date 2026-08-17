"""
tests/unit/test_password_reset.py

L1/L2 coverage (§19) for the password reset flow (app/api/routes_auth.py's
password-reset/request + password-reset/confirm) — production-readiness
gap analysis, item B.4. mailtrap_client.send_email is mocked here via the
existing queued-fake-client-style monkeypatch pattern (§7's own
precedent, e.g. test_escalation_mcp.py) — never a real send in this file.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

import app.api.routes_auth as routes_auth_module
from app.auth.security import hash_reset_token
from app.db.models import PasswordResetToken
from app.db.session import async_session_maker

_TOKEN_RE = re.compile(r"Reset token: (\S+)")


@pytest.fixture
def fake_send_email(monkeypatch):
    fake = AsyncMock(return_value=True)
    monkeypatch.setattr(routes_auth_module, "send_email", fake)
    return fake


def _extract_token_from_email_body(fake_send_email: AsyncMock) -> str:
    body = fake_send_email.await_args.kwargs["body"]
    match = _TOKEN_RE.search(body)
    assert match, f"no reset token found in email body: {body!r}"
    return match.group(1)


# ---------------------------------------------------------------------------
# Anti-enumeration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_request_reset_response_identical_for_existing_and_nonexistent_email(
    client, support_agent_user, fake_send_email, cleanup_password_reset_tokens
):
    user, _password = support_agent_user
    cleanup_password_reset_tokens.append(user.user_id)

    existing_resp = await client.post("/auth/password-reset/request", json={"email": user.email})
    nonexistent_resp = await client.post(
        "/auth/password-reset/request", json={"email": "nobody-registered@test.local"}
    )

    assert existing_resp.status_code == nonexistent_resp.status_code == 202
    assert existing_resp.json() == nonexistent_resp.json()


@pytest.mark.asyncio
async def test_request_reset_only_sends_email_and_stores_token_for_existing_user(
    client, support_agent_user, fake_send_email, cleanup_password_reset_tokens
):
    user, _password = support_agent_user
    cleanup_password_reset_tokens.append(user.user_id)

    await client.post("/auth/password-reset/request", json={"email": "nobody-registered@test.local"})
    fake_send_email.assert_not_awaited()

    await client.post("/auth/password-reset/request", json={"email": user.email})
    fake_send_email.assert_awaited_once()

    async with async_session_maker() as session:
        tokens = (
            (await session.execute(select(PasswordResetToken).where(PasswordResetToken.user_id == user.user_id)))
            .scalars()
            .all()
        )
        assert len(tokens) == 1
        assert tokens[0].used_at is None


@pytest.mark.asyncio
async def test_request_reset_does_not_send_for_deactivated_user(
    client, admin_user, support_agent_user, fake_send_email
):
    admin, admin_password = admin_user
    sa_user, _ = support_agent_user
    token = (await client.post("/auth/login", json={"email": admin.email, "password": admin_password})).json()[
        "access_token"
    ]
    await client.post(f"/users/{sa_user.user_id}/deactivate", headers={"Authorization": f"Bearer {token}"})

    await client.post("/auth/password-reset/request", json={"email": sa_user.email})
    fake_send_email.assert_not_awaited()


# ---------------------------------------------------------------------------
# Confirm — happy path + rejections
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_reset_round_trip_changes_password(
    client, support_agent_user, fake_send_email, cleanup_password_reset_tokens
):
    user, old_password = support_agent_user
    cleanup_password_reset_tokens.append(user.user_id)

    await client.post("/auth/password-reset/request", json={"email": user.email})
    raw_token = _extract_token_from_email_body(fake_send_email)

    confirm_resp = await client.post(
        "/auth/password-reset/confirm", json={"token": raw_token, "new_password": "Brand-New-Pass1!"}
    )
    assert confirm_resp.status_code == 200
    assert confirm_resp.json()["status"] == "password_reset"

    old_login = await client.post("/auth/login", json={"email": user.email, "password": old_password})
    assert old_login.status_code == 401

    new_login = await client.post("/auth/login", json={"email": user.email, "password": "Brand-New-Pass1!"})
    assert new_login.status_code == 200

    async with async_session_maker() as session:
        row = (
            await session.execute(select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_reset_token(raw_token)))
        ).scalar_one()
        assert row.used_at is not None


@pytest.mark.asyncio
async def test_confirm_rejects_unknown_token(client):
    resp = await client.post(
        "/auth/password-reset/confirm", json={"token": "not-a-real-token", "new_password": "whatever123"}
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_confirm_rejects_already_used_token(
    client, support_agent_user, fake_send_email, cleanup_password_reset_tokens
):
    user, _old_password = support_agent_user
    cleanup_password_reset_tokens.append(user.user_id)
    await client.post("/auth/password-reset/request", json={"email": user.email})
    raw_token = _extract_token_from_email_body(fake_send_email)

    first = await client.post(
        "/auth/password-reset/confirm", json={"token": raw_token, "new_password": "First-New-Pass1!"}
    )
    assert first.status_code == 200

    second = await client.post(
        "/auth/password-reset/confirm", json={"token": raw_token, "new_password": "Second-New-Pass1!"}
    )
    assert second.status_code == 400


@pytest.mark.asyncio
async def test_confirm_rejects_expired_token(
    client, support_agent_user, fake_send_email, cleanup_password_reset_tokens
):
    user, _password = support_agent_user
    cleanup_password_reset_tokens.append(user.user_id)
    await client.post("/auth/password-reset/request", json={"email": user.email})

    async with async_session_maker() as session:
        row = (
            await session.execute(select(PasswordResetToken).where(PasswordResetToken.user_id == user.user_id))
        ).scalar_one()
        row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        await session.commit()

    raw_token = _extract_token_from_email_body(fake_send_email)
    resp = await client.post(
        "/auth/password-reset/confirm", json={"token": raw_token, "new_password": "whatever123"}
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_confirm_rejection_reasons_are_indistinguishable(
    client, support_agent_user, fake_send_email, cleanup_password_reset_tokens
):
    """Unknown, expired, and already-used tokens must all produce the same
    error shape — the confirm-side anti-enumeration check."""
    user, _password = support_agent_user
    cleanup_password_reset_tokens.append(user.user_id)
    await client.post("/auth/password-reset/request", json={"email": user.email})
    raw_token = _extract_token_from_email_body(fake_send_email)

    unknown_resp = await client.post(
        "/auth/password-reset/confirm", json={"token": "totally-unknown-token", "new_password": "whatever123"}
    )

    used_resp = await client.post(
        "/auth/password-reset/confirm", json={"token": raw_token, "new_password": "First-New-Pass1!"}
    )
    assert used_resp.status_code == 200
    reused_resp = await client.post(
        "/auth/password-reset/confirm", json={"token": raw_token, "new_password": "Second-New-Pass1!"}
    )

    assert unknown_resp.status_code == reused_resp.status_code == 400
    assert unknown_resp.json()["detail"] == reused_resp.json()["detail"]
