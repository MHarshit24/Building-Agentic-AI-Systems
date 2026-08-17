"""
app/api/routes_users.py

Admin-only user management CRUD — production-readiness gap analysis,
item B.3. Prior to this file there was zero programmatic way to create,
list, update, or deactivate a user account (only scripts/seed_synthetic_
data.py or hand-run SQL). Every endpoint reuses existing, proven
conventions exactly: require_admin (app/middleware/rbac_check.py),
hash_password() (app/auth/security.py), the same rate-limit tiers and
pagination shape already used by routes_ingest.py/routes_conversations.py.

Deactivation (not hard deletion) matches this project's own established
soft-retire philosophy (IngestedAsset.is_active, NotificationStatus) —
users.is_active is a new column (see the accompanying Alembic migration),
never a DELETE.

Self-lockout guards: neither role-change-away-from-admin nor deactivation
may ever leave the system with zero active admin accounts, and an admin
may never demote or deactivate their own account. Both are real
production gaps a system calling itself production-grade cannot ship
without — this is the failure mode user management exists to prevent.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import hash_password
from app.db.models import User, UserRole
from app.db.session import get_db
from app.middleware.rate_limit import limiter
from app.middleware.rbac_check import require_admin
from app.schemas.users import (
    UserCreateRequest,
    UserListResponse,
    UserResponse,
    UserUpdateRequest,
)

router = APIRouter(prefix="/users", tags=["users"])


async def _count_active_admins(db: AsyncSession) -> int:
    result = await db.execute(
        select(func.count()).select_from(User).where(User.role == UserRole.admin, User.is_active.is_(True))
    )
    return result.scalar_one()


async def _get_user_or_404(db: AsyncSession, user_id: int) -> User:
    result = await db.execute(select(User).where(User.user_id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def create_user(
    request: Request,
    body: UserCreateRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
) -> UserResponse:
    email = body.email.lower()
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A user with this email already exists")

    new_user = User(email=email, password_hash=hash_password(body.password), role=body.role)
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return UserResponse.model_validate(new_user, from_attributes=True)


@router.get("", response_model=UserListResponse)
@limiter.limit("60/minute")
async def list_users(
    request: Request,
    limit: int = Query(default=50, le=100, ge=1),
    offset: int = Query(default=0, ge=0),
    role: UserRole | None = None,
    is_active: bool | None = None,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
) -> UserListResponse:
    stmt = select(User)
    count_stmt = select(func.count()).select_from(User)
    if role is not None:
        stmt = stmt.where(User.role == role)
        count_stmt = count_stmt.where(User.role == role)
    if is_active is not None:
        stmt = stmt.where(User.is_active == is_active)
        count_stmt = count_stmt.where(User.is_active == is_active)

    total = (await db.execute(count_stmt)).scalar_one()
    rows = (await db.execute(stmt.order_by(User.user_id).limit(limit).offset(offset))).scalars().all()

    return UserListResponse(
        users=[UserResponse.model_validate(row, from_attributes=True) for row in rows],
        total=total,
    )


@router.get("/{user_id}", response_model=UserResponse)
@limiter.limit("60/minute")
async def get_user(
    request: Request,
    user_id: int,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
) -> UserResponse:
    target = await _get_user_or_404(db, user_id)
    return UserResponse.model_validate(target, from_attributes=True)


@router.patch("/{user_id}", response_model=UserResponse)
@limiter.limit("10/minute")
async def update_user(
    request: Request,
    user_id: int,
    body: UserUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
) -> UserResponse:
    target = await _get_user_or_404(db, user_id)

    is_self = user_id == user["user_id"]
    is_demotion = body.role is not None and body.role != UserRole.admin and target.role == UserRole.admin

    if is_demotion:
        if is_self:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot demote or deactivate your own account",
            )
        if target.is_active and await _count_active_admins(db) <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot remove the last remaining active admin account",
            )

    if body.email is not None:
        target.email = body.email.lower()
    if body.role is not None:
        target.role = body.role

    await db.commit()
    await db.refresh(target)
    return UserResponse.model_validate(target, from_attributes=True)


@router.post("/{user_id}/deactivate", response_model=UserResponse)
@limiter.limit("10/minute")
async def deactivate_user(
    request: Request,
    user_id: int,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
) -> UserResponse:
    target = await _get_user_or_404(db, user_id)
    is_self = user_id == user["user_id"]

    if is_self:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot demote or deactivate your own account",
        )
    if target.role == UserRole.admin and target.is_active and await _count_active_admins(db) <= 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove the last remaining active admin account",
        )

    target.is_active = False
    await db.commit()
    await db.refresh(target)
    return UserResponse.model_validate(target, from_attributes=True)


@router.post("/{user_id}/reactivate", response_model=UserResponse)
@limiter.limit("10/minute")
async def reactivate_user(
    request: Request,
    user_id: int,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
) -> UserResponse:
    target = await _get_user_or_404(db, user_id)
    target.is_active = True
    await db.commit()
    await db.refresh(target)
    return UserResponse.model_validate(target, from_attributes=True)
