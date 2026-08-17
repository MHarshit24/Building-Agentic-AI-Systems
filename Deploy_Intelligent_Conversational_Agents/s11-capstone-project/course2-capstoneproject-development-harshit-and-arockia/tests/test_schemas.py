"""
Unit tests for models/schemas.py — Pydantic request/response models.
Unit tests for models/responses.py — ApiResponse envelope.
"""
import pytest
from pydantic import ValidationError

from models.schemas import (
    ChatRequest,
    ChatResponse,
    JobSearchRequest,
    JobListing,
    JobSearchResponse,
    ResumeAnalysisRequest,
    ResumeAnalysisResponse,
    CoverLetterRequest,
    CoverLetterResponse,
    HealthResponse,
    SessionClearResponse,
    SessionCreateResponse,
    TokenRequest,
    TokenResponse,
)


# ── ChatRequest ───────────────────────────────────────────────────────────────

class TestChatRequest:
    def test_required_message(self):
        req = ChatRequest(message="Hello")
        assert req.message == "Hello"

    def test_default_session_id(self):
        req = ChatRequest(message="Hi")
        assert req.session_id == "default"

    def test_custom_session_id(self):
        req = ChatRequest(message="Hi", session_id="abc-123")
        assert req.session_id == "abc-123"

    def test_missing_message_raises(self):
        with pytest.raises(ValidationError):
            ChatRequest()


# ── ChatResponse ──────────────────────────────────────────────────────────────

class TestChatResponse:
    def test_valid_response(self):
        resp = ChatResponse(response="Hello back", session_id="s1")
        assert resp.response == "Hello back"
        assert resp.session_id == "s1"

    def test_missing_fields_raise(self):
        with pytest.raises(ValidationError):
            ChatResponse(response="Hello")  # session_id missing


# ── JobSearchRequest ──────────────────────────────────────────────────────────

class TestJobSearchRequest:
    def test_required_query(self):
        req = JobSearchRequest(query="Python Developer")
        assert req.query == "Python Developer"

    def test_defaults(self):
        req = JobSearchRequest(query="Engineer")
        assert req.location == ""
        assert req.session_id == "default"

    def test_custom_location(self):
        req = JobSearchRequest(query="ML Engineer", location="New York")
        assert req.location == "New York"


# ── JobListing ────────────────────────────────────────────────────────────────

class TestJobListing:
    def test_required_fields(self):
        listing = JobListing(
            title="SWE", company="Acme", location="Remote", description="Build stuff"
        )
        assert listing.title == "SWE"
        assert listing.apply_link is None

    def test_optional_apply_link(self):
        listing = JobListing(
            title="SWE", company="Acme", location="Remote",
            description="Build stuff", apply_link="https://apply.example.com"
        )
        assert listing.apply_link == "https://apply.example.com"


# ── ResumeAnalysisRequest / Response ─────────────────────────────────────────

_LONG_RESUME = ("Python developer with 5 years of experience in web and data engineering. " * 2).strip()

class TestResumeAnalysisRequest:
    def test_required_resume_text(self):
        req = ResumeAnalysisRequest(resume_text=_LONG_RESUME)
        assert req.resume_text == _LONG_RESUME

    def test_defaults(self):
        req = ResumeAnalysisRequest(resume_text=_LONG_RESUME)
        assert req.job_description == ""
        assert req.session_id == "default"

    def test_with_job_description(self):
        req = ResumeAnalysisRequest(
            resume_text=_LONG_RESUME, job_description="We need a Python dev"
        )
        assert req.job_description == "We need a Python dev"


class TestResumeAnalysisResponse:
    def test_valid(self):
        resp = ResumeAnalysisResponse(analysis="Strong profile", session_id="s2")
        assert resp.analysis == "Strong profile"


# ── CoverLetterRequest / Response ─────────────────────────────────────────────

_LONG_JD = "We are looking for a skilled data scientist to join our growing team. "

class TestCoverLetterRequest:
    def test_required_fields(self):
        req = CoverLetterRequest(
            resume_text=_LONG_RESUME,
            job_title="Data Scientist",
            company_name="BigCorp",
            job_description=_LONG_JD,
        )
        assert req.user_name == "Applicant"
        assert req.session_id == "default"

    def test_custom_user_name(self):
        req = CoverLetterRequest(
            resume_text=_LONG_RESUME,
            job_title="Data Scientist",
            company_name="BigCorp",
            job_description=_LONG_JD,
            user_name="Alice",
        )
        assert req.user_name == "Alice"

    def test_missing_required_raises(self):
        with pytest.raises(ValidationError):
            CoverLetterRequest(resume_text=_LONG_RESUME)  # job_title etc. missing


class TestCoverLetterResponse:
    def test_valid(self):
        resp = CoverLetterResponse(cover_letter="Dear Hiring Manager...", session_id="s3")
        assert resp.cover_letter.startswith("Dear")


# ── HealthResponse ────────────────────────────────────────────────────────────

class TestHealthResponse:
    def test_valid(self):
        resp = HealthResponse(status="healthy", version="1.0.0", message="Running")
        assert resp.status == "healthy"
        assert resp.version == "1.0.0"


# ── SessionClearResponse ──────────────────────────────────────────────────────

class TestSessionClearResponse:
    def test_valid(self):
        resp = SessionClearResponse(message="Cleared", session_id="sess-abc")
        assert resp.session_id == "sess-abc"


# ── SessionCreateResponse ─────────────────────────────────────────────────────

class TestSessionCreateResponse:
    def test_valid_with_session_id(self):
        resp = SessionCreateResponse(session_id="abc-123")
        assert resp.session_id == "abc-123"

    def test_default_message(self):
        resp = SessionCreateResponse(session_id="abc-123")
        assert "session" in resp.message.lower()

    def test_custom_message(self):
        resp = SessionCreateResponse(session_id="abc-123", message="All good.")
        assert resp.message == "All good."

    def test_missing_session_id_raises(self):
        with pytest.raises(ValidationError):
            SessionCreateResponse()


# ── TokenRequest / TokenResponse ─────────────────────────────────────────────

class TestTokenRequest:
    def test_valid(self):
        req = TokenRequest(username="user@test.com", password="secret")
        assert req.username == "user@test.com"
        assert req.password == "secret"

    def test_missing_username_raises(self):
        with pytest.raises(ValidationError):
            TokenRequest(password="secret")

    def test_missing_password_raises(self):
        with pytest.raises(ValidationError):
            TokenRequest(username="user@test.com")

    def test_invalid_email_raises(self):
        with pytest.raises(ValidationError):
            TokenRequest(username="not-an-email", password="secret")


class TestTokenResponse:
    def test_valid(self):
        resp = TokenResponse(access_token="eyJ.abc", token_type="Bearer", expires_in=86400)
        assert resp.access_token == "eyJ.abc"
        assert resp.token_type == "Bearer"
        assert resp.expires_in == 86400

    def test_default_token_type(self):
        resp = TokenResponse(access_token="tok", expires_in=3600)
        assert resp.token_type == "Bearer"

    def test_missing_access_token_raises(self):
        with pytest.raises(ValidationError):
            TokenResponse(expires_in=86400)

    def test_missing_expires_in_raises(self):
        with pytest.raises(ValidationError):
            TokenResponse(access_token="tok")


# ── session_id validator edge-cases ──────────────────────────────────────────

class TestSessionIdValidator:
    def test_null_session_id_is_allowed(self):
        req = ChatRequest(message="Hi", session_id=None)
        assert req.session_id is None

    def test_invalid_session_id_raises(self):
        with pytest.raises(ValidationError):
            ChatRequest(message="Hi", session_id="abc!@#invalid")

    def test_explicit_session_id_in_job_search_request(self):
        req = JobSearchRequest(query="Dev", session_id="my-session-id")
        assert req.session_id == "my-session-id"

    def test_explicit_session_id_in_resume_analysis_request(self):
        req = ResumeAnalysisRequest(resume_text=_LONG_RESUME, session_id="sess-xyz")
        assert req.session_id == "sess-xyz"

    def test_explicit_session_id_in_cover_letter_request(self):
        req = CoverLetterRequest(
            resume_text=_LONG_RESUME,
            job_title="Dev",
            company_name="Acme",
            job_description=_LONG_JD,
            session_id="sess-cl",
        )
        assert req.session_id == "sess-cl"

    def test_user_name_none_defaults_to_applicant(self):
        req = CoverLetterRequest(
            resume_text=_LONG_RESUME,
            job_title="Dev",
            company_name="Acme",
            job_description=_LONG_JD,
            user_name=None,
        )
        assert req.user_name == "Applicant"


# ── ApiResponse envelope (models/responses.py) ───────────────────────────────

class TestApiResponse:
    def test_ok_factory_sets_success_true(self):
        from models.responses import ApiResponse
        resp = ApiResponse.ok(data={"key": "value"}, request_id="req-001")
        assert resp.success is True
        assert resp.data == {"key": "value"}
        assert resp.error is None

    def test_ok_factory_sets_meta_request_id(self):
        from models.responses import ApiResponse
        resp = ApiResponse.ok(data="payload", request_id="req-abc")
        assert resp.meta.request_id == "req-abc"
        assert resp.meta.api_version == "1.0.0"

    def test_fail_factory_sets_success_false(self):
        from models.responses import ApiResponse
        resp = ApiResponse.fail(
            code="NOT_FOUND",
            message="Resource not found.",
            request_id="req-002",
        )
        assert resp.success is False
        assert resp.data is None
        assert resp.error.code == "NOT_FOUND"
        assert resp.error.message == "Resource not found."

    def test_fail_factory_with_details(self):
        from models.responses import ApiResponse, FieldError
        details = [FieldError(field="body.message", message="field required")]
        resp = ApiResponse.fail(
            code="VALIDATION_ERROR",
            message="Validation failed.",
            request_id="req-003",
            details=details,
        )
        assert resp.error.details[0].field == "body.message"

    def test_field_error_model(self):
        from models.responses import FieldError
        fe = FieldError(field="username", message="Invalid email")
        assert fe.field == "username"
        assert fe.message == "Invalid email"

    def test_error_detail_without_field_errors(self):
        from models.responses import ErrorDetail
        ed = ErrorDetail(code="INTERNAL_ERROR", message="Something went wrong")
        assert ed.code == "INTERNAL_ERROR"
        assert ed.details is None

    def test_request_meta_default_version(self):
        from models.responses import RequestMeta
        meta = RequestMeta(request_id="req-xyz")
        assert meta.api_version == "1.0.0"
