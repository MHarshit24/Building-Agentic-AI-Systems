"""
app/api/routes_auth.py

POST /auth/login, POST /auth/logout — section 16/17 of Blueprint.md.

POST /auth/password-reset/request, POST /auth/password-reset/confirm —
production-readiness gap analysis, item B.4. Reuses mailtrap_client.py's
send_email() as-is (no new integration) and matches /auth/login's own
anti-enumeration discipline (never reveal which check failed) and
IP-keyed rate-limit shape exactly.

POST /auth/refresh — frontend integration pass. /auth/login always issued
a refresh token, but no endpoint ever redeemed it, forcing a full
re-login every 30 minutes. Rotates on every use: the presented refresh
token is blacklisted and a new access/refresh pair is issued.

POST /auth/register — reverses blueprint.md §22.1's original "no self-
registration" decision, at the project owner's explicit request: a user
that doesn't exist yet can sign up directly instead of depending on
scripts/seed_synthetic_data.py for account provisioning. Always creates a
support_agent (see RegisterRequest's own docstring for why that's
structural, not just a default value) and auto-logs the new account in.
"""

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt_handler import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    blacklist_token,
    create_access_token,
    create_refresh_token,
    is_token_blacklisted,
    verify_access_token,
)
from app.auth.security import generate_reset_token, hash_password, hash_reset_token, verify_password
from app.config import get_settings
from app.db.models import PasswordResetToken, User, UserRole
from app.db.session import get_db
from app.middleware.jwt_auth import get_current_user
from app.middleware.rate_limit import limiter
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    LogoutResponse,
    PasswordResetConfirmRequest,
    PasswordResetConfirmResponse,
    PasswordResetRequestRequest,
    PasswordResetRequestResponse,
    RefreshRequest,
    RefreshResponse,
    RegisterRequest,
)
from mcp_servers.notification_mcp.mailtrap_client import send_email

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

_GENERIC_RESET_REQUEST_MESSAGE = "If an account exists for that email, a reset link has been sent."


@router.post("/register", response_model=LoginResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/15minute")  # same IP-keyed shape as /auth/login — no user identity exists pre-account
async def register(
    request: Request,
    body: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    """
    Public. Creates a new account and immediately logs it in (same
    response shape as POST /login) — removes the previous hard dependency
    on scripts/seed_synthetic_data.py for provisioning any account at all.

    Always creates a support_agent — there is no role field on
    RegisterRequest for a client to set, so "self-service signup always
    gets the default, least-privileged role" is enforced structurally, not
    just by a check. Admin accounts remain exclusively provisioned via the
    existing admin-only POST /users.
    """
    email = body.email.lower()
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A user with this email already exists")

    new_user = User(
        email=email,
        password_hash=hash_password(body.password),
        role=UserRole.support_agent,
        last_login_at=datetime.now(timezone.utc),
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    token_payload = {
        "user_id": new_user.user_id,
        "role": new_user.role.value,
        "email": new_user.email,
    }
    access_token = create_access_token(token_payload)
    refresh_token = create_refresh_token(token_payload)

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        role=new_user.role.value,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/login", response_model=LoginResponse)
@limiter.limit("5/15minute")  # keyed by source IP — no user identity exists before login succeeds (§16.1)
async def login(
    request: Request,
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    """
    Public. Verifies email+password, returns a short-lived access token
    plus a refresh token. Generic 401 on any failure (wrong email, wrong
    password, or a deactivated account) — never reveals which one was
    the reason.
    """
    result = await db.execute(select(User).where(User.email == body.email.lower()))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    token_payload = {
        "user_id": user.user_id,
        "role": user.role.value,
        "email": user.email,
    }
    access_token = create_access_token(token_payload)
    refresh_token = create_refresh_token(token_payload)

    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        role=user.role.value,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/refresh", response_model=RefreshResponse)
@limiter.limit("5/15minute")  # same IP-keyed shape as /auth/login — no verified user identity until the token checks out
async def refresh(
    request: Request,
    body: RefreshRequest,
) -> RefreshResponse:
    """
    Public (the refresh token itself is the auth). A refresh token has
    always been issued at login (§16), but nothing previously redeemed
    it — access tokens expire after 30 minutes and the only recovery was
    a full re-login. Verifies the supplied token is a well-formed,
    non-blacklisted `type: "refresh"` token, then issues a brand-new
    access/refresh pair and blacklists the old refresh token's jti
    (rotation) so it can't be replayed after this call.
    """
    payload = verify_access_token(body.refresh_token)  # generic decode+verify despite the name — works for any token type
    if payload is None or payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")

    jti = payload.get("jti")
    if jti and await is_token_blacklisted(jti):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")

    token_payload = {
        "user_id": payload["user_id"],
        "role": payload["role"],
        "email": payload["email"],
    }
    new_access_token = create_access_token(token_payload)
    new_refresh_token = create_refresh_token(token_payload)

    exp = payload.get("exp")
    if jti and exp:
        await blacklist_token(jti, datetime.fromtimestamp(exp, tz=timezone.utc))

    return RefreshResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/logout", response_model=LogoutResponse)
async def logout(user: dict = Depends(get_current_user)) -> LogoutResponse:
    """
    Authenticated, any role. Blacklists the current token's jti in Redis
    until its natural expiry, per §16 — JWTs are stateless and can't be
    deleted server-side, so this is how "logout" actually works.
    """
    jti = user.get("jti")
    exp = user.get("exp")
    if jti and exp:
        expires_at = datetime.fromtimestamp(exp, tz=timezone.utc)
        await blacklist_token(jti, expires_at)
    else:
        logger.warning("Logout called with a token missing jti/exp claims — nothing blacklisted.")

    return LogoutResponse(status="logged_out")


@router.post("/password-reset/request", response_model=PasswordResetRequestResponse, status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("5/15minute")  # same IP-keyed shape as /auth/login — no user identity exists pre-auth
async def request_password_reset(
    request: Request,
    body: PasswordResetRequestRequest,
    db: AsyncSession = Depends(get_db),
) -> PasswordResetRequestResponse:
    """
    Public. Always returns the same 202 + generic message regardless of
    whether the email exists or the send actually succeeds — the direct
    analog of /auth/login's generic 401. Only does real work (token
    generation, storage, email dispatch) when a matching active user is
    found; never raises on a Mailtrap failure (send_email itself never
    raises either).
    """
    result = await db.execute(select(User).where(User.email == body.email.lower()))
    user = result.scalar_one_or_none()

    if user is not None and user.is_active:
        settings = get_settings()
        raw_token = generate_reset_token()
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.password_reset_token_expiry_minutes)
        db.add(PasswordResetToken(user_id=user.user_id, token_hash=hash_reset_token(raw_token), expires_at=expires_at))
        await db.commit()

        await send_email(
            to=user.email,
            subject="Password reset request",
            body=(
                "A password reset was requested for your account.\n\n"
                f"Reset token: {raw_token}\n\n"
                f"This token expires in {settings.password_reset_token_expiry_minutes} minutes. "
                "If you did not request this, you can safely ignore this email."
            ),
        )

    return PasswordResetRequestResponse(message=_GENERIC_RESET_REQUEST_MESSAGE)


@router.post("/password-reset/confirm", response_model=PasswordResetConfirmResponse)
@limiter.limit("5/15minute")
async def confirm_password_reset(
    request: Request,
    body: PasswordResetConfirmRequest,
    db: AsyncSession = Depends(get_db),
) -> PasswordResetConfirmResponse:
    """
    Public (the token itself is the auth). Generic 400 on any failure —
    unknown token, expired token, or already-used token are all
    indistinguishable from the response, same anti-enumeration discipline
    as everywhere else in this flow.
    """
    token_hash = hash_reset_token(body.token)
    result = await db.execute(select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash))
    reset_token = result.scalar_one_or_none()

    now = datetime.now(timezone.utc)
    if (
        reset_token is None
        or reset_token.used_at is not None
        or reset_token.expires_at < now
    ):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token")

    user_result = await db.execute(select(User).where(User.user_id == reset_token.user_id))
    user = user_result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token")

    user.password_hash = hash_password(body.new_password)
    reset_token.used_at = now
    await db.commit()

    return PasswordResetConfirmResponse(status="password_reset")