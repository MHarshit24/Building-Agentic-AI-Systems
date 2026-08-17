"""
Unit tests for grpc_server.py — JobAgentServicer RPC methods.

Each test class covers one RPC or one internal helper.
The ``servicer`` fixture (conftest.py) provides a pre-wired
JobAgentServicer with all external dependencies mocked.
The ``make_context`` fixture provides a fresh MockContext per call.
"""
import uuid
import pytest
from unittest.mock import MagicMock, patch


# ── HealthCheck ───────────────────────────────────────────────────────────────

class TestHealthCheck:
    def test_returns_healthy_status(self, servicer, make_context):
        from proto import job_agent_pb2
        resp = servicer.HealthCheck(job_agent_pb2.HealthRequest(), make_context())
        assert resp.status == "healthy"

    def test_returns_correct_version(self, servicer, make_context):
        from proto import job_agent_pb2
        resp = servicer.HealthCheck(job_agent_pb2.HealthRequest(), make_context())
        assert resp.version == "1.0.0"

    def test_response_message_mentions_running(self, servicer, make_context):
        from proto import job_agent_pb2
        resp = servicer.HealthCheck(job_agent_pb2.HealthRequest(), make_context())
        assert "running" in resp.message.lower()


# ── GetToken ──────────────────────────────────────────────────────────────────

class TestGetToken:
    def test_returns_access_token(self, servicer, make_context):
        from proto import job_agent_pb2
        req  = job_agent_pb2.GetTokenRequest(username="user@test.com", password="pass")
        resp = servicer.GetToken(req, make_context())
        assert resp.access_token == "eyJ.token"
        assert resp.token_type   == "Bearer"
        assert resp.expires_in   == 86400

    def test_aborts_when_username_empty(self, servicer, make_context):
        import grpc
        from proto import job_agent_pb2
        ctx = make_context()
        with pytest.raises(Exception):
            servicer.GetToken(
                job_agent_pb2.GetTokenRequest(username="", password="pass"), ctx
            )
        assert ctx.aborted
        assert ctx.abort_code == grpc.StatusCode.INVALID_ARGUMENT

    def test_aborts_when_password_empty(self, servicer, make_context):
        import grpc
        from proto import job_agent_pb2
        ctx = make_context()
        with pytest.raises(Exception):
            servicer.GetToken(
                job_agent_pb2.GetTokenRequest(username="u@test.com", password=""), ctx
            )
        assert ctx.aborted
        assert ctx.abort_code == grpc.StatusCode.INVALID_ARGUMENT

    def test_aborts_on_credentials_error(self, servicer, make_context, mocker):
        import grpc
        from proto import job_agent_pb2
        from exceptions import Auth0CredentialsError
        mocker.patch("grpc_server.fetch_token", side_effect=Auth0CredentialsError("bad creds"))
        ctx = make_context()
        with pytest.raises(Exception):
            servicer.GetToken(
                job_agent_pb2.GetTokenRequest(username="u@test.com", password="wrong"), ctx
            )
        assert ctx.aborted
        assert ctx.abort_code == grpc.StatusCode.UNAUTHENTICATED

    def test_aborts_on_config_error(self, servicer, make_context, mocker):
        import grpc
        from proto import job_agent_pb2
        from exceptions import Auth0ConfigError
        mocker.patch("grpc_server.fetch_token", side_effect=Auth0ConfigError("no domain"))
        ctx = make_context()
        with pytest.raises(Exception):
            servicer.GetToken(
                job_agent_pb2.GetTokenRequest(username="u@test.com", password="p"), ctx
            )
        assert ctx.aborted
        assert ctx.abort_code == grpc.StatusCode.INTERNAL


# ── ChatPublic ────────────────────────────────────────────────────────────────

class TestChatPublic:
    def test_returns_agent_response(self, servicer, make_context):
        from proto import job_agent_pb2
        req  = job_agent_pb2.ChatRequest(message="Hello", session_id="sess-1")
        resp = servicer.ChatPublic(req, make_context())
        assert resp.response == "agent reply"

    def test_preserves_provided_session_id(self, servicer, make_context):
        from proto import job_agent_pb2
        req  = job_agent_pb2.ChatRequest(message="Hi", session_id="my-session")
        resp = servicer.ChatPublic(req, make_context())
        assert resp.session_id == "my-session"

    def test_auto_generates_session_id_when_empty(self, servicer, make_context):
        from proto import job_agent_pb2
        req  = job_agent_pb2.ChatRequest(message="Hi", session_id="")
        resp = servicer.ChatPublic(req, make_context())
        assert resp.session_id  # non-empty
        # Should be a valid UUID
        uuid.UUID(resp.session_id)

    def test_aborts_when_message_empty(self, servicer, make_context):
        import grpc
        from proto import job_agent_pb2
        ctx = make_context()
        with pytest.raises(Exception):
            servicer.ChatPublic(job_agent_pb2.ChatRequest(message=""), ctx)
        assert ctx.aborted
        assert ctx.abort_code == grpc.StatusCode.INVALID_ARGUMENT

    def test_no_auth_required(self, servicer, make_context):
        """ChatPublic must work without any authorization metadata."""
        from proto import job_agent_pb2
        ctx  = make_context()  # no metadata
        resp = servicer.ChatPublic(
            job_agent_pb2.ChatRequest(message="No auth needed"), ctx
        )
        assert resp.response == "agent reply"
        assert not ctx.aborted


# ── CreateSession ─────────────────────────────────────────────────────────────

class TestCreateSession:
    def test_returns_session_id(self, servicer, make_context):
        from proto import job_agent_pb2
        resp = servicer.CreateSession(job_agent_pb2.CreateSessionRequest(), make_context())
        assert resp.session_id
        uuid.UUID(resp.session_id)  # validates UUID format

    def test_response_message_mentions_session(self, servicer, make_context):
        from proto import job_agent_pb2
        resp = servicer.CreateSession(job_agent_pb2.CreateSessionRequest(), make_context())
        assert "session" in resp.message.lower()

    def test_each_call_returns_unique_id(self, servicer, make_context):
        from proto import job_agent_pb2
        id1 = servicer.CreateSession(
            job_agent_pb2.CreateSessionRequest(), make_context()
        ).session_id
        id2 = servicer.CreateSession(
            job_agent_pb2.CreateSessionRequest(), make_context()
        ).session_id
        assert id1 != id2

    def test_no_auth_required(self, servicer, make_context):
        from proto import job_agent_pb2
        ctx  = make_context()
        resp = servicer.CreateSession(job_agent_pb2.CreateSessionRequest(), ctx)
        assert not ctx.aborted
        assert resp.session_id


# ── Chat (protected) ──────────────────────────────────────────────────────────

class TestChat:
    def test_aborts_when_no_auth_metadata(self, servicer, make_context):
        import grpc
        from proto import job_agent_pb2
        ctx = make_context()  # no metadata
        with pytest.raises(Exception):
            servicer.Chat(job_agent_pb2.ChatRequest(message="Hi"), ctx)
        assert ctx.aborted
        assert ctx.abort_code == grpc.StatusCode.UNAUTHENTICATED

    def test_returns_response_with_valid_auth(self, servicer, make_context, auth_metadata):
        from proto import job_agent_pb2
        req  = job_agent_pb2.ChatRequest(message="Hello", session_id="s1")
        resp = servicer.Chat(req, make_context(metadata=auth_metadata))
        assert resp.response   == "agent reply"
        assert resp.session_id == "s1"

    def test_aborts_when_message_empty(self, servicer, make_context, auth_metadata):
        import grpc
        from proto import job_agent_pb2
        ctx = make_context(metadata=auth_metadata)
        with pytest.raises(Exception):
            servicer.Chat(job_agent_pb2.ChatRequest(message=""), ctx)
        assert ctx.aborted
        assert ctx.abort_code == grpc.StatusCode.INVALID_ARGUMENT

    def test_passes_user_id_to_run_agent(self, servicer, make_context, auth_metadata, mocker):
        """The authenticated user's sub claim must reach run_agent as user_id."""
        from proto import job_agent_pb2
        mock_run = mocker.patch("grpc_server.run_agent", return_value="ok")
        servicer.Chat(
            job_agent_pb2.ChatRequest(message="Hello", session_id="s99"),
            make_context(metadata=auth_metadata),
        )
        _, kwargs = mock_run.call_args
        assert kwargs.get("user_id") == "auth0|test-user"

    def test_auto_generates_session_id(self, servicer, make_context, auth_metadata):
        from proto import job_agent_pb2
        resp = servicer.Chat(
            job_agent_pb2.ChatRequest(message="Hi", session_id=""),
            make_context(metadata=auth_metadata),
        )
        assert resp.session_id
        uuid.UUID(resp.session_id)


# ── SearchJobs (protected) ────────────────────────────────────────────────────

class TestSearchJobs:
    def test_aborts_without_auth(self, servicer, make_context):
        import grpc
        from proto import job_agent_pb2
        ctx = make_context()
        with pytest.raises(Exception):
            servicer.SearchJobs(job_agent_pb2.JobSearchRequest(query="Developer"), ctx)
        assert ctx.aborted
        assert ctx.abort_code == grpc.StatusCode.UNAUTHENTICATED

    def test_returns_results_with_auth(self, servicer, make_context, auth_metadata):
        from proto import job_agent_pb2
        req  = job_agent_pb2.JobSearchRequest(
            query="Python Dev", location="Remote", session_id="s1"
        )
        resp = servicer.SearchJobs(req, make_context(metadata=auth_metadata))
        assert resp.results == "job results"

    def test_aborts_when_query_empty(self, servicer, make_context, auth_metadata):
        import grpc
        from proto import job_agent_pb2
        ctx = make_context(metadata=auth_metadata)
        with pytest.raises(Exception):
            servicer.SearchJobs(job_agent_pb2.JobSearchRequest(query=""), ctx)
        assert ctx.aborted
        assert ctx.abort_code == grpc.StatusCode.INVALID_ARGUMENT

    def test_passes_location_to_tool(self, servicer, make_context, auth_metadata, mocker):
        from proto import job_agent_pb2
        mock_fetch = mocker.patch("grpc_server.fetch_job_listings", return_value="results")
        servicer.SearchJobs(
            job_agent_pb2.JobSearchRequest(query="Engineer", location="New York"),
            make_context(metadata=auth_metadata),
        )
        mock_fetch.assert_called_once_with("Engineer", "New York")


# ── AnalyzeResume (protected) ─────────────────────────────────────────────────

class TestAnalyzeResume:
    def test_aborts_without_auth(self, servicer, make_context):
        import grpc
        from proto import job_agent_pb2
        ctx = make_context()
        with pytest.raises(Exception):
            servicer.AnalyzeResume(
                job_agent_pb2.ResumeAnalysisRequest(resume_text="my resume"), ctx
            )
        assert ctx.aborted
        assert ctx.abort_code == grpc.StatusCode.UNAUTHENTICATED

    def test_returns_analysis_with_auth(self, servicer, make_context, auth_metadata):
        from proto import job_agent_pb2
        req  = job_agent_pb2.ResumeAnalysisRequest(
            resume_text="5 years of Python experience", session_id="s1"
        )
        resp = servicer.AnalyzeResume(req, make_context(metadata=auth_metadata))
        assert resp.analysis == "analysis text"

    def test_aborts_when_resume_text_empty(self, servicer, make_context, auth_metadata):
        import grpc
        from proto import job_agent_pb2
        ctx = make_context(metadata=auth_metadata)
        with pytest.raises(Exception):
            servicer.AnalyzeResume(
                job_agent_pb2.ResumeAnalysisRequest(resume_text=""), ctx
            )
        assert ctx.aborted
        assert ctx.abort_code == grpc.StatusCode.INVALID_ARGUMENT

    def test_passes_job_description_to_tool(self, servicer, make_context, auth_metadata, mocker):
        from proto import job_agent_pb2
        mock_analyze = mocker.patch(
            "grpc_server.analyze_resume_core", return_value="analysis"
        )
        servicer.AnalyzeResume(
            job_agent_pb2.ResumeAnalysisRequest(
                resume_text="resume", job_description="JD here"
            ),
            make_context(metadata=auth_metadata),
        )
        mock_analyze.assert_called_once_with("resume", "JD here")


# ── AppError propagation in RPCs ─────────────────────────────────────────────

class TestRpcAppErrorPropagation:
    """
    Each RPC that calls agent/tool functions must abort with the correct gRPC
    status code when that function raises an AppError subclass.
    Covers the ``except AppError`` branches in grpc_server.py.
    """

    def test_chat_public_aborts_on_gemini_rate_limit(
        self, servicer, make_context, mocker
    ):
        import grpc
        from proto import job_agent_pb2
        from exceptions import GeminiRateLimitError
        mocker.patch("grpc_server.run_agent", side_effect=GeminiRateLimitError("rate"))
        ctx = make_context()
        with pytest.raises(Exception):
            servicer.ChatPublic(job_agent_pb2.ChatRequest(message="Hi"), ctx)
        assert ctx.aborted
        assert ctx.abort_code == grpc.StatusCode.RESOURCE_EXHAUSTED

    def test_chat_aborts_on_gemini_network_error(
        self, servicer, make_context, auth_metadata, mocker
    ):
        import grpc
        from proto import job_agent_pb2
        from exceptions import GeminiNetworkError
        mocker.patch("grpc_server.run_agent", side_effect=GeminiNetworkError("net"))
        ctx = make_context(metadata=auth_metadata)
        with pytest.raises(Exception):
            servicer.Chat(job_agent_pb2.ChatRequest(message="Hi"), ctx)
        assert ctx.aborted
        assert ctx.abort_code == grpc.StatusCode.UNAVAILABLE

    def test_search_jobs_aborts_on_serpapi_rate_limit(
        self, servicer, make_context, auth_metadata, mocker
    ):
        import grpc
        from proto import job_agent_pb2
        from exceptions import SerpApiRateLimitError
        mocker.patch(
            "grpc_server.fetch_job_listings",
            side_effect=SerpApiRateLimitError("quota"),
        )
        ctx = make_context(metadata=auth_metadata)
        with pytest.raises(Exception):
            servicer.SearchJobs(
                job_agent_pb2.JobSearchRequest(query="Dev"), ctx
            )
        assert ctx.aborted
        assert ctx.abort_code == grpc.StatusCode.RESOURCE_EXHAUSTED

    def test_analyze_resume_aborts_on_gemini_config_error(
        self, servicer, make_context, auth_metadata, mocker
    ):
        import grpc
        from proto import job_agent_pb2
        from exceptions import GeminiConfigError
        mocker.patch(
            "grpc_server.analyze_resume_core",
            side_effect=GeminiConfigError("no key"),
        )
        ctx = make_context(metadata=auth_metadata)
        with pytest.raises(Exception):
            servicer.AnalyzeResume(
                job_agent_pb2.ResumeAnalysisRequest(resume_text="resume"), ctx
            )
        assert ctx.aborted
        assert ctx.abort_code == grpc.StatusCode.INTERNAL

    def test_generate_cover_letter_aborts_on_gemini_invalid_request(
        self, servicer, make_context, auth_metadata, mocker
    ):
        import grpc
        from proto import job_agent_pb2
        from exceptions import GeminiInvalidRequestError
        mocker.patch(
            "grpc_server.generate_cover_letter_core",
            side_effect=GeminiInvalidRequestError("blocked"),
        )
        ctx = make_context(metadata=auth_metadata)
        req = job_agent_pb2.CoverLetterRequest(
            resume_text="r", job_title="t", company_name="c", job_description="d"
        )
        with pytest.raises(Exception):
            servicer.GenerateCoverLetter(req, ctx)
        assert ctx.aborted
        assert ctx.abort_code == grpc.StatusCode.INVALID_ARGUMENT


# ── GenerateCoverLetter (protected) ───────────────────────────────────────────

class TestGenerateCoverLetter:
    def _full_request(self, pb2):
        return pb2.CoverLetterRequest(
            resume_text="my resume",
            job_title="Engineer",
            company_name="ACME",
            job_description="Build things.",
            user_name="Jane",
        )

    def test_aborts_without_auth(self, servicer, make_context):
        import grpc
        from proto import job_agent_pb2
        ctx = make_context()
        with pytest.raises(Exception):
            servicer.GenerateCoverLetter(self._full_request(job_agent_pb2), ctx)
        assert ctx.aborted
        assert ctx.abort_code == grpc.StatusCode.UNAUTHENTICATED

    def test_returns_cover_letter_with_auth(self, servicer, make_context, auth_metadata):
        from proto import job_agent_pb2
        resp = servicer.GenerateCoverLetter(
            self._full_request(job_agent_pb2),
            make_context(metadata=auth_metadata),
        )
        assert resp.cover_letter == "Dear Hiring Manager..."

    def test_aborts_when_required_fields_missing(self, servicer, make_context, auth_metadata):
        import grpc
        from proto import job_agent_pb2
        ctx = make_context(metadata=auth_metadata)
        # Missing job_title, company_name, job_description
        req = job_agent_pb2.CoverLetterRequest(
            resume_text="resume", job_title="", company_name="", job_description=""
        )
        with pytest.raises(Exception):
            servicer.GenerateCoverLetter(req, ctx)
        assert ctx.aborted
        assert ctx.abort_code == grpc.StatusCode.INVALID_ARGUMENT

    def test_defaults_user_name_to_applicant(self, servicer, make_context, auth_metadata, mocker):
        from proto import job_agent_pb2
        mock_gen = mocker.patch(
            "grpc_server.generate_cover_letter_core", return_value="letter"
        )
        req = job_agent_pb2.CoverLetterRequest(
            resume_text="resume",
            job_title="Dev",
            company_name="Co",
            job_description="Do stuff.",
            user_name="",  # empty → should default to "Applicant"
        )
        servicer.GenerateCoverLetter(req, make_context(metadata=auth_metadata))
        _, kwargs = mock_gen.call_args
        assert kwargs.get("user_name") == "Applicant"


# ── ClearSession (protected) ──────────────────────────────────────────────────

class TestClearSession:
    def test_aborts_without_auth(self, servicer, make_context):
        import grpc
        from proto import job_agent_pb2
        ctx = make_context()
        with pytest.raises(Exception):
            servicer.ClearSession(
                job_agent_pb2.ClearSessionRequest(session_id="s1"), ctx
            )
        assert ctx.aborted
        assert ctx.abort_code == grpc.StatusCode.UNAUTHENTICATED

    def test_clears_session_and_returns_success(self, servicer, make_context, auth_metadata):
        from proto import job_agent_pb2
        resp = servicer.ClearSession(
            job_agent_pb2.ClearSessionRequest(session_id="sess-abc"),
            make_context(metadata=auth_metadata),
        )
        assert resp.session_id == "sess-abc"
        assert "cleared" in resp.message.lower()

    def test_aborts_when_session_id_empty(self, servicer, make_context, auth_metadata):
        import grpc
        from proto import job_agent_pb2
        ctx = make_context(metadata=auth_metadata)
        with pytest.raises(Exception):
            servicer.ClearSession(
                job_agent_pb2.ClearSessionRequest(session_id=""), ctx
            )
        assert ctx.aborted
        assert ctx.abort_code == grpc.StatusCode.INVALID_ARGUMENT

    def test_calls_clear_session_with_correct_id(self, servicer, make_context, auth_metadata, mocker):
        from proto import job_agent_pb2
        mock_clear = mocker.patch("grpc_server.clear_session")
        servicer.ClearSession(
            job_agent_pb2.ClearSessionRequest(session_id="sess-xyz"),
            make_context(metadata=auth_metadata),
        )
        mock_clear.assert_called_once_with("sess-xyz")


# ── ListSessions (protected) ──────────────────────────────────────────────────

class TestListSessions:
    def test_aborts_without_auth(self, servicer, make_context):
        import grpc
        from proto import job_agent_pb2
        ctx = make_context()
        with pytest.raises(Exception):
            servicer.ListSessions(job_agent_pb2.ListSessionsRequest(), ctx)
        assert ctx.aborted
        assert ctx.abort_code == grpc.StatusCode.UNAUTHENTICATED

    def test_returns_session_list(self, servicer, make_context, auth_metadata):
        from proto import job_agent_pb2
        resp = servicer.ListSessions(
            job_agent_pb2.ListSessionsRequest(),
            make_context(metadata=auth_metadata),
        )
        assert resp.sessions == ["s1", "s2"]


# ── _map_app_error ────────────────────────────────────────────────────────────

class TestMapAppError:
    def test_auth0_credentials_error_maps_to_unauthenticated(self):
        import grpc
        from grpc_server import _map_app_error
        from exceptions import Auth0CredentialsError
        code, _ = _map_app_error(Auth0CredentialsError("bad creds"))
        assert code == grpc.StatusCode.UNAUTHENTICATED

    def test_auth0_network_error_maps_to_unavailable(self):
        import grpc
        from grpc_server import _map_app_error
        from exceptions import Auth0NetworkError
        code, _ = _map_app_error(Auth0NetworkError("network"))
        assert code == grpc.StatusCode.UNAVAILABLE

    def test_auth0_config_error_maps_to_internal(self):
        import grpc
        from grpc_server import _map_app_error
        from exceptions import Auth0ConfigError
        code, _ = _map_app_error(Auth0ConfigError("no domain"))
        assert code == grpc.StatusCode.INTERNAL

    def test_gemini_rate_limit_maps_to_resource_exhausted(self):
        import grpc
        from grpc_server import _map_app_error
        from exceptions import GeminiRateLimitError
        code, _ = _map_app_error(GeminiRateLimitError("rate limited"))
        assert code == grpc.StatusCode.RESOURCE_EXHAUSTED

    def test_gemini_quota_exceeded_maps_to_unavailable(self):
        import grpc
        from grpc_server import _map_app_error
        from exceptions import GeminiQuotaExceededError
        code, _ = _map_app_error(GeminiQuotaExceededError("quota"))
        assert code == grpc.StatusCode.UNAVAILABLE

    def test_gemini_network_error_maps_to_unavailable(self):
        import grpc
        from grpc_server import _map_app_error
        from exceptions import GeminiNetworkError
        code, _ = _map_app_error(GeminiNetworkError("net"))
        assert code == grpc.StatusCode.UNAVAILABLE

    def test_gemini_invalid_request_maps_to_invalid_argument(self):
        import grpc
        from grpc_server import _map_app_error
        from exceptions import GeminiInvalidRequestError
        code, _ = _map_app_error(GeminiInvalidRequestError("bad prompt"))
        assert code == grpc.StatusCode.INVALID_ARGUMENT

    def test_serpapi_rate_limit_maps_to_resource_exhausted(self):
        import grpc
        from grpc_server import _map_app_error
        from exceptions import SerpApiRateLimitError
        code, _ = _map_app_error(SerpApiRateLimitError("quota"))
        assert code == grpc.StatusCode.RESOURCE_EXHAUSTED

    def test_serpapi_network_error_maps_to_unavailable(self):
        import grpc
        from grpc_server import _map_app_error
        from exceptions import SerpApiNetworkError
        code, _ = _map_app_error(SerpApiNetworkError("net"))
        assert code == grpc.StatusCode.UNAVAILABLE

    def test_serpapi_config_error_maps_to_internal(self):
        import grpc
        from grpc_server import _map_app_error
        from exceptions import SerpApiConfigError
        code, _ = _map_app_error(SerpApiConfigError("no key"))
        assert code == grpc.StatusCode.INTERNAL

    def test_generic_app_error_maps_to_internal(self):
        import grpc
        from grpc_server import _map_app_error
        from exceptions import AppError
        code, _ = _map_app_error(AppError("oops"))
        assert code == grpc.StatusCode.INTERNAL

    def test_error_message_included_in_detail(self):
        from grpc_server import _map_app_error
        from exceptions import Auth0CredentialsError
        _, detail = _map_app_error(Auth0CredentialsError("token expired"))
        assert "token expired" in detail


# ── _require_auth ─────────────────────────────────────────────────────────────

class TestRequireAuth:
    def test_aborts_when_no_authorization_header(self, make_context):
        import grpc
        ctx = make_context()  # no metadata at all
        with pytest.raises(Exception):
            from grpc_server import _require_auth
            _require_auth(ctx)
        assert ctx.aborted
        assert ctx.abort_code == grpc.StatusCode.UNAUTHENTICATED

    def test_aborts_when_header_not_bearer(self, make_context):
        import grpc
        ctx = make_context(metadata=[("authorization", "Token xyz")])
        with pytest.raises(Exception):
            from grpc_server import _require_auth
            _require_auth(ctx)
        assert ctx.aborted
        assert ctx.abort_code == grpc.StatusCode.UNAUTHENTICATED

    def test_returns_payload_on_valid_token(self, make_context, mocker):
        mocker.patch(
            "grpc_server.verify_token",
            return_value={"sub": "auth0|valid"},
        )
        ctx    = make_context(metadata=[("authorization", "Bearer valid.tok")])
        from grpc_server import _require_auth
        result = _require_auth(ctx)
        assert result == {"sub": "auth0|valid"}
        assert not ctx.aborted

    def test_aborts_when_verify_token_raises_credentials_error(self, make_context, mocker):
        import grpc
        from exceptions import Auth0CredentialsError
        mocker.patch(
            "grpc_server.verify_token",
            side_effect=Auth0CredentialsError("expired"),
        )
        ctx = make_context(metadata=[("authorization", "Bearer expired.tok")])
        with pytest.raises(Exception):
            from grpc_server import _require_auth
            _require_auth(ctx)
        assert ctx.aborted
        assert ctx.abort_code == grpc.StatusCode.UNAUTHENTICATED

    def test_aborts_when_verify_token_raises_config_error(self, make_context, mocker):
        import grpc
        from exceptions import Auth0ConfigError
        mocker.patch(
            "grpc_server.verify_token",
            side_effect=Auth0ConfigError("no domain"),
        )
        ctx = make_context(metadata=[("authorization", "Bearer tok")])
        with pytest.raises(Exception):
            from grpc_server import _require_auth
            _require_auth(ctx)
        assert ctx.aborted
        assert ctx.abort_code == grpc.StatusCode.INTERNAL

    def test_require_auth_returns_empty_dict_when_abort_does_not_raise(self, mocker):
        """Covers line 140: the ``return {}`` after context.abort() for a non-raising context."""
        from exceptions import Auth0CredentialsError
        mocker.patch(
            "grpc_server.verify_token",
            side_effect=Auth0CredentialsError("expired"),
        )
        ctx = MagicMock()  # .abort() does NOT raise (matches real gRPC behaviour)
        ctx.invocation_metadata.return_value = [("authorization", "Bearer tok")]

        from grpc_server import _require_auth
        result = _require_auth(ctx)
        assert result == {}
        ctx.abort.assert_called_once()


# ── serve() ───────────────────────────────────────────────────────────────────

class TestServe:
    """
    Tests for grpc_server.serve() — server startup, TLS configuration,
    and KeyboardInterrupt graceful shutdown.  Covers lines 350-383.
    """

    def test_tls_raises_value_error_without_cert_or_key(self, mocker):
        mock_server = MagicMock()
        mocker.patch("grpc_server.grpc.server", return_value=mock_server)

        from grpc_server import serve
        with pytest.raises(ValueError, match="TLS requires"):
            serve(use_tls=True)  # no tls_cert_chain or tls_private_key

    def test_tls_raises_value_error_when_key_is_missing(self, mocker):
        mock_server = MagicMock()
        mocker.patch("grpc_server.grpc.server", return_value=mock_server)

        from grpc_server import serve
        with pytest.raises(ValueError, match="TLS requires"):
            serve(use_tls=True, tls_cert_chain="cert.pem")  # no private key

    def test_insecure_server_calls_add_insecure_port(self, mocker):
        mock_server = MagicMock()
        mocker.patch("grpc_server.grpc.server", return_value=mock_server)
        mock_server.wait_for_termination.return_value = None

        from grpc_server import serve
        serve()

        mock_server.add_insecure_port.assert_called_once()
        mock_server.start.assert_called_once()

    def test_insecure_port_uses_host_and_port(self, mocker):
        mock_server = MagicMock()
        mocker.patch("grpc_server.grpc.server", return_value=mock_server)
        mock_server.wait_for_termination.return_value = None

        from grpc_server import serve
        serve(host="127.0.0.1", port=9999)

        call_args = mock_server.add_insecure_port.call_args[0][0]
        assert "127.0.0.1" in call_args
        assert "9999" in call_args

    def test_keyboard_interrupt_triggers_graceful_stop(self, mocker):
        mock_server = MagicMock()
        mocker.patch("grpc_server.grpc.server", return_value=mock_server)
        mock_server.wait_for_termination.side_effect = KeyboardInterrupt()

        from grpc_server import serve
        serve()  # must not raise

        mock_server.stop.assert_called_once_with(grace=5)

    def test_tls_server_calls_add_secure_port(self, mocker, tmp_path):
        cert_file = tmp_path / "cert.pem"
        key_file  = tmp_path / "key.pem"
        cert_file.write_bytes(b"CERT_DATA")
        key_file.write_bytes(b"KEY_DATA")

        mock_server = MagicMock()
        mocker.patch("grpc_server.grpc.server", return_value=mock_server)
        mocker.patch("grpc_server.grpc.ssl_server_credentials", return_value=MagicMock())
        mock_server.wait_for_termination.return_value = None

        from grpc_server import serve
        serve(
            use_tls=True,
            tls_cert_chain=str(cert_file),
            tls_private_key=str(key_file),
        )

        mock_server.add_secure_port.assert_called_once()
        mock_server.start.assert_called_once()
