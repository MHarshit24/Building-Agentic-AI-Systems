"""
tests/unit/test_users_crud.py

L1/L2 coverage (§19) for the admin-only user-management CRUD endpoints
(app/api/routes_users.py) — production-readiness gap analysis, item B.3.
Real Postgres test DB via tests/conftest.py's fixtures, no LLM involved.
"""

from __future__ import annotations

import pytest

from app.auth.security import verify_password
from app.db.models import UserRole
from app.db.session import async_session_maker


async def _login(client, user, password) -> str:
    resp = await client.post("/auth/login", json={"email": user.email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# RBAC gating — every endpoint in this router is admin-only
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method,path,json_body",
    [
        ("POST", "/users", {"email": "x@test.local", "password": "whatever123", "role": "support_agent"}),
        ("GET", "/users", None),
        ("GET", "/users/1", None),
        ("PATCH", "/users/1", {}),
        ("POST", "/users/1/deactivate", None),
        ("POST", "/users/1/reactivate", None),
    ],
)
async def test_non_admin_gets_403_on_every_users_endpoint(client, support_agent_user, method, path, json_body):
    user, password = support_agent_user
    token = await _login(client, user, password)

    resp = await client.request(method, path, headers=_auth_header(token), json=json_body)
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_can_create_user_with_hashed_password(client, admin_user, make_user):
    admin, admin_password = admin_user
    token = await _login(client, admin, admin_password)

    email = "new-agent@test.local"
    resp = await client.post(
        "/users",
        headers=_auth_header(token),
        json={"email": email, "password": "Sup3r-Secret!", "role": "support_agent"},
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == email
    assert body["role"] == "support_agent"
    assert body["is_active"] is True
    assert "password_hash" not in body
    assert "password" not in body

    async with async_session_maker() as session:
        from sqlalchemy import select

        from app.db.models import User

        row = (await session.execute(select(User).where(User.email == email))).scalar_one()
        assert row.password_hash != "Sup3r-Secret!"
        assert verify_password("Sup3r-Secret!", row.password_hash)
        await session.delete(row)
        await session.commit()


@pytest.mark.asyncio
async def test_create_user_duplicate_email_returns_409(client, admin_user, support_agent_user):
    admin, admin_password = admin_user
    existing_user, _ = support_agent_user
    token = await _login(client, admin, admin_password)

    resp = await client.post(
        "/users",
        headers=_auth_header(token),
        json={"email": existing_user.email, "password": "whatever123", "role": "support_agent"},
    )
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# List / get
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_can_list_and_get_users(client, admin_user, support_agent_user):
    admin, admin_password = admin_user
    sa_user, _ = support_agent_user
    token = await _login(client, admin, admin_password)

    list_resp = await client.get("/users", headers=_auth_header(token))
    assert list_resp.status_code == 200
    body = list_resp.json()
    assert body["total"] >= 2
    assert any(u["user_id"] == sa_user.user_id for u in body["users"])

    get_resp = await client.get(f"/users/{sa_user.user_id}", headers=_auth_header(token))
    assert get_resp.status_code == 200
    assert get_resp.json()["email"] == sa_user.email


@pytest.mark.asyncio
async def test_get_nonexistent_user_returns_404(client, admin_user):
    admin, admin_password = admin_user
    token = await _login(client, admin, admin_password)

    resp = await client.get("/users/999999999", headers=_auth_header(token))
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Deactivate / reactivate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deactivate_then_reactivate_round_trip(client, admin_user, support_agent_user):
    admin, admin_password = admin_user
    sa_user, _ = support_agent_user
    token = await _login(client, admin, admin_password)

    deactivate_resp = await client.post(f"/users/{sa_user.user_id}/deactivate", headers=_auth_header(token))
    assert deactivate_resp.status_code == 200
    assert deactivate_resp.json()["is_active"] is False

    reactivate_resp = await client.post(f"/users/{sa_user.user_id}/reactivate", headers=_auth_header(token))
    assert reactivate_resp.status_code == 200
    assert reactivate_resp.json()["is_active"] is True


@pytest.mark.asyncio
async def test_deactivated_user_existing_token_still_authenticates_within_lifetime(
    client, admin_user, support_agent_user
):
    """Decided tradeoff (production-readiness gap analysis, item B.3):
    revocation is enforced at /auth/login, not inside get_current_user —
    an already-issued token remains valid for the rest of its own
    (<=30 minute) lifetime after deactivation. This proves that's real
    and intentional, not an oversight."""
    admin, admin_password = admin_user
    sa_user, sa_password = support_agent_user
    admin_token = await _login(client, admin, admin_password)
    sa_token = await _login(client, sa_user, sa_password)

    deactivate_resp = await client.post(
        f"/users/{sa_user.user_id}/deactivate", headers=_auth_header(admin_token)
    )
    assert deactivate_resp.status_code == 200

    # Existing token still authenticates (logout is a harmless authenticated no-op here).
    still_valid_resp = await client.post("/auth/logout", headers=_auth_header(sa_token))
    assert still_valid_resp.status_code == 200


@pytest.mark.asyncio
async def test_deactivated_user_cannot_obtain_new_login_token(client, admin_user, support_agent_user):
    admin, admin_password = admin_user
    sa_user, sa_password = support_agent_user
    admin_token = await _login(client, admin, admin_password)

    await client.post(f"/users/{sa_user.user_id}/deactivate", headers=_auth_header(admin_token))

    resp = await client.post("/auth/login", json={"email": sa_user.email, "password": sa_password})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_deactivated_user_login_rejection_is_generic_same_as_bad_credentials(
    client, admin_user, support_agent_user
):
    """Same anti-enumeration discipline as everywhere else in this flow —
    a deactivated account's rejection must not be distinguishable from a
    wrong-password rejection."""
    admin, admin_password = admin_user
    sa_user, sa_password = support_agent_user
    admin_token = await _login(client, admin, admin_password)

    await client.post(f"/users/{sa_user.user_id}/deactivate", headers=_auth_header(admin_token))

    deactivated_resp = await client.post(
        "/auth/login", json={"email": sa_user.email, "password": sa_password}
    )
    wrong_password_resp = await client.post(
        "/auth/login", json={"email": sa_user.email, "password": "definitely-wrong"}
    )

    assert deactivated_resp.status_code == wrong_password_resp.status_code == 401
    assert deactivated_resp.json()["detail"] == wrong_password_resp.json()["detail"]


# ---------------------------------------------------------------------------
# Self-lockout guards
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_cannot_deactivate_own_account(client, admin_user, make_user):
    """A second active admin exists, so this isn't the last-admin case —
    proves the self-guard fires independently of the last-admin guard."""
    admin, admin_password = admin_user
    await make_user(role=UserRole.admin)
    token = await _login(client, admin, admin_password)

    resp = await client.post(f"/users/{admin.user_id}/deactivate", headers=_auth_header(token))
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_admin_cannot_demote_own_role(client, admin_user, make_user):
    admin, admin_password = admin_user
    await make_user(role=UserRole.admin)
    token = await _login(client, admin, admin_password)

    resp = await client.patch(
        f"/users/{admin.user_id}", headers=_auth_header(token), json={"role": "support_agent"}
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_cannot_deactivate_last_remaining_active_admin(client, make_user):
    """The guard only matters when exactly one active admin remains and a
    DIFFERENT actor targets them (self-targeting is already blocked by
    the separate self-guard). The only realistic way to reach that as a
    *different* actor is the decided token-lifetime tradeoff itself
    (production-readiness gap analysis, item B.3): admin_y logs in while
    still active, is then deactivated by admin_x, and admin_y's own
    still-valid token is the "different actor" attempting to act on
    admin_x — who is by then the sole remaining active admin."""
    admin_x, password_x = await make_user(role=UserRole.admin)
    admin_y, password_y = await make_user(role=UserRole.admin)

    token_y = await _login(client, admin_y, password_y)  # obtained while admin_y is still active
    token_x = await _login(client, admin_x, password_x)

    deactivate_y_resp = await client.post(f"/users/{admin_y.user_id}/deactivate", headers=_auth_header(token_x))
    assert deactivate_y_resp.status_code == 200  # fine: 2 active admins before this call

    # admin_x is now the sole remaining active admin; admin_y's token is
    # still valid (the accepted <=30 minute window) and is a genuinely
    # different actor from admin_x.
    demote_x_resp = await client.patch(
        f"/users/{admin_x.user_id}", headers=_auth_header(token_y), json={"role": "support_agent"}
    )
    assert demote_x_resp.status_code == 400

    deactivate_x_resp = await client.post(f"/users/{admin_x.user_id}/deactivate", headers=_auth_header(token_y))
    assert deactivate_x_resp.status_code == 400


@pytest.mark.asyncio
async def test_deactivating_non_last_admin_succeeds(client, make_user):
    """Positive-path counterpart — the guard must not block ordinary admin
    turnover when >=2 active admins remain."""
    admin_a, password_a = await make_user(role=UserRole.admin)
    admin_b, _ = await make_user(role=UserRole.admin)
    token_a = await _login(client, admin_a, password_a)

    resp = await client.post(f"/users/{admin_b.user_id}/deactivate", headers=_auth_header(token_a))
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False
