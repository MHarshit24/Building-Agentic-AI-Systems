"""
Uniform API response envelope.

Every endpoint returns:

    Success → { "success": true,  "data": <payload>, "error": null,   "meta": {...} }
    Failure → { "success": false, "data": null,       "error": {...},  "meta": {...} }

Usage
-----
    # In a route handler
    return ApiResponse.ok(data=MySchema(...), request_id=_req_id(request))

    # In an exception handler
    return JSONResponse(
        status_code=422,
        content=ApiResponse.fail(
            code="VALIDATION_ERROR",
            message="Request validation failed.",
            request_id=_req_id(request),
            details=[FieldError(field="body.message", message="field required")],
        ).model_dump(),
    )
"""
from __future__ import annotations

from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


# ── Building blocks ───────────────────────────────────────────────────────────

class FieldError(BaseModel):
    """A single field-level validation failure."""

    field: str = Field(
        ...,
        description="Dot / arrow-separated path to the failing field (e.g. 'body → message')",
    )
    message: str = Field(..., description="Human-readable description of the failure")


class ErrorDetail(BaseModel):
    """Structured error payload carried inside a failed ApiResponse."""

    code: str = Field(
        ...,
        description="Machine-readable error code (e.g. VALIDATION_ERROR, UNAUTHORIZED)",
    )
    message: str = Field(..., description="Human-readable error summary")
    details: Optional[List[FieldError]] = Field(
        default=None,
        description="Per-field errors — populated on 422 validation failures only",
    )


class RequestMeta(BaseModel):
    """Metadata attached to every response for tracing and versioning."""

    request_id: str = Field(
        ...,
        description="UUID that uniquely identifies this request; echoed from X-Request-ID header",
    )
    api_version: str = Field(default="1.0.0", description="API version string")


# ── Envelope ──────────────────────────────────────────────────────────────────

class ApiResponse(BaseModel, Generic[T]):
    """
    Uniform response envelope for every endpoint.

    All successful responses carry the domain payload in ``data``.
    All error responses carry structured diagnostics in ``error``.
    Both always include ``meta`` for request tracing.
    """

    success: bool = Field(..., description="True when the request completed successfully")
    data: Optional[T] = Field(
        default=None, description="Domain payload (null on error responses)"
    )
    error: Optional[ErrorDetail] = Field(
        default=None, description="Structured error info (null on success responses)"
    )
    meta: RequestMeta = Field(..., description="Per-request metadata")

    # ── Factories ─────────────────────────────────────────────────────────────

    @classmethod
    def ok(cls, data: T, request_id: str) -> "ApiResponse[T]":
        """Wrap a successful payload in the envelope."""
        return cls(
            success=True,
            data=data,
            error=None,
            meta=RequestMeta(request_id=request_id),
        )

    @classmethod
    def fail(
        cls,
        code: str,
        message: str,
        request_id: str,
        details: Optional[List[FieldError]] = None,
    ) -> "ApiResponse[None]":
        """Build an error response envelope."""
        return cls(
            success=False,
            data=None,
            error=ErrorDetail(code=code, message=message, details=details),
            meta=RequestMeta(request_id=request_id),
        )
