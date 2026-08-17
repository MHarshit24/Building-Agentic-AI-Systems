from __future__ import annotations

import re
from typing import Optional, List

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ── Helpers ──────────────────────────────────────────────────────────────────

_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")
_SESSION_ID_RE = re.compile(
    r"^[a-zA-Z0-9_\-]{1,128}$"
)  # UUID, "default", "direct", or custom alphanumeric


def _validate_session_id(value: Optional[str]) -> Optional[str]:
    """Shared validator for optional session_id fields."""
    if value is None:
        return value
    value = value.strip()
    if not _SESSION_ID_RE.match(value):
        raise ValueError(
            "session_id must be 1–128 alphanumeric characters, hyphens, or underscores."
        )
    return value


# ── Auth ──────────────────────────────────────────────────────────────────────

class TokenRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    username: str = Field(
        ...,
        min_length=1,
        max_length=254,
        description="Auth0 user email / username",
    )
    password: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Auth0 user password",
    )

    @field_validator("username")
    @classmethod
    def username_must_be_email(cls, v: str) -> str:
        if not _EMAIL_RE.match(v):
            raise ValueError("username must be a valid email address.")
        return v.lower()


class TokenResponse(BaseModel):
    access_token: str = Field(..., description="Bearer token to use in Authorization header")
    token_type: str = Field(default="Bearer")
    expires_in: int = Field(..., gt=0, description="Token lifetime in seconds")


# ── Chat ──────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    message: str = Field(
        ...,
        min_length=1,
        max_length=4_000,
        description="User's chat message",
    )
    session_id: Optional[str] = Field(
        default="default",
        description="Session ID for conversation memory (UUID or alphanumeric string)",
    )

    @field_validator("message")
    @classmethod
    def message_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("message must not be blank.")
        return v

    @field_validator("session_id")
    @classmethod
    def validate_session_id(cls, v: Optional[str]) -> Optional[str]:
        return _validate_session_id(v)


class ChatResponse(BaseModel):
    response: str = Field(..., description="Agent's response")
    session_id: str = Field(..., description="Session ID used for this response")


# ── Jobs ──────────────────────────────────────────────────────────────────────

class JobSearchRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    query: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Job title or role to search for",
    )
    location: Optional[str] = Field(
        default="",
        max_length=200,
        description="City or location for job search",
    )
    session_id: Optional[str] = Field(default="default")

    @field_validator("query")
    @classmethod
    def query_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("query must not be blank.")
        return v

    @field_validator("session_id")
    @classmethod
    def validate_session_id(cls, v: Optional[str]) -> Optional[str]:
        return _validate_session_id(v)


class JobListing(BaseModel):
    title: str
    company: str
    location: str
    description: str
    apply_link: Optional[str] = None


class JobSearchResponse(BaseModel):
    results: str
    session_id: str


# ── Resume ────────────────────────────────────────────────────────────────────

class ResumeAnalysisRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    resume_text: str = Field(
        ...,
        min_length=50,
        max_length=50_000,
        description="Full text of the user's resume (min 50 characters)",
    )
    job_description: Optional[str] = Field(
        default="",
        max_length=10_000,
        description="Job description to compare against (optional)",
    )
    session_id: Optional[str] = Field(default="default")

    @field_validator("resume_text")
    @classmethod
    def resume_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("resume_text must not be blank.")
        return v

    @field_validator("session_id")
    @classmethod
    def validate_session_id(cls, v: Optional[str]) -> Optional[str]:
        return _validate_session_id(v)


class ResumeAnalysisResponse(BaseModel):
    analysis: str
    session_id: str


# ── Cover Letter ──────────────────────────────────────────────────────────────

class CoverLetterRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    resume_text: str = Field(
        ...,
        min_length=50,
        max_length=50_000,
        description="User's resume content (min 50 characters)",
    )
    job_title: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Job title being applied for",
    )
    company_name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Company name",
    )
    job_description: str = Field(
        ...,
        min_length=10,
        max_length=10_000,
        description="Full job description (min 10 characters)",
    )
    user_name: Optional[str] = Field(
        default="Applicant",
        min_length=1,
        max_length=200,
        description="Applicant's name",
    )
    session_id: Optional[str] = Field(default="default")

    @field_validator("resume_text", "job_description")
    @classmethod
    def text_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Field must not be blank.")
        return v

    @field_validator("job_title", "company_name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Field must not be blank.")
        return v

    @field_validator("session_id")
    @classmethod
    def validate_session_id(cls, v: Optional[str]) -> Optional[str]:
        return _validate_session_id(v)

    @model_validator(mode="after")
    def user_name_defaults_to_applicant(self) -> "CoverLetterRequest":
        if not self.user_name or not self.user_name.strip():
            self.user_name = "Applicant"
        return self


class CoverLetterResponse(BaseModel):
    cover_letter: str
    session_id: str


# ── System ────────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str = Field(..., description="API health status (e.g. 'healthy')")
    version: str = Field(..., description="API version string")
    message: str = Field(..., description="Human-readable status message")


class SessionClearResponse(BaseModel):
    message: str
    session_id: str


class SessionCreateResponse(BaseModel):
    session_id: str = Field(..., description="Newly created session ID")
    message: str = Field(default="Session created successfully.")


class SessionsListResponse(BaseModel):
    sessions: List[str] = Field(..., description="All active session IDs")
