"""
Integration tests for fastapi_app.py — all HTTP endpoints via TestClient.

Uses FastAPI's TestClient (backed by httpx) to exercise every route,
the global AppError exception handler, and the SSE streaming endpoint.

External dependencies (agent, auth, tools) are patched at the module-name
level so tests never make real LLM or API calls.
"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient


# ── Shared fixtures ───────────────────────────────────────────────────────────

FAKE_USER = {"sub": "auth0|test-user", "email": "test@example.com"}
FAKE_TOKEN = {"access_token": "tok.jwt.sig", "token_type": "Bearer", "expires_in": 86400}


@pytest.fixture()
def client(mocker):
    """
    TestClient with every external dependency mocked.

    The ``get_current_user`` FastAPI dependency is overridden via
    ``app.dependency_overrides`` so authenticated endpoints return
    FAKE_USER without a real JWT.
    """
    # ── sync mocks ────────────────────────────────────────────────────────────
    mocker.patch("fastapi_app.run_agent",                 return_value="agent reply")
    mocker.patch("fastapi_app.route_query",               return_value=("general", "router reply"))
    mocker.patch("fastapi_app.fetch_job_listings",        return_value="job results markdown")
    mocker.patch("fastapi_app.analyze_resume_core",       return_value="resume analysis text")
    mocker.patch("fastapi_app.generate_cover_letter_core",return_value="Dear Hiring Manager...")
    mocker.patch("fastapi_app.fetch_token",               return_value=FAKE_TOKEN)
    mocker.patch("fastapi_app.clear_session")
    mocker.patch("fastapi_app.list_sessions",             return_value=["s1", "s2"])
    mocker.patch("fastapi_app.get_session_history",       return_value=MagicMock())
    mocker.patch("fastapi_app.get_langfuse_handler",      return_value=None)
    mocker.patch("fastapi_app.flush_langfuse")

    # ── async mocks ───────────────────────────────────────────────────────────
    mocker.patch(
        "fastapi_app.run_agent_async",
        new=AsyncMock(return_value="async agent reply"),
    )

    # stream_agent must be an async generator function
    async def _mock_stream(user_message=None, session_id="default", user_id=None):
        yield "Hello"
        yield " world"

    mocker.patch("fastapi_app.stream_agent", new=_mock_stream)

    # ── app + dependency override ─────────────────────────────────────────────
    from fastapi_app import app
    from auth.auth0 import get_current_user

    app.dependency_overrides[get_current_user] = lambda: FAKE_USER

    # Context manager triggers startup / shutdown lifecycle events (covers
    # the on_shutdown handler that calls flush_langfuse).
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c

    app.dependency_overrides.clear()


# ── GET /api/health ───────────────────────────────────────────────────────────

class TestHealthEndpoint:
    def test_returns_200(self, client):
        assert client.get("/api/health").status_code == 200

    def test_status_is_healthy(self, client):
        data = client.get("/api/health").json()
        assert data["data"]["status"] == "healthy"

    def test_version_is_1_0_0(self, client):
        data = client.get("/api/health").json()
        assert data["data"]["version"] == "1.0.0"

    def test_success_flag_is_true(self, client):
        assert client.get("/api/health").json()["success"] is True

    def test_x_request_id_header_used_when_present(self, client):
        resp = client.get("/api/health", headers={"x-request-id": "req-abc"})
        assert resp.json()["meta"]["request_id"] == "req-abc"


# ── POST /api/auth/token ──────────────────────────────────────────────────────

class TestAuthTokenEndpoint:
    def _valid_body(self):
        return {"username": "user@example.com", "password": "secret"}

    def test_returns_200(self, client):
        assert client.post("/api/auth/token", json=self._valid_body()).status_code == 200

    def test_returns_access_token(self, client):
        data = client.post("/api/auth/token", json=self._valid_body()).json()
        assert data["data"]["access_token"] == "tok.jwt.sig"

    def test_returns_bearer_token_type(self, client):
        data = client.post("/api/auth/token", json=self._valid_body()).json()
        assert data["data"]["token_type"] == "Bearer"

    def test_returns_expires_in(self, client):
        data = client.post("/api/auth/token", json=self._valid_body()).json()
        assert data["data"]["expires_in"] == 86400

    def test_422_on_invalid_email(self, client):
        resp = client.post("/api/auth/token", json={"username": "notanemail", "password": "p"})
        assert resp.status_code == 422

    def test_app_error_returns_error_json(self, client, mocker):
        from exceptions import Auth0CredentialsError
        mocker.patch("fastapi_app.fetch_token", side_effect=Auth0CredentialsError("bad creds"))
        resp = client.post("/api/auth/token", json=self._valid_body())
        assert resp.status_code == 401
        body = resp.json()
        assert body["success"] is False
        assert body["error"]["code"] == "AUTH0_INVALID_CREDENTIALS"


# ── POST /api/chat/public ─────────────────────────────────────────────────────

class TestChatPublicEndpoint:
    def test_returns_200(self, client):
        assert client.post("/api/chat/public", json={"message": "Hi"}).status_code == 200

    def test_returns_agent_reply(self, client):
        data = client.post("/api/chat/public", json={"message": "Hi"}).json()
        assert data["data"]["response"] == "agent reply"

    def test_preserves_provided_session_id(self, client):
        data = client.post(
            "/api/chat/public", json={"message": "Hi", "session_id": "my-sess"}
        ).json()
        assert data["data"]["session_id"] == "my-sess"

    def test_auto_generates_session_id_when_absent(self, client):
        data = client.post("/api/chat/public", json={"message": "Hi"}).json()
        assert data["data"]["session_id"]  # non-empty

    def test_422_on_empty_message(self, client):
        assert client.post("/api/chat/public", json={"message": ""}).status_code == 422

    def test_app_error_handler_formats_json_response(self, client, mocker):
        from exceptions import GeminiRateLimitError
        mocker.patch("fastapi_app.run_agent", side_effect=GeminiRateLimitError("quota"))
        resp = client.post("/api/chat/public", json={"message": "Hi"})
        assert resp.status_code == 429
        assert resp.json()["success"] is False
        assert resp.json()["error"]["code"] == "LLM_RATE_LIMITED"


# ── POST /api/session ─────────────────────────────────────────────────────────

class TestCreateSessionEndpoint:
    def test_returns_200(self, client):
        assert client.post("/api/session").status_code == 200

    def test_returns_nonempty_session_id(self, client):
        data = client.post("/api/session").json()
        assert data["data"]["session_id"]

    def test_session_id_is_uuid_format(self, client):
        import uuid
        sid = client.post("/api/session").json()["data"]["session_id"]
        uuid.UUID(sid)  # raises ValueError if not a valid UUID

    def test_calls_get_session_history(self, client, mocker):
        mock_gsh = mocker.patch("fastapi_app.get_session_history", return_value=MagicMock())
        client.post("/api/session")
        mock_gsh.assert_called_once()


# ── POST /api/chat (🔒) ───────────────────────────────────────────────────────

class TestChatEndpoint:
    def test_returns_200_with_auth(self, client):
        assert client.post("/api/chat", json={"message": "Hi"}).status_code == 200

    def test_returns_agent_reply(self, client):
        data = client.post("/api/chat", json={"message": "Hi"}).json()
        assert data["data"]["response"] == "agent reply"

    def test_passes_user_id_to_run_agent(self, client, mocker):
        mock_run = mocker.patch("fastapi_app.run_agent", return_value="ok")
        client.post("/api/chat", json={"message": "Hi", "session_id": "s1"})
        _, kwargs = mock_run.call_args
        assert kwargs.get("user_id") == FAKE_USER["sub"]

    def test_app_error_returns_error_response(self, client, mocker):
        from exceptions import GeminiNetworkError
        mocker.patch("fastapi_app.run_agent", side_effect=GeminiNetworkError("timeout"))
        resp = client.post("/api/chat", json={"message": "Hi"})
        assert resp.status_code == 503
        assert resp.json()["success"] is False


# ── POST /api/chat/async (🔒) ─────────────────────────────────────────────────

class TestChatAsyncEndpoint:
    def test_returns_200_with_auth(self, client):
        assert client.post("/api/chat/async", json={"message": "Hi"}).status_code == 200

    def test_returns_async_agent_reply(self, client):
        data = client.post("/api/chat/async", json={"message": "Hi"}).json()
        assert data["data"]["response"] == "async agent reply"

    def test_passes_user_id_to_run_agent_async(self, client, mocker):
        mock_run = AsyncMock(return_value="ok")
        mocker.patch("fastapi_app.run_agent_async", new=mock_run)
        client.post("/api/chat/async", json={"message": "Hi", "session_id": "s1"})
        _, kwargs = mock_run.call_args
        assert kwargs.get("user_id") == FAKE_USER["sub"]


# ── POST /api/chat/stream ─────────────────────────────────────────────────────

class TestChatStreamEndpoint:
    def test_returns_200(self, client):
        assert client.post("/api/chat/stream", json={"message": "Hi"}).status_code == 200

    def test_content_type_is_event_stream(self, client):
        resp = client.post("/api/chat/stream", json={"message": "Hi"})
        assert "text/event-stream" in resp.headers["content-type"]

    def test_body_contains_token_events(self, client):
        body = client.post("/api/chat/stream", json={"message": "Hi"}).text
        assert "Hello" in body
        assert "world" in body

    def test_body_contains_done_event(self, client):
        body = client.post("/api/chat/stream", json={"message": "Hi"}).text
        assert '"done"' in body and "true" in body.lower()

    def test_sse_data_prefix_present(self, client):
        body = client.post("/api/chat/stream", json={"message": "Hi"}).text
        assert body.startswith("data:")

    def test_stream_error_yields_error_event(self, client, mocker):
        async def _boom(**kwargs):
            raise RuntimeError("stream broken")
            yield  # make it a generator

        mocker.patch("fastapi_app.stream_agent", new=_boom)
        resp = client.post("/api/chat/stream", json={"message": "Hi"})
        assert resp.status_code == 200  # SSE always 200; error is in body
        assert "STREAM_ERROR" in resp.text


# ── POST /api/chat/route ──────────────────────────────────────────────────────

class TestChatRouteEndpoint:
    def test_returns_200(self, client):
        assert client.post("/api/chat/route", json={"message": "Hi"}).status_code == 200

    def test_response_prefixed_with_intent(self, client):
        data = client.post("/api/chat/route", json={"message": "Hi"}).json()
        response = data["data"]["response"]
        # format: "[<intent>] <response>"
        assert response.startswith("[general]")
        assert "router reply" in response

    def test_passes_message_to_route_query(self, client, mocker):
        mock_rq = mocker.patch("fastapi_app.route_query", return_value=("job_search", "jobs"))
        client.post("/api/chat/route", json={"message": "Find jobs"})
        mock_rq.assert_called_once_with("Find jobs")


# ── POST /api/jobs/search (🔒) ────────────────────────────────────────────────

class TestJobSearchEndpoint:
    def test_returns_200_with_auth(self, client):
        resp = client.post("/api/jobs/search", json={"query": "Python dev"})
        assert resp.status_code == 200

    def test_returns_job_results(self, client):
        data = client.post("/api/jobs/search", json={"query": "Python dev"}).json()
        assert data["data"]["results"] == "job results markdown"

    def test_passes_location_to_tool(self, client, mocker):
        mock_fetch = mocker.patch("fastapi_app.fetch_job_listings", return_value="jobs")
        client.post("/api/jobs/search", json={"query": "Dev", "location": "Remote"})
        mock_fetch.assert_called_once_with("Dev", "Remote")

    def test_422_on_empty_query(self, client):
        assert client.post("/api/jobs/search", json={"query": ""}).status_code == 422


# ── POST /api/resume/analyze (🔒) ─────────────────────────────────────────────

class TestResumeAnalyzeEndpoint:
    def _body(self, **kw):
        return {"resume_text": "x" * 100, **kw}

    def test_returns_200_with_auth(self, client):
        assert client.post("/api/resume/analyze", json=self._body()).status_code == 200

    def test_returns_analysis(self, client):
        data = client.post("/api/resume/analyze", json=self._body()).json()
        assert data["data"]["analysis"] == "resume analysis text"

    def test_passes_job_description_to_core(self, client, mocker):
        mock_core = mocker.patch("fastapi_app.analyze_resume_core", return_value="ok")
        client.post(
            "/api/resume/analyze",
            json=self._body(job_description="Senior Python role"),
        )
        args, _ = mock_core.call_args
        assert args[1] == "Senior Python role"

    def test_422_on_short_resume_text(self, client):
        assert client.post("/api/resume/analyze", json={"resume_text": "short"}).status_code == 422

    def test_langfuse_handler_flushed_when_present(self, mocker):
        """Covers lines 299-302: langfuse_handler.flush() in the finally block."""
        mock_handler = MagicMock()
        mocker.patch("fastapi_app.get_langfuse_handler", return_value=mock_handler)
        mocker.patch("fastapi_app.analyze_resume_core", return_value="analysis")

        from fastapi_app import app
        from auth.auth0 import get_current_user
        app.dependency_overrides[get_current_user] = lambda: FAKE_USER
        with TestClient(app) as c:
            c.post("/api/resume/analyze", json={"resume_text": "x" * 100})
        app.dependency_overrides.clear()

        mock_handler.flush.assert_called_once()

    def test_langfuse_flush_exception_swallowed(self, mocker):
        """flush() errors in the finally block must not propagate to the caller."""
        mock_handler = MagicMock()
        mock_handler.flush.side_effect = RuntimeError("flush failed")
        mocker.patch("fastapi_app.get_langfuse_handler", return_value=mock_handler)
        mocker.patch("fastapi_app.analyze_resume_core", return_value="analysis")

        from fastapi_app import app
        from auth.auth0 import get_current_user
        app.dependency_overrides[get_current_user] = lambda: FAKE_USER
        with TestClient(app) as c:
            resp = c.post("/api/resume/analyze", json={"resume_text": "x" * 100})
        app.dependency_overrides.clear()

        assert resp.status_code == 200


# ── POST /api/cover-letter/gen (🔒) ──────────────────────────────────────────

class TestCoverLetterEndpoint:
    def _body(self, **kw):
        return {
            "resume_text":     "x" * 100,
            "job_title":       "Engineer",
            "company_name":    "ACME",
            "job_description": "Build systems at scale.",
            **kw,
        }

    def test_returns_200_with_auth(self, client):
        assert client.post("/api/cover-letter/gen", json=self._body()).status_code == 200

    def test_returns_cover_letter(self, client):
        data = client.post("/api/cover-letter/gen", json=self._body()).json()
        assert data["data"]["cover_letter"] == "Dear Hiring Manager..."

    def test_defaults_user_name_to_applicant(self, client, mocker):
        mock_core = mocker.patch("fastapi_app.generate_cover_letter_core", return_value="letter")
        client.post("/api/cover-letter/gen", json=self._body())
        _, kwargs = mock_core.call_args
        assert kwargs.get("user_name") == "Applicant"

    def test_passes_provided_user_name(self, client, mocker):
        mock_core = mocker.patch("fastapi_app.generate_cover_letter_core", return_value="letter")
        client.post("/api/cover-letter/gen", json=self._body(user_name="Jane Doe"))
        _, kwargs = mock_core.call_args
        assert kwargs.get("user_name") == "Jane Doe"

    def test_422_on_missing_job_title(self, client):
        body = self._body()
        body.pop("job_title")
        assert client.post("/api/cover-letter/gen", json=body).status_code == 422

    def test_langfuse_handler_flushed_when_present(self, mocker):
        """Covers lines 329-332: langfuse_handler.flush() in the finally block."""
        mock_handler = MagicMock()
        mocker.patch("fastapi_app.get_langfuse_handler", return_value=mock_handler)
        mocker.patch("fastapi_app.generate_cover_letter_core", return_value="letter")

        from fastapi_app import app
        from auth.auth0 import get_current_user
        app.dependency_overrides[get_current_user] = lambda: FAKE_USER
        with TestClient(app) as c:
            c.post("/api/cover-letter/gen", json=self._body())
        app.dependency_overrides.clear()

        mock_handler.flush.assert_called_once()

    def test_langfuse_flush_exception_swallowed(self, mocker):
        """flush() errors in the finally block must not propagate."""
        mock_handler = MagicMock()
        mock_handler.flush.side_effect = RuntimeError("flush failed")
        mocker.patch("fastapi_app.get_langfuse_handler", return_value=mock_handler)
        mocker.patch("fastapi_app.generate_cover_letter_core", return_value="letter")

        from fastapi_app import app
        from auth.auth0 import get_current_user
        app.dependency_overrides[get_current_user] = lambda: FAKE_USER
        with TestClient(app) as c:
            resp = c.post("/api/cover-letter/gen", json=self._body())
        app.dependency_overrides.clear()

        assert resp.status_code == 200


# ── DELETE /api/chat/{session_id} (🔒) ───────────────────────────────────────

class TestClearSessionEndpoint:
    def test_returns_200_with_auth(self, client):
        assert client.delete("/api/chat/my-session").status_code == 200

    def test_returns_cleared_message(self, client):
        data = client.delete("/api/chat/my-session").json()
        assert "cleared" in data["data"]["message"].lower()

    def test_returns_correct_session_id(self, client):
        data = client.delete("/api/chat/target-sess").json()
        assert data["data"]["session_id"] == "target-sess"

    def test_calls_clear_session_with_id(self, client, mocker):
        mock_clear = mocker.patch("fastapi_app.clear_session")
        client.delete("/api/chat/sess-xyz")
        mock_clear.assert_called_once_with("sess-xyz")


# ── GET /api/sessions (🔒) ───────────────────────────────────────────────────

class TestListSessionsEndpoint:
    def test_returns_200_with_auth(self, client):
        assert client.get("/api/sessions").status_code == 200

    def test_returns_session_list(self, client):
        data = client.get("/api/sessions").json()
        assert data["data"]["sessions"] == ["s1", "s2"]


# ── Global AppError handler ───────────────────────────────────────────────────

class TestAppErrorHandler:
    """
    Exercises the @app.exception_handler(AppError) registered in fastapi_app.py.
    Each test triggers a different AppError subclass and verifies the HTTP status
    and JSON error code.
    """

    def test_gemini_config_error_returns_500(self, client, mocker):
        from exceptions import GeminiConfigError
        mocker.patch("fastapi_app.run_agent", side_effect=GeminiConfigError("no key"))
        resp = client.post("/api/chat/public", json={"message": "Hi"})
        assert resp.status_code == 500
        assert resp.json()["error"]["code"] == "LLM_CONFIGURATION_ERROR"

    def test_gemini_rate_limit_returns_429(self, client, mocker):
        from exceptions import GeminiRateLimitError
        mocker.patch("fastapi_app.run_agent", side_effect=GeminiRateLimitError("rate"))
        resp = client.post("/api/chat/public", json={"message": "Hi"})
        assert resp.status_code == 429

    def test_gemini_network_error_returns_503(self, client, mocker):
        from exceptions import GeminiNetworkError
        mocker.patch("fastapi_app.run_agent", side_effect=GeminiNetworkError("down"))
        resp = client.post("/api/chat/public", json={"message": "Hi"})
        assert resp.status_code == 503

    def test_serpapi_rate_limit_returns_429(self, client, mocker):
        from exceptions import SerpApiRateLimitError
        mocker.patch("fastapi_app.fetch_job_listings", side_effect=SerpApiRateLimitError("quota"))
        resp = client.post("/api/jobs/search", json={"query": "dev"})
        assert resp.status_code == 429

    def test_auth0_credentials_error_returns_401(self, client, mocker):
        from exceptions import Auth0CredentialsError
        mocker.patch("fastapi_app.fetch_token", side_effect=Auth0CredentialsError("bad"))
        resp = client.post(
            "/api/auth/token",
            json={"username": "u@test.com", "password": "wrong"},
        )
        assert resp.status_code == 401

    def test_error_response_has_success_false(self, client, mocker):
        from exceptions import GeminiRateLimitError
        mocker.patch("fastapi_app.run_agent", side_effect=GeminiRateLimitError("r"))
        body = client.post("/api/chat/public", json={"message": "Hi"}).json()
        assert body["success"] is False

    def test_error_response_contains_message(self, client, mocker):
        from exceptions import GeminiConfigError
        mocker.patch("fastapi_app.run_agent", side_effect=GeminiConfigError("api key missing"))
        body = client.post("/api/chat/public", json={"message": "Hi"}).json()
        assert "api key missing" in body["error"]["message"]
