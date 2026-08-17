"""
Unit tests for auth/auth0.py — Auth0 RS256 JWT validation.

auth0.py raises domain exceptions (Auth0ConfigError, Auth0CredentialsError,
Auth0NetworkError) instead of FastAPI HTTPException.  Tests assert these
specific exception types so failures surface clearly.

Notes:
- Uses pytest-mock's mocker.patch() which handles module-attribute lookup correctly.
- For _get_jwks (which has @lru_cache), patches http_requests on the module.
- verify_token calls _get_jwks internally, so those tests mock _get_jwks directly.
"""
import pytest
from unittest.mock import MagicMock, patch
from fastapi.security import HTTPAuthorizationCredentials

from exceptions import Auth0ConfigError, Auth0CredentialsError, Auth0NetworkError


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_credentials(token="test.jwt.token"):
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def _make_fake_jwks():
    return {"keys": [{"kid": "key1", "kty": "RSA", "use": "sig", "n": "abc", "e": "AQAB"}]}


# ── _get_jwks ─────────────────────────────────────────────────────────────────

class TestGetJwks:
    def test_raises_config_error_when_auth0_domain_missing(self, monkeypatch):
        monkeypatch.setenv("AUTH0_DOMAIN", "")
        from auth.auth0 import _get_jwks
        with pytest.raises(Auth0ConfigError):
            _get_jwks()

    def test_raises_network_error_on_timeout(self, mocker):
        import requests
        mock_http = MagicMock()
        mock_http.get.side_effect = requests.Timeout("timed out")
        mock_http.Timeout         = requests.Timeout
        mock_http.ConnectionError = requests.ConnectionError
        mock_http.HTTPError       = requests.HTTPError
        mocker.patch("auth.auth0.http_requests", mock_http)

        from auth.auth0 import _get_jwks
        with pytest.raises(Auth0NetworkError) as exc_info:
            _get_jwks()
        assert "timed out" in str(exc_info.value).lower()

    def test_raises_network_error_on_connection_refused(self, mocker):
        import requests
        mock_http = MagicMock()
        mock_http.get.side_effect = requests.ConnectionError("refused")
        mock_http.Timeout         = requests.Timeout
        mock_http.ConnectionError = requests.ConnectionError
        mock_http.HTTPError       = requests.HTTPError
        mocker.patch("auth.auth0.http_requests", mock_http)

        from auth.auth0 import _get_jwks
        with pytest.raises(Auth0NetworkError) as exc_info:
            _get_jwks()
        assert "connect" in str(exc_info.value).lower()

    def test_raises_network_error_on_http_error(self, mocker):
        import requests
        mock_http = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 503
        http_err = requests.HTTPError(response=mock_resp)
        mock_http.get.side_effect = http_err
        mock_http.Timeout         = requests.Timeout
        mock_http.ConnectionError = requests.ConnectionError
        mock_http.HTTPError       = requests.HTTPError
        mocker.patch("auth.auth0.http_requests", mock_http)

        from auth.auth0 import _get_jwks
        with pytest.raises(Auth0NetworkError) as exc_info:
            _get_jwks()
        assert "http error" in str(exc_info.value).lower()

    def test_returns_keys_on_success(self, mocker):
        fake_jwks = _make_fake_jwks()
        mock_resp = MagicMock()
        mock_resp.json.return_value = fake_jwks

        mock_http = MagicMock()
        mock_http.get.return_value = mock_resp

        mocker.patch("auth.auth0.http_requests", mock_http)

        from auth.auth0 import _get_jwks
        result = _get_jwks()

        assert result == fake_jwks
        mock_resp.raise_for_status.assert_called_once()

    def test_raises_network_error_on_request_failure(self, mocker):
        import requests
        mock_http = MagicMock()
        mock_http.get.side_effect = Exception("network error")
        # Preserve real exception classes so auth0.py's except clauses work
        mock_http.Timeout          = requests.Timeout
        mock_http.ConnectionError  = requests.ConnectionError
        mock_http.HTTPError        = requests.HTTPError
        mocker.patch("auth.auth0.http_requests", mock_http)

        from auth.auth0 import _get_jwks
        with pytest.raises(Auth0NetworkError):
            _get_jwks()


# ── verify_token ──────────────────────────────────────────────────────────────

class TestVerifyToken:
    def test_raises_config_error_when_domain_not_set(self, monkeypatch):
        monkeypatch.setenv("AUTH0_DOMAIN", "")
        from auth.auth0 import verify_token
        with pytest.raises(Auth0ConfigError):
            verify_token("any.token.here")

    def test_raises_config_error_when_audience_not_set(self, monkeypatch):
        monkeypatch.setenv("AUTH0_AUDIENCE", "")
        from auth.auth0 import verify_token
        with pytest.raises(Auth0ConfigError):
            verify_token("any.token.here")

    def test_raises_credentials_error_on_invalid_token_header(self, mocker):
        from jose import JWTError
        from auth.auth0 import verify_token

        mocker.patch("auth.auth0._get_jwks", return_value={"keys": []})
        mocker.patch("jose.jwt.get_unverified_header", side_effect=JWTError("bad header"))

        with pytest.raises(Auth0CredentialsError):
            verify_token("bad.token")

    def test_raises_credentials_error_when_no_matching_key(self, mocker):
        from auth.auth0 import verify_token

        fake_jwks = {"keys": [{"kid": "other", "kty": "RSA", "use": "sig", "n": "n", "e": "e"}]}
        mocker.patch("auth.auth0._get_jwks", return_value=fake_jwks)
        mocker.patch("jose.jwt.get_unverified_header", return_value={"kid": "missing"})

        with pytest.raises(Auth0CredentialsError) as exc_info:
            verify_token("some.token")
        assert "matching signing key" in str(exc_info.value)

    def test_raises_credentials_error_on_expired_token(self, mocker):
        from jose.exceptions import ExpiredSignatureError
        from auth.auth0 import verify_token

        fake_key = {"kid": "k1", "kty": "RSA", "use": "sig", "n": "n", "e": "e"}
        mocker.patch("auth.auth0._get_jwks", return_value={"keys": [fake_key]})
        mocker.patch("jose.jwt.get_unverified_header", return_value={"kid": "k1"})
        mocker.patch("jose.jwt.decode", side_effect=ExpiredSignatureError())

        with pytest.raises(Auth0CredentialsError) as exc_info:
            verify_token("expired.token")
        assert "expired" in str(exc_info.value).lower()

    def test_raises_credentials_error_on_generic_jwt_error(self, mocker):
        from jose import JWTError
        from auth.auth0 import verify_token

        fake_key = {"kid": "k1", "kty": "RSA", "use": "sig", "n": "n", "e": "e"}
        mocker.patch("auth.auth0._get_jwks", return_value={"keys": [fake_key]})
        mocker.patch("jose.jwt.get_unverified_header", return_value={"kid": "k1"})
        mocker.patch("jose.jwt.decode", side_effect=JWTError("signature mismatch"))

        with pytest.raises(Auth0CredentialsError) as exc_info:
            verify_token("tampered.token")
        assert "validation failed" in str(exc_info.value).lower()

    def test_returns_payload_on_valid_token(self, mocker):
        from auth.auth0 import verify_token

        fake_key = {"kid": "k1", "kty": "RSA", "use": "sig", "n": "n", "e": "e"}
        expected = {"sub": "auth0|123", "email": "user@test.com"}

        mocker.patch("auth.auth0._get_jwks", return_value={"keys": [fake_key]})
        mocker.patch("jose.jwt.get_unverified_header", return_value={"kid": "k1"})
        mocker.patch("jose.jwt.decode", return_value=expected)

        result = verify_token("valid.token")
        assert result == expected


# ── get_current_user ──────────────────────────────────────────────────────────

class TestGetCurrentUser:
    def test_raises_credentials_error_when_no_credentials(self):
        from auth.auth0 import get_current_user
        with pytest.raises(Auth0CredentialsError) as exc_info:
            get_current_user(credentials=None)
        assert "missing" in str(exc_info.value).lower()

    def test_returns_payload_when_credentials_valid(self, mocker):
        from auth.auth0 import get_current_user
        expected = {"sub": "auth0|abc"}
        mocker.patch("auth.auth0.verify_token", return_value=expected)
        result = get_current_user(credentials=_make_credentials("good.token"))
        assert result == expected


# ── get_optional_user ─────────────────────────────────────────────────────────

class TestGetOptionalUser:
    def test_returns_none_when_no_credentials(self):
        from auth.auth0 import get_optional_user
        result = get_optional_user(credentials=None)
        assert result is None

    def test_returns_payload_when_credentials_valid(self, mocker):
        from auth.auth0 import get_optional_user
        expected = {"sub": "auth0|xyz"}
        mocker.patch("auth.auth0.verify_token", return_value=expected)
        result = get_optional_user(credentials=_make_credentials("good.token"))
        assert result == expected

    def test_returns_none_when_token_invalid(self, mocker):
        from auth.auth0 import get_optional_user
        mocker.patch(
            "auth.auth0.verify_token",
            side_effect=Auth0CredentialsError("bad token"),
        )
        result = get_optional_user(credentials=_make_credentials("bad.token"))
        assert result is None

    def test_returns_none_when_config_error(self, mocker):
        from auth.auth0 import get_optional_user
        mocker.patch(
            "auth.auth0.verify_token",
            side_effect=Auth0ConfigError("no domain"),
        )
        result = get_optional_user(credentials=_make_credentials("tok"))
        assert result is None
