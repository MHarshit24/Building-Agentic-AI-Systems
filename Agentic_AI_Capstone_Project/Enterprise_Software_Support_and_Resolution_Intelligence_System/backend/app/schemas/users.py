"""
app/schemas/users.py

Request/response models for the user-management endpoints
(app/api/routes_users.py) — production-readiness gap analysis, item B.3.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.db.models import UserRole


class UserCreateRequest(BaseModel):
    email: str
    password: str
    role: UserRole


class UserUpdateRequest(BaseModel):
    email: str | None = None
    role: UserRole | None = None


class UserResponse(BaseModel):
    user_id: int
    email: str
    role: UserRole
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None


class UserListResponse(BaseModel):
    users: list[UserResponse]
    total: int
