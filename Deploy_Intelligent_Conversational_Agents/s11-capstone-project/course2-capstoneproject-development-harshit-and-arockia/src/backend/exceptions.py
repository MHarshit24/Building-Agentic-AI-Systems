"""
Domain-specific exception hierarchy for the Job Placement Agent API.

Every exception carries two class-level attributes used by the global
``AppError`` exception handler in ``main.py``:

    http_status : int  — the HTTP status code to return to the client
    error_code  : str  — machine-readable code embedded in ApiResponse.error.code

Hierarchy
---------
AppError
├── ConfigurationError          500  CONFIGURATION_ERROR
├── Auth0Error                  502  AUTH0_ERROR
│   ├── Auth0ConfigError        500  AUTH0_CONFIGURATION_ERROR
│   ├── Auth0CredentialsError   401  AUTH0_INVALID_CREDENTIALS
│   └── Auth0NetworkError       503  AUTH0_UNAVAILABLE
├── GeminiError                 502  LLM_ERROR
│   ├── GeminiConfigError       500  LLM_CONFIGURATION_ERROR
│   ├── GeminiRateLimitError    429  LLM_RATE_LIMITED
│   ├── GeminiQuotaExceededError 503 LLM_QUOTA_EXCEEDED
│   ├── GeminiNetworkError      503  LLM_UNAVAILABLE
│   └── GeminiInvalidRequestError 400 LLM_INVALID_REQUEST
├── LangfuseError               502  OBSERVABILITY_ERROR
│   ├── LangfuseConfigError     500  OBSERVABILITY_CONFIGURATION_ERROR
│   └── LangfuseNetworkError    503  OBSERVABILITY_UNAVAILABLE
├── SerpApiError                502  JOB_SEARCH_ERROR
│   ├── SerpApiConfigError      500  JOB_SEARCH_CONFIGURATION_ERROR
│   ├── SerpApiRateLimitError   429  JOB_SEARCH_RATE_LIMITED
│   └── SerpApiNetworkError     503  JOB_SEARCH_UNAVAILABLE
└── AgentError                  502  AGENT_ERROR
"""
from __future__ import annotations


class AppError(Exception):
    """
    Base class for all application-level errors.

    Subclasses set ``http_status`` and ``error_code`` as class variables so
    the global exception handler can respond correctly without inspecting the
    exception type.
    """

    http_status: int = 500
    error_code: str = "INTERNAL_SERVER_ERROR"

    def __init__(self, message: str, *, cause: Exception | None = None) -> None:
        super().__init__(message)
        self.cause = cause


# ── Generic configuration error ───────────────────────────────────────────────

class ConfigurationError(AppError):
    """A required environment variable or configuration value is missing or invalid."""

    http_status = 500
    error_code = "CONFIGURATION_ERROR"


# ── Auth0 ─────────────────────────────────────────────────────────────────────

class Auth0Error(AppError):
    """Base class for all Auth0 authentication errors."""

    http_status = 502
    error_code = "AUTH0_ERROR"


class Auth0ConfigError(Auth0Error):
    """Auth0 environment variables (domain, client ID, audience…) are missing or wrong."""

    http_status = 500
    error_code = "AUTH0_CONFIGURATION_ERROR"


class Auth0CredentialsError(Auth0Error):
    """
    The supplied credentials or JWT are invalid, expired, or rejected by Auth0.
    Maps to HTTP 401 — clients should re-authenticate.
    """

    http_status = 401
    error_code = "AUTH0_INVALID_CREDENTIALS"


class Auth0NetworkError(Auth0Error):
    """The Auth0 tenant could not be reached (network failure or Auth0 outage)."""

    http_status = 503
    error_code = "AUTH0_UNAVAILABLE"


# ── Gemini / LLM ──────────────────────────────────────────────────────────────

class GeminiError(AppError):
    """Base class for all Gemini API / LLM errors."""

    http_status = 502
    error_code = "LLM_ERROR"


class GeminiConfigError(GeminiError):
    """GEMINI_API_KEY or GEMINI_MODEL_NAME is missing or authentication failed."""

    http_status = 500
    error_code = "LLM_CONFIGURATION_ERROR"


class GeminiRateLimitError(GeminiError):
    """Gemini API rate limit exceeded (HTTP 429). The client should back off and retry."""

    http_status = 429
    error_code = "LLM_RATE_LIMITED"


class GeminiQuotaExceededError(GeminiError):
    """Gemini API daily / monthly quota has been exhausted."""

    http_status = 503
    error_code = "LLM_QUOTA_EXCEEDED"


class GeminiNetworkError(GeminiError):
    """The Gemini API could not be reached (connection refused, timeout, or 5xx)."""

    http_status = 503
    error_code = "LLM_UNAVAILABLE"


class GeminiInvalidRequestError(GeminiError):
    """The request was rejected by Gemini (prompt too long, blocked content, etc.)."""

    http_status = 400
    error_code = "LLM_INVALID_REQUEST"


# ── Langfuse ──────────────────────────────────────────────────────────────────

class LangfuseError(AppError):
    """Base class for all Langfuse observability errors."""

    http_status = 502
    error_code = "OBSERVABILITY_ERROR"


class LangfuseConfigError(LangfuseError):
    """Langfuse API keys are missing or invalid."""

    http_status = 500
    error_code = "OBSERVABILITY_CONFIGURATION_ERROR"


class LangfuseNetworkError(LangfuseError):
    """The Langfuse server could not be reached."""

    http_status = 503
    error_code = "OBSERVABILITY_UNAVAILABLE"


# ── SerpAPI / Job Search ──────────────────────────────────────────────────────

class SerpApiError(AppError):
    """Base class for all SerpAPI job search errors."""

    http_status = 502
    error_code = "JOB_SEARCH_ERROR"


class SerpApiConfigError(SerpApiError):
    """SERPAPI_API_KEY is missing or the API returned an authentication error."""

    http_status = 500
    error_code = "JOB_SEARCH_CONFIGURATION_ERROR"


class SerpApiRateLimitError(SerpApiError):
    """SerpAPI rate limit or monthly quota has been exceeded."""

    http_status = 429
    error_code = "JOB_SEARCH_RATE_LIMITED"


class SerpApiNetworkError(SerpApiError):
    """SerpAPI could not be reached."""

    http_status = 503
    error_code = "JOB_SEARCH_UNAVAILABLE"


# ── Agent ─────────────────────────────────────────────────────────────────────

class AgentError(AppError):
    """The LangChain agent failed to produce a valid response."""

    http_status = 502
    error_code = "AGENT_ERROR"
