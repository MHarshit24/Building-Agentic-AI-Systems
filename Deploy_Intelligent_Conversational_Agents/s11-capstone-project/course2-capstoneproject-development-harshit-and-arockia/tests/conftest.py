"""
Shared pytest fixtures for Job Placement Agent backend tests.

Path setup is handled by pytest.ini (pythonpath = src/backend).

Module-level sys.modules stubs at the top of this file ensure that
all backend code can be imported even when the local environment does
not have the exact pinned versions of langchain / grpcio installed.

IMPORTANT: stubs are real types.ModuleType objects (not MagicMock).
Using MagicMock as a module breaks mocker.patch() because MagicMock's
__setattr__ / __getattr__ don't behave like a real module's __dict__.
"""
import os
import sys
import types
from unittest.mock import MagicMock

# ── sys.modules stubs ─────────────────────────────────────────────────────────


def _stub_module(name: str, **attrs):
    """Create a real module object with the given attributes."""
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    return mod


# ── Proto message stub factory ────────────────────────────────────────────────

def _pb(**defaults):
    """
    Build a lightweight protobuf-like message class.

    Instances accept any keyword args and store them as plain attributes.
    Default field values are merged with the constructor kwargs so that
    accesses like ``request.session_id`` return ``""`` even when the
    caller omitted the field.
    """
    class _Msg:
        def __init__(self, **kwargs):
            for k, v in {**defaults, **kwargs}.items():
                setattr(self, k, v)
    return _Msg


# ── Build proto stubs ─────────────────────────────────────────────────────────

_pb2 = _stub_module("proto.job_agent_pb2")

# Public RPC messages
_pb2.HealthRequest         = _pb()
_pb2.HealthResponse        = _pb(status="", version="", message="")
_pb2.GetTokenRequest       = _pb(username="", password="")
_pb2.GetTokenResponse      = _pb(access_token="", token_type="Bearer", expires_in=0)
_pb2.ChatRequest           = _pb(message="", session_id="")
_pb2.ChatResponse          = _pb(response="", session_id="")
_pb2.CreateSessionRequest  = _pb()
_pb2.CreateSessionResponse = _pb(session_id="", message="")

# Protected RPC messages
_pb2.JobSearchRequest       = _pb(query="", location="", session_id="")
_pb2.JobSearchResponse      = _pb(results="", session_id="")
_pb2.ResumeAnalysisRequest  = _pb(resume_text="", job_description="", session_id="")
_pb2.ResumeAnalysisResponse = _pb(analysis="", session_id="")
_pb2.CoverLetterRequest     = _pb(
    resume_text="", job_title="", company_name="",
    job_description="", user_name="", session_id="",
)
_pb2.CoverLetterResponse    = _pb(cover_letter="", session_id="")
_pb2.ClearSessionRequest    = _pb(session_id="")
_pb2.ClearSessionResponse   = _pb(message="", session_id="")
_pb2.ListSessionsRequest    = _pb()
_pb2.ListSessionsResponse   = _pb(sessions=[])

_pb2_grpc = _stub_module("proto.job_agent_pb2_grpc")
_pb2_grpc.JobAgentServiceServicer            = object   # base class
_pb2_grpc.add_JobAgentServiceServicer_to_server = MagicMock()

_proto_pkg = _stub_module("proto")

sys.modules.setdefault("proto",                    _proto_pkg)
sys.modules.setdefault("proto.job_agent_pb2",      _pb2)
sys.modules.setdefault("proto.job_agent_pb2_grpc", _pb2_grpc)

# ── sonora stubs ──────────────────────────────────────────────────────────────
sys.modules.setdefault("sonora",      _stub_module("sonora"))
sys.modules.setdefault("sonora.wsgi", _stub_module("sonora.wsgi", grpcWSGI=MagicMock))

# ── langchain.agents ──────────────────────────────────────────────────────────
sys.modules["langchain.agents"] = _stub_module(
    "langchain.agents",
    AgentExecutor=MagicMock,
    create_tool_calling_agent=MagicMock(),
)

# ── langchain.tools ───────────────────────────────────────────────────────────
def _add_invoke(fn):
    """Attach a minimal .invoke() shim to a plain function."""
    fn.invoke = lambda kwargs, **_: fn(**kwargs)
    fn.name = fn.__name__
    fn.description = (fn.__doc__ or "").strip()
    return fn

def _tool_decorator(fn=None, **kw):
    """Mimic @tool: wrap the function if called directly, return decorator if not."""
    return _add_invoke(fn) if fn else (lambda f: _add_invoke(f))

sys.modules["langchain.tools"] = _stub_module("langchain.tools", tool=_tool_decorator)

# ── langchain_core sub-packages ───────────────────────────────────────────────
_lc_core = _stub_module("langchain_core")
sys.modules["langchain_core"] = _lc_core
sys.modules["langchain_core.prompts"] = _stub_module(
    "langchain_core.prompts",
    ChatPromptTemplate=MagicMock(),
    MessagesPlaceholder=MagicMock(),
)
# runnables: include RunnableBranch + RunnablePassthrough for router.py (Sprint 5/6)
sys.modules["langchain_core.runnables"] = _stub_module(
    "langchain_core.runnables",
    RunnableBranch=MagicMock,
    RunnablePassthrough=MagicMock(),
)
sys.modules["langchain_core.runnables.history"] = _stub_module(
    "langchain_core.runnables.history",
    RunnableWithMessageHistory=MagicMock,
)
# output_parsers: StrOutputParser used in resume_analyzer.py LCEL chain (Sprint 5/6)
sys.modules["langchain_core.output_parsers"] = _stub_module(
    "langchain_core.output_parsers",
    StrOutputParser=MagicMock,
)
# chat_history: InMemoryChatMessageHistory used in job_agent.py
sys.modules["langchain_core.chat_history"] = _stub_module(
    "langchain_core.chat_history",
    InMemoryChatMessageHistory=MagicMock,
)

# ── langchain_community ───────────────────────────────────────────────────────
sys.modules["langchain_community"] = _stub_module("langchain_community")
sys.modules["langchain_community.chat_message_histories"] = _stub_module(
    "langchain_community.chat_message_histories",
    ChatMessageHistory=MagicMock,
)

# ── langchain_openai ──────────────────────────────────────────────────────────
sys.modules["langchain_openai"] = _stub_module(
    "langchain_openai",
    ChatOpenAI=MagicMock,
)

# ── serpapi ───────────────────────────────────────────────────────────────────
if "serpapi" not in sys.modules:
    sys.modules["serpapi"] = _stub_module("serpapi", GoogleSearch=MagicMock)

# ── langfuse ──────────────────────────────────────────────────────────────────
if "langfuse" not in sys.modules:
    sys.modules["langfuse"] = _stub_module("langfuse", Langfuse=MagicMock)
if "langfuse.callback" not in sys.modules:
    sys.modules["langfuse.callback"] = _stub_module(
        "langfuse.callback", CallbackHandler=MagicMock
    )


# ── Standard imports ──────────────────────────────────────────────────────────
import pytest


# ── gRPC test helpers ─────────────────────────────────────────────────────────

class GrpcAbortError(Exception):
    """
    Raised by MockContext.abort() to simulate gRPC aborting the current call.

    Tests catch this via ``pytest.raises(Exception)`` then inspect
    ``ctx.aborted`` and ``ctx.abort_code`` for the exact failure reason.
    """
    def __init__(self, code, details):
        self.code    = code
        self.details = details
        super().__init__(f"gRPC abort: {code.name} — {details}")


class MockContext:
    """
    Minimal test stand-in for ``grpc.ServicerContext``.

    Attributes set after abort():
        aborted       — True once abort() is called
        abort_code    — the grpc.StatusCode passed to abort()
        abort_details — the detail string passed to abort()
    """

    def __init__(self, metadata=None):
        self._metadata   = list(metadata or [])
        self.aborted      = False
        self.abort_code   = None
        self.abort_details = None

    def invocation_metadata(self):
        return self._metadata

    def abort(self, code, details):
        self.aborted       = True
        self.abort_code    = code
        self.abort_details = details
        raise GrpcAbortError(code, details)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def make_context():
    """
    Factory fixture: returns a callable that creates a fresh MockContext.

    Usage::

        ctx = make_context()                           # no auth
        ctx = make_context(metadata=auth_metadata)     # with auth
    """
    def _factory(metadata=None):
        return MockContext(metadata=metadata)
    return _factory


@pytest.fixture()
def auth_metadata():
    """Valid bearer-token metadata tuple for protected RPC calls."""
    return [("authorization", "Bearer test.jwt.token")]


@pytest.fixture()
def servicer(mocker):
    """
    Return an instantiated JobAgentServicer with all external dependencies
    (agent, tools, auth) pre-mocked so servicer tests are fully isolated.
    """
    mocker.patch("grpc_server.run_agent",   return_value="agent reply")
    mocker.patch("grpc_server.clear_session")
    mocker.patch("grpc_server.list_sessions",  return_value=["s1", "s2"])
    mocker.patch("grpc_server.get_session_history", return_value=MagicMock())
    mocker.patch("grpc_server.fetch_job_listings",  return_value="job results")
    mocker.patch("grpc_server.analyze_resume_core", return_value="analysis text")
    mocker.patch(
        "grpc_server.generate_cover_letter_core",
        return_value="Dear Hiring Manager...",
    )
    mocker.patch("grpc_server.fetch_token", return_value={
        "access_token": "eyJ.token",
        "token_type":   "Bearer",
        "expires_in":   86400,
    })
    mocker.patch(
        "grpc_server.verify_token",
        return_value={"sub": "auth0|test-user"},
    )

    from grpc_server import JobAgentServicer
    return JobAgentServicer()


# ── Environment variable fixtures ─────────────────────────────────────────────

@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Provide a clean, predictable environment for every test."""
    monkeypatch.setenv("GEMINI_API_KEY",        "test-gemini-key")
    monkeypatch.setenv("GEMINI_MODEL_NAME",     "gemini-test-model")
    monkeypatch.setenv("GEMINI_BASE_URL",       "https://test.example.com/v1/")
    monkeypatch.setenv("SERPAPI_API_KEY",       "test-serpapi-key")
    monkeypatch.setenv("AUTH0_DOMAIN",          "test.auth0.com")
    monkeypatch.setenv("AUTH0_AUDIENCE",        "https://test.api.com")
    monkeypatch.setenv("AUTH0_CLIENT_ID",       "test-client-id")
    monkeypatch.setenv("AUTH0_CLIENT_SECRET",   "test-client-secret")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY",   "")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY",   "")
    monkeypatch.setenv("LANGFUSE_HOST",         "https://cloud.langfuse.com")


@pytest.fixture()
def langfuse_env(monkeypatch):
    """Override LANGFUSE keys so Langfuse initialisation is attempted."""
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-test-secret")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-test-public")


# ── Cache / singleton reset fixtures ─────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_llm_cache():
    """Clear the lru_cache on get_llm between tests."""
    from agent.llm import get_llm
    get_llm.cache_clear()
    yield
    get_llm.cache_clear()


@pytest.fixture(autouse=True)
def reset_jwks_cache():
    """Clear the lru_cache on _get_jwks between tests."""
    from auth.auth0 import _get_jwks
    _get_jwks.cache_clear()
    yield
    _get_jwks.cache_clear()


@pytest.fixture(autouse=True)
def reset_agent_singletons():
    """Reset lazy agent singletons so each test gets a clean slate."""
    import agent.job_agent as job_agent_module
    job_agent_module._executor            = None
    job_agent_module._agent_with_history  = None
    job_agent_module._session_store.clear()
    yield
    job_agent_module._executor            = None
    job_agent_module._agent_with_history  = None
    job_agent_module._session_store.clear()


@pytest.fixture(autouse=True)
def reset_analysis_chain_cache():
    """Clear lru_cache on _get_analysis_chain (LCEL chain, Sprint 5/6)."""
    from agent.tools.resume_analyzer import _get_analysis_chain
    _get_analysis_chain.cache_clear()
    yield
    _get_analysis_chain.cache_clear()


@pytest.fixture(autouse=True)
def reset_router_caches():
    """Clear lru_caches on router chain factories (Sprint 5/6)."""
    from agent.router import _get_classify_chain, get_router_pipeline
    _get_classify_chain.cache_clear()
    get_router_pipeline.cache_clear()
    yield
    _get_classify_chain.cache_clear()
    get_router_pipeline.cache_clear()
