"""
Unit tests for auth/auth0.py — fetch_token() and the GetToken gRPC RPC.

fetch_token() raises domain exceptions:
  Auth0ConfigError       — missing env vars
  Auth0CredentialsError  — Auth0 rejected the credentials
  Auth0NetworkError      — Auth0 token endpoint unreachable

TestGetTokenGrpc exercises the servicer's GetToken RPC end-to-end using
the grpc_server servicer fixture.
"""
import pytest
from unittest.mock import MagicMock

from exceptions import Auth0ConfigError, Auth0CredentialsError, Auth0NetworkError


# ── fetch_token ───────────────────────────────────────────────────────────────

class TestFetchToken:
    def _mock_success_response(self, access_token="eyJ.test.token"):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "access_token": access_token,
            "token_type":   "Bearer",
            "expires_in":   86400,
        }
        mock_resp.raise_for_status.return_value = None
        return mock_resp

    def test_returns_access_token_on_success(self, mocker):
        mock_resp = self._mock_success_response("eyJ.valid.token")
        mocker.patch("auth.auth0.http_requests.post", return_value=mock_resp)

        from auth.auth0 import fetch_token
        result = fetch_token("user@test.com", "secret123")

        assert result["access_token"] == "eyJ.valid.token"
        assert result["token_type"]   == "Bearer"
        assert result["expires_in"]   == 86400

    def test_posts_to_correct_auth0_url(self, mocker):
        mock_resp = self._mock_success_response()
        mock_post = mocker.patch("auth.auth0.http_requests.post", return_value=mock_resp)

        from auth.auth0 import fetch_token
        fetch_token("user@test.com", "pass")

        call_url = mock_post.call_args[0][0]
        assert "test.auth0.com" in call_url
        assert "/oauth/token" in call_url

    def test_sends_password_grant_type(self, mocker):
        mock_resp = self._mock_success_response()
        mock_post = mocker.patch("auth.auth0.http_requests.post", return_value=mock_resp)

        from auth.auth0 import fetch_token
        fetch_token("user@test.com", "pass")

        payload = mock_post.call_args[1]["json"]
        assert payload["grant_type"] == "password"
        assert payload["username"]   == "user@test.com"
        assert payload["password"]   == "pass"

    def test_sends_correct_client_credentials(self, mocker):
        mock_resp = self._mock_success_response()
        mock_post = mocker.patch("auth.auth0.http_requests.post", return_value=mock_resp)

        from auth.auth0 import fetch_token
        fetch_token("user@test.com", "pass")

        payload = mock_post.call_args[1]["json"]
        assert payload["client_id"] == "test-client-id"
        assert payload["audience"]  == "https://test.api.com"

    def test_raises_config_error_when_domain_missing(self, monkeypatch):
        monkeypatch.setenv("AUTH0_DOMAIN", "")
        from auth.auth0 import fetch_token
        with pytest.raises(Auth0ConfigError) as exc_info:
            fetch_token("user@test.com", "pass")
        assert "AUTH0_DOMAIN" in str(exc_info.value)

    def test_raises_config_error_when_client_secret_missing(self, monkeypatch):
        monkeypatch.setenv("AUTH0_CLIENT_SECRET", "")
        from auth.auth0 import fetch_token
        with pytest.raises(Auth0ConfigError) as exc_info:
            fetch_token("user@test.com", "pass")
        assert "AUTH0_CLIENT_SECRET" in str(exc_info.value)

    def test_raises_credentials_error_on_bad_credentials(self, mocker):
        import requests as req
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"error_description": "Wrong email or password."}
        http_err = req.HTTPError(response=mock_resp)
        mock_resp.raise_for_status.side_effect = http_err

        mocker.patch("auth.auth0.http_requests.post", return_value=mock_resp)

        from auth.auth0 import fetch_token
        with pytest.raises(Auth0CredentialsError) as exc_info:
            fetch_token("user@test.com", "wrong-pass")
        assert "Wrong email or password" in str(exc_info.value)

    def test_raises_network_error_on_connection_failure(self, mocker):
        mocker.patch(
            "auth.auth0.http_requests.post",
            side_effect=ConnectionError("timeout"),
        )

        from auth.auth0 import fetch_token
        with pytest.raises(Auth0NetworkError):
            fetch_token("user@test.com", "pass")

    def test_raises_network_error_on_requests_timeout(self, mocker):
        import requests as req
        mocker.patch(
            "auth.auth0.http_requests.post",
            side_effect=req.Timeout("timed out"),
        )
        from auth.auth0 import fetch_token
        with pytest.raises(Auth0NetworkError) as exc_info:
            fetch_token("u@test.com", "p")
        assert "timed out" in str(exc_info.value).lower()

    def test_raises_network_error_on_requests_connection_error(self, mocker):
        import requests as req
        mocker.patch(
            "auth.auth0.http_requests.post",
            side_effect=req.ConnectionError("refused"),
        )
        from auth.auth0 import fetch_token
        with pytest.raises(Auth0NetworkError):
            fetch_token("u@test.com", "p")

    def test_raises_credentials_error_when_json_parse_fails(self, mocker):
        """Fallback to str(exc) when response.json() raises on bad credentials."""
        import requests as req
        mock_resp = MagicMock()
        mock_resp.json.side_effect = Exception("not json")
        http_err = req.HTTPError(response=mock_resp)
        mock_resp.raise_for_status.side_effect = http_err
        mocker.patch("auth.auth0.http_requests.post", return_value=mock_resp)

        from auth.auth0 import fetch_token
        with pytest.raises(Auth0CredentialsError):
            fetch_token("user@test.com", "wrong-pass")

    def test_default_token_type_is_bearer_when_omitted(self, mocker):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"access_token": "tok", "expires_in": 3600}
        mock_resp.raise_for_status.return_value = None
        mocker.patch("auth.auth0.http_requests.post", return_value=mock_resp)

        from auth.auth0 import fetch_token
        result = fetch_token("u", "p")
        assert result["token_type"] == "Bearer"


# ── GetToken gRPC RPC ─────────────────────────────────────────────────────────

class TestGetTokenGrpc:
    """
    Tests for the GetToken RPC in the gRPC servicer.
    Uses the ``servicer`` fixture from conftest.py which mocks fetch_token.
    """

    def test_returns_200_equivalent_with_valid_credentials(
        self, servicer, make_context
    ):
        from proto import job_agent_pb2
        resp = servicer.GetToken(
            job_agent_pb2.GetTokenRequest(username="user@test.com", password="secret"),
            make_context(),
        )
        assert resp.access_token == "eyJ.token"
        assert resp.token_type   == "Bearer"
        assert resp.expires_in   == 86400

    def test_response_contains_access_token(self, servicer, make_context):
        from proto import job_agent_pb2
        resp = servicer.GetToken(
            job_agent_pb2.GetTokenRequest(username="user@test.com", password="secret"),
            make_context(),
        )
        assert resp.access_token.startswith("eyJ")

    def test_no_auth_header_required(self, servicer, make_context):
        """GetToken is a public RPC — no authorization metadata needed."""
        from proto import job_agent_pb2
        ctx = make_context()  # no metadata
        resp = servicer.GetToken(
            job_agent_pb2.GetTokenRequest(username="u@test.com", password="p"),
            ctx,
        )
        assert not ctx.aborted
        assert resp.access_token

    def test_aborts_invalid_argument_when_username_missing(self, servicer, make_context):
        import grpc
        from proto import job_agent_pb2
        ctx = make_context()
        with pytest.raises(Exception):
            servicer.GetToken(
                job_agent_pb2.GetTokenRequest(username="", password="p"), ctx
            )
        assert ctx.aborted
        assert ctx.abort_code == grpc.StatusCode.INVALID_ARGUMENT

    def test_aborts_invalid_argument_when_password_missing(self, servicer, make_context):
        import grpc
        from proto import job_agent_pb2
        ctx = make_context()
        with pytest.raises(Exception):
            servicer.GetToken(
                job_agent_pb2.GetTokenRequest(username="u@test.com", password=""), ctx
            )
        assert ctx.aborted
        assert ctx.abort_code == grpc.StatusCode.INVALID_ARGUMENT

    def test_propagates_unauthenticated_on_bad_credentials(
        self, servicer, make_context, mocker
    ):
        import grpc
        from proto import job_agent_pb2
        mocker.patch(
            "grpc_server.fetch_token",
            side_effect=Auth0CredentialsError("Wrong email or password."),
        )
        ctx = make_context()
        with pytest.raises(Exception):
            servicer.GetToken(
                job_agent_pb2.GetTokenRequest(
                    username="bad@user.com", password="wrong"
                ),
                ctx,
            )
        assert ctx.aborted
        assert ctx.abort_code == grpc.StatusCode.UNAUTHENTICATED

    def test_propagates_internal_on_config_error(
        self, servicer, make_context, mocker
    ):
        import grpc
        from proto import job_agent_pb2
        mocker.patch(
            "grpc_server.fetch_token",
            side_effect=Auth0ConfigError("Auth0 not configured."),
        )
        ctx = make_context()
        with pytest.raises(Exception):
            servicer.GetToken(
                job_agent_pb2.GetTokenRequest(username="u@t.com", password="p"),
                ctx,
            )
        assert ctx.aborted
        assert ctx.abort_code == grpc.StatusCode.INTERNAL
