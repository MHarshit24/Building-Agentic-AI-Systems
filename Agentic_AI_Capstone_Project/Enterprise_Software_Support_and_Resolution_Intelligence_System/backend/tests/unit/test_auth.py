"""
tests/unit/test_auth.py

L1/L2 coverage (§19) for POST /auth/login, POST /auth/logout, and RBAC
gating (§16, §16.1). No LLM calls anywhere in this file — auth doesn't
touch the LLM layer at all, so there's nothing to mock here.
"""

from __future__ import annotations

import time
from uuid import UUID, uuid4

import pytest
from jose import jwt
from fastapi import Depends
from sqlalchemy import delete, select

from app.auth.jwt_handler import ACCESS_TOKEN_EXPIRE_MINUTES, ALGORITHM
from app.config import get_settings
from app.db.models import User, UserRole
from app.db.session import async_session_maker
from app.main import app
from app.middleware.rbac_check import require_admin

# ---------------------------------------------------------------------------
# No admin-only endpoint is wired into app.main yet (routes_ingest.py, the
# one §17 endpoint that gates on require_admin, is still an empty stub from
# a later stage). RBAC gating itself — get_current_user -> require_admin —
# already exists and is exactly what §16's RBAC requirement needs tested,
# so a throwaway probe route is registered on the real app here to exercise
# that dependency chain end-to-end over real HTTP, without inventing/
# touching any app source file.
# ---------------------------------------------------------------------------

@app.get("/_test_only/admin_probe")
async def _admin_probe(user: dict = Depends(require_admin)):
    return {"ok": True, "role": user.get("role")}


@pytest.mark.asyncio
async def test_login_success_returns_valid_token_pair(client, support_agent_user):
    user, password = support_agent_user

    resp = await client.post(
        "/auth/login", json={"email": user.email, "password": password}
    )

    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"access_token", "refresh_token", "role", "expires_in"}
    assert body["role"] == "support_agent"
    assert body["expires_in"] == ACCESS_TOKEN_EXPIRE_MINUTES * 60

    settings = get_settings()
    access_payload = jwt.decode(
        body["access_token"], settings.jwt_secret_key, algorithms=[ALGORITHM]
    )
    refresh_payload = jwt.decode(
        body["refresh_token"], settings.jwt_secret_key, algorithms=[ALGORITHM]
    )

    for payload, expected_type in (
        (access_payload, "access"),
        (refresh_payload, "refresh"),
    ):
        assert payload["user_id"] == user.user_id
        assert payload["role"] == "support_agent"
        assert payload["email"] == user.email
        assert payload["type"] == expected_type
        assert payload["exp"] > time.time()
        UUID(payload["jti"])  # raises ValueError if not a valid UUID

    assert access_payload["jti"] != refresh_payload["jti"]


@pytest.mark.asyncio
async def test_login_wrong_password_and_nonexistent_email_return_same_generic_401(
    client, support_agent_user
):
    user, _password = support_agent_user

    resp_wrong_password = await client.post(
        "/auth/login", json={"email": user.email, "password": "definitely-wrong"}
    )
    resp_nonexistent_email = await client.post(
        "/auth/login",
        json={"email": "nobody-registered@test.local", "password": "whatever"},
    )

    assert resp_wrong_password.status_code == 401
    assert resp_nonexistent_email.status_code == 401
    # Same detail message either way — never reveals which one was wrong.
    assert resp_wrong_password.json()["detail"] == resp_nonexistent_email.json()["detail"]


@pytest.mark.asyncio
async def test_login_rate_limit_locks_out_sixth_attempt(client, support_agent_user):
    user, _password = support_agent_user

    for attempt in range(5):
        resp = await client.post(
            "/auth/login", json={"email": user.email, "password": "wrong-password"}
        )
        assert resp.status_code == 401, f"attempt {attempt + 1} should still be under the limit"

    locked_out_resp = await client.post(
        "/auth/login", json={"email": user.email, "password": "wrong-password"}
    )
    assert locked_out_resp.status_code == 429


@pytest.mark.asyncio
async def test_logout_blacklists_token(client, support_agent_user):
    user, password = support_agent_user

    login_resp = await client.post(
        "/auth/login", json={"email": user.email, "password": password}
    )
    access_token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    first_logout = await client.post("/auth/logout", headers=headers)
    assert first_logout.status_code == 200
    assert first_logout.json()["status"] == "logged_out"

    # Same token, second authenticated request — must now fail, since its
    # jti was just blacklisted (§16: JWTs are stateless, logout blacklists
    # instead of deleting).
    second_logout = await client.post("/auth/logout", headers=headers)
    assert second_logout.status_code == 401


@pytest.mark.asyncio
async def test_register_creates_support_agent_and_auto_logs_in(client):
    """Reverses blueprint.md §22.1's original "no self-registration"
    decision, at the project owner's explicit request: an account that
    doesn't exist yet can sign up directly instead of depending on
    scripts/seed_synthetic_data.py."""
    email = f"newuser-{uuid4().hex[:12]}@test.local"

    resp = await client.post("/auth/register", json={"email": email, "password": "Test-Passw0rd!"})

    assert resp.status_code == 201
    body = resp.json()
    assert set(body.keys()) == {"access_token", "refresh_token", "role", "expires_in"}
    assert body["role"] == "support_agent"  # never client-settable — RegisterRequest has no role field at all

    settings = get_settings()
    payload = jwt.decode(body["access_token"], settings.jwt_secret_key, algorithms=[ALGORITHM])
    assert payload["email"] == email
    assert payload["role"] == "support_agent"

    async with async_session_maker() as session:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one()
        assert user.role == UserRole.support_agent
        assert user.is_active is True
        assert user.last_login_at is not None  # auto-login on registration sets it, same as a real login would
        user_id = user.user_id

    async with async_session_maker() as session:
        await session.execute(delete(User).where(User.user_id == user_id))
        await session.commit()


@pytest.mark.asyncio
async def test_register_rejects_duplicate_email(client, support_agent_user):
    user, _password = support_agent_user

    resp = await client.post("/auth/register", json={"email": user.email, "password": "Another-Passw0rd!"})
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_register_rejects_short_password(client):
    email = f"shortpw-{uuid4().hex[:12]}@test.local"
    resp = await client.post("/auth/register", json={"email": email, "password": "short"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_login_degrades_gracefully_when_redis_is_unreachable(client, support_agent_user, monkeypatch):
    """Regression test for a real bug found via manual QA: slowapi's
    swallow_errors=True only protects the rate-CHECK phase
    (Limiter.__evaluate_limits) — request.state.view_rate_limit is only
    ever set on ITS success path, but the header-injection phase that
    runs right after every route unconditionally reads that attribute
    regardless, crashing with AttributeError on a genuinely swallowed
    Redis outage. Simulates the outage by making the limiter's own
    storage backend raise ConnectionError (same exception type Redis
    itself raises), without touching the real test Redis instance other
    tests in this file depend on."""
    import redis.exceptions
    from app.middleware.rate_limit import limiter

    def _raise_connection_error(*args, **kwargs):
        raise redis.exceptions.ConnectionError("simulated Redis outage")

    monkeypatch.setattr(limiter._storage, "incr", _raise_connection_error)

    user, password = support_agent_user
    resp = await client.post("/auth/login", json={"email": user.email, "password": password})

    # The real bug produced a 500 (AttributeError) here; a healthy
    # degradation still completes the login, just without rate-limiting
    # (and without rate-limit response headers) for the duration of the
    # outage.
    assert resp.status_code == 200
    assert set(resp.json().keys()) == {"access_token", "refresh_token", "role", "expires_in"}


@pytest.mark.asyncio
async def test_refresh_issues_new_pair_and_rotates_old_refresh_token(client, support_agent_user):
    """A2: /auth/login always issued a refresh token, but nothing redeemed
    it until now. Confirms refresh -> new working access token, a rotated
    (different) refresh token, and that the OLD refresh token is now
    blacklisted (can't be replayed)."""
    user, password = support_agent_user

    login_resp = await client.post("/auth/login", json={"email": user.email, "password": password})
    old_refresh_token = login_resp.json()["refresh_token"]

    refresh_resp = await client.post("/auth/refresh", json={"refresh_token": old_refresh_token})
    assert refresh_resp.status_code == 200
    body = refresh_resp.json()
    assert set(body.keys()) == {"access_token", "refresh_token", "expires_in"}
    assert body["expires_in"] == ACCESS_TOKEN_EXPIRE_MINUTES * 60
    assert body["refresh_token"] != old_refresh_token

    # New access token actually works against a real protected endpoint.
    logout_resp = await client.post(
        "/auth/logout", headers={"Authorization": f"Bearer {body['access_token']}"}
    )
    assert logout_resp.status_code == 200

    # Old refresh token was blacklisted by the refresh call above — replaying
    # it must now fail, not silently succeed a second time.
    replay_resp = await client.post("/auth/refresh", json={"refresh_token": old_refresh_token})
    assert replay_resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_rejects_an_access_token(client, support_agent_user):
    """An access token is a well-formed, validly-signed JWT too — this
    confirms /auth/refresh actually checks `type: "refresh"` rather than
    accepting any valid token, which would let a live access token be
    used to mint an unbounded chain of new token pairs."""
    user, password = support_agent_user

    login_resp = await client.post("/auth/login", json={"email": user.email, "password": password})
    access_token = login_resp.json()["access_token"]

    resp = await client.post("/auth/refresh", json={"refresh_token": access_token})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_rejects_garbage_token(client):
    resp = await client.post("/auth/refresh", json={"refresh_token": "not-a-real-jwt"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_rbac_admin_only_rejects_support_agent_token(
    client, support_agent_user, admin_user
):
    sa_user, sa_password = support_agent_user
    admin, admin_password = admin_user

    sa_login = await client.post(
        "/auth/login", json={"email": sa_user.email, "password": sa_password}
    )
    admin_login = await client.post(
        "/auth/login", json={"email": admin.email, "password": admin_password}
    )
    sa_token = sa_login.json()["access_token"]
    admin_token = admin_login.json()["access_token"]

    sa_resp = await client.get(
        "/_test_only/admin_probe", headers={"Authorization": f"Bearer {sa_token}"}
    )
    admin_resp = await client.get(
        "/_test_only/admin_probe", headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert sa_resp.status_code == 403
    assert admin_resp.status_code == 200
    assert admin_resp.json()["role"] == "admin"
