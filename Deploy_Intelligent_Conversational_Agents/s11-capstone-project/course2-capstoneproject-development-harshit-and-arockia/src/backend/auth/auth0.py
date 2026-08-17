"""
Auth0 JWT Authentication Module
--------------------------------
Validates RS256 JWTs issued by Auth0 against the tenant's JWKS endpoint.
Provides FastAPI dependencies for both required and optional authentication.

Raises domain exceptions (see exceptions.py) instead of FastAPI HTTPException
so all errors flow through the uniform ApiResponse envelope.

    Auth0ConfigError       (500) — env vars missing / JWKS unreachable
    Auth0CredentialsError  (401) — bad token, expired token, bad password
    Auth0NetworkError      (503) — Auth0 tenant unreachable
"""
import os
import logging
from functools import lru_cache
from typing import Optional

import requests as http_requests
from jose import jwt, JWTError
from fastapi import Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from exceptions import Auth0ConfigError, Auth0CredentialsError, Auth0NetworkError

logger = logging.getLogger(__name__)

security_scheme = HTTPBearer(auto_error=False)
ALGORITHMS = ["RS256"]


# ── JWKS fetching ─────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _get_jwks() -> dict:
    """Fetch the JWKS from Auth0 and cache the result for the process lifetime."""
    domain = os.getenv("AUTH0_DOMAIN", "").strip()
    if not domain:
        raise Auth0ConfigError(
            "AUTH0_DOMAIN environment variable is not set. "
            "Add it to your .env file or deployment secrets."
        )

    jwks_url = f"https://{domain}/.well-known/jwks.json"
    try:
        resp = http_requests.get(jwks_url, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except http_requests.Timeout:
        logger.error("JWKS fetch timed out: %s", jwks_url)
        raise Auth0NetworkError(
            "Auth0 JWKS endpoint timed out. Auth0 may be experiencing issues."
        )
    except http_requests.ConnectionError as exc:
        logger.error("JWKS fetch — connection error: %s", exc)
        raise Auth0NetworkError(
            f"Could not connect to Auth0 to retrieve signing keys: {exc}"
        )
    except http_requests.HTTPError as exc:
        logger.error("JWKS fetch — HTTP error %s: %s", exc.response.status_code, exc)
        raise Auth0NetworkError(
            f"Auth0 JWKS endpoint returned an unexpected HTTP error: {exc}"
        )
    except Exception as exc:
        logger.error("JWKS fetch failed unexpectedly: %s", exc, exc_info=True)
        raise Auth0NetworkError(
            f"Unable to fetch Auth0 signing keys: {exc}"
        ) from exc


# ── Core token validation ─────────────────────────────────────────────────────

def verify_token(token: str) -> dict:
    """
    Decode and validate an Auth0 RS256 JWT.

    Returns the decoded payload dict on success.

    Raises:
        Auth0ConfigError:       Required env vars are missing.
        Auth0CredentialsError:  Token is invalid, expired, or from the wrong tenant.
        Auth0NetworkError:      Auth0 / JWKS endpoint is unreachable.
    """
    domain   = os.getenv("AUTH0_DOMAIN", "").strip()
    audience = os.getenv("AUTH0_AUDIENCE", "").strip()

    if not domain or not audience:
        missing = [k for k, v in {"AUTH0_DOMAIN": domain, "AUTH0_AUDIENCE": audience}.items() if not v]
        raise Auth0ConfigError(
            f"Auth0 configuration is incomplete. Missing: {', '.join(missing)}"
        )

    jwks = _get_jwks()

    # Parse the token header to find the right signing key
    try:
        unverified_header = jwt.get_unverified_header(token)
    except JWTError as exc:
        raise Auth0CredentialsError(
            f"Token header is malformed and cannot be parsed: {exc}"
        ) from exc

    rsa_key = {}
    for key in jwks.get("keys", []):
        if key.get("kid") == unverified_header.get("kid"):
            rsa_key = {k: key[k] for k in ("kty", "kid", "use", "n", "e") if k in key}
            break

    if not rsa_key:
        raise Auth0CredentialsError(
            "No matching signing key found in Auth0 JWKS. "
            "The token may have been issued by a different Auth0 tenant."
        )

    # Decode and validate
    try:
        payload = jwt.decode(
            token,
            rsa_key,
            algorithms=ALGORITHMS,
            audience=audience,
            issuer=f"https://{domain}/",
        )
        return payload
    except jwt.ExpiredSignatureError as exc:
        raise Auth0CredentialsError("Token has expired. Please sign in again.") from exc
    except JWTError as exc:
        raise Auth0CredentialsError(
            f"Token validation failed: {exc}"
        ) from exc


# ── FastAPI dependency — required auth ────────────────────────────────────────

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security_scheme),
) -> dict:
    """
    FastAPI dependency that requires a valid Bearer JWT.

    Usage:
        current_user: dict = Depends(get_current_user)

    Raises:
        Auth0CredentialsError: if the Authorization header is absent or the token is invalid.
    """
    if credentials is None:
        raise Auth0CredentialsError(
            "Authorization header is missing. "
            "Include 'Authorization: Bearer <token>' in your request."
        )
    return verify_token(credentials.credentials)


# ── Token acquisition — Resource Owner Password Grant ────────────────────────

def fetch_token(username: str, password: str) -> dict:
    """
    Exchange a username/password for an Auth0 access token using the
    Resource Owner Password Grant.

    Returns a dict with keys: access_token, token_type, expires_in.

    Raises:
        Auth0ConfigError:       Required env vars are missing.
        Auth0CredentialsError:  Auth0 rejected the username/password.
        Auth0NetworkError:      Auth0 token endpoint is unreachable.

    Prerequisites (Auth0 dashboard):
        Applications → <app> → Advanced Settings → Grant Types → enable Password.
    """
    domain        = os.getenv("AUTH0_DOMAIN", "").strip()
    client_id     = os.getenv("AUTH0_CLIENT_ID", "").strip()
    client_secret = os.getenv("AUTH0_CLIENT_SECRET", "").strip()
    audience      = os.getenv("AUTH0_AUDIENCE", "").strip()

    missing = [
        k for k, v in {
            "AUTH0_DOMAIN":        domain,
            "AUTH0_CLIENT_ID":     client_id,
            "AUTH0_CLIENT_SECRET": client_secret,
            "AUTH0_AUDIENCE":      audience,
        }.items()
        if not v
    ]
    if missing:
        raise Auth0ConfigError(
            f"Auth0 is not fully configured. Missing variables: {', '.join(missing)}"
        )

    payload = {
        "grant_type":    "password",
        "username":      username,
        "password":      password,
        "client_id":     client_id,
        "client_secret": client_secret,
        "audience":      audience,
        "scope":         "openid profile email",
    }

    try:
        resp = http_requests.post(
            f"https://{domain}/oauth/token",
            json=payload,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            "access_token": data["access_token"],
            "token_type":   data.get("token_type", "Bearer"),
            "expires_in":   data.get("expires_in", 86400),
        }

    except http_requests.HTTPError as exc:
        try:
            error_detail = exc.response.json().get("error_description", str(exc))
        except Exception:
            error_detail = str(exc)
        logger.warning("Auth0 rejected token request for '%s': %s", username, error_detail)
        raise Auth0CredentialsError(error_detail) from exc

    except http_requests.Timeout:
        logger.error("Auth0 token request timed out for user '%s'", username)
        raise Auth0NetworkError(
            "Auth0 token endpoint timed out. Please try again shortly."
        )

    except http_requests.ConnectionError as exc:
        logger.error("Auth0 token request — connection error: %s", exc)
        raise Auth0NetworkError(
            f"Could not connect to Auth0: {exc}"
        ) from exc

    except Exception as exc:
        logger.error("Auth0 token request failed unexpectedly: %s", exc, exc_info=True)
        raise Auth0NetworkError(
            f"Auth0 token request failed: {exc}"
        ) from exc


# ── FastAPI dependency — optional auth ───────────────────────────────────────

def get_optional_user(
    credentials: HTTPAuthorizationCredentials = Security(security_scheme),
) -> Optional[dict]:
    """
    FastAPI dependency that returns the user payload if a valid token is present,
    or None for unauthenticated requests. Does not raise on missing tokens.
    """
    if credentials is None:
        return None
    try:
        return verify_token(credentials.credentials)
    except (Auth0CredentialsError, Auth0ConfigError, Auth0NetworkError):
        return None
