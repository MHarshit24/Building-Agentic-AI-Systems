"""
app/schemas/auth.py

Request/response models for POST /auth/login, POST /auth/logout,
POST /auth/password-reset/{request,confirm}, and POST /auth/refresh.
See section 16/17 of Blueprint.md (refresh added post-blueprint, frontend
integration pass — a refresh token was always issued at login but nothing
redeemed it until now).
"""

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=8)
    # No `role` field, deliberately — self-registration always creates a
    # support_agent account (routes_auth.py never reads a role from this
    # body), so there is no field for a client to even attempt to set to
    # "admin". Admin accounts remain provisionable only via the existing
    # admin-only POST /users (schemas/users.py's UserCreateRequest).


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    role: str
    expires_in: int  # seconds until the access token expires


class LogoutResponse(BaseModel):
    status: str


class RefreshRequest(BaseModel):
    refresh_token: str


class RefreshResponse(BaseModel):
    access_token: str
    refresh_token: str  # rotated — the caller must swap its stored refresh token for this one
    expires_in: int  # seconds until the new access token expires


class PasswordResetRequestRequest(BaseModel):
    email: str


class PasswordResetRequestResponse(BaseModel):
    message: str


class PasswordResetConfirmRequest(BaseModel):
    token: str
    new_password: str


class PasswordResetConfirmResponse(BaseModel):
    status: str