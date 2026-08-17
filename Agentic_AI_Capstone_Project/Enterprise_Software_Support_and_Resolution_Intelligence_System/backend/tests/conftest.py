"""
tests/conftest.py

Shared pytest fixtures: an async test client wrapping the FastAPI app, and
fixtures that seed test users directly via the DB session.

---------------------------------------------------------------------------
Design decision: a separate, dedicated test database — not the dev DB
---------------------------------------------------------------------------
This suite runs against its own Postgres database
(`{DB_NAME}_test`, e.g. `enterprise_support_intelligence_db_test`), created
and Alembic-migrated fresh at the start of the test session and dropped at
the end — never `enterprise_support_intelligence_db`, the dev database that
already holds real conversation/message rows from manual testing.

Why: this project has treated per-project/per-assignment database isolation
as a first-class concern from day one (every prior assignment got its own
dedicated DB before any code was written) — running tests against the dev
DB instead would be the first time that principle was quietly dropped, for
no real benefit. Concretely, it would risk two things: (1) a login-lockout
test needs exactly 5 failed attempts and a 6th that must be blocked — that
depends on rate-limit/user state nobody else is touching at that moment,
which the dev DB can't promise if a developer is poking the running app by
hand; (2) tests would be reading/writing real seeded rows, so a bug in a
test's cleanup (or a test that crashes mid-run) could silently corrupt data
someone was relying on for manual QA. A disposable DB removes both risks
structurally instead of relying on careful test hygiene to avoid them.

This also mirrors `.github/workflows/backend-ci.yml` exactly: CI spins up
its own ephemeral `esri_ci` Postgres/Redis service containers and runs
`alembic upgrade head` before pytest ever starts. This file is the
local-dev equivalent of that CI service-container step — same idea
(disposable, migrated, torn down), just against a real local Postgres
instead of a GitHub Actions service container.

Setup/teardown, once per test session (see `_test_infrastructure` below):
  1. Connect to the `postgres` maintenance database and DROP + CREATE
     `{DB_NAME}_test`, so every run starts from a genuinely clean schema —
     not accumulated cruft from a previous run.
  2. Run `alembic upgrade head` as a subprocess against that database
     (mirrors the CI step verbatim). Schema comes from the real migration
     chain, not a `Base.metadata.create_all()` shortcut, so these tests
     exercise the same DDL that would actually ship.
  3. Redis gets the same treatment for the same reason: `REDIS_URL`'s
     logical DB index is swapped to a dedicated index and flushed before
     the session runs, so the login-lockout test's counters (and the
     logout test's blacklist entries) start clean rather than inheriting
     whatever manual dev testing left behind on the dev index.
  4. Session end: dispose the app's pooled async engine, then drop the
     test database. Nothing persists between runs.

`app/config.py` deliberately skips loading `.env` when running under
pytest (see its `"pytest" in sys.modules` check) — this file is *why*:
it loads both `.env` files itself, then overrides `DB_NAME`/`REDIS_URL`
*before* any `app.*` module is imported. That ordering is the whole trick:
`get_settings()` is `lru_cache`d, so whatever is in `os.environ` the first
time it's called is what the entire test session gets. Every `app.*`
import below the env-setup block is deliberately placed after it.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio

# §40's Postgres checkpointer (psycopg's async driver) cannot run under
# Windows' default ProactorEventLoop — see app/main.py's own copy of this
# same fix for the full explanation (MCP's stdio client already has a
# documented fallback for SelectorEventLoop, so this is safe for both).
# Must run before pytest-asyncio creates its first event loop.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# ---------------------------------------------------------------------------
# 1. Environment setup — MUST run before any `app.*` module is imported.
# ---------------------------------------------------------------------------

_THIS_FILE = Path(__file__).resolve()
_BACKEND_DIR = _THIS_FILE.parents[1]        # backend/
_PROJECT_ROOT = _THIS_FILE.parents[2]       # Enterprise_..._System/
_SUITE_ROOT = _THIS_FILE.parents[4]         # Building_Agentic_AI_Systems/ (root .env)


def _swap_redis_db_index(url: str, new_index: int) -> str:
    base = url.rsplit("/", 1)[0]
    return f"{base}/{new_index}"


def _load_test_environment() -> None:
    """Replicate app/config.py's dual-.env load (skipped there under pytest)
    so real local secrets (DB host/user/password, JWT secret, Redis URL,
    Azure/Langfuse/SMTP keys) are available, then redirect DB_NAME/REDIS_URL
    at dedicated, disposable test resources."""
    from dotenv import load_dotenv

    root_env = _SUITE_ROOT / ".env"
    project_env = _PROJECT_ROOT / ".env"
    if root_env.exists():
        load_dotenv(root_env)
    if project_env.exists():
        load_dotenv(project_env, override=True)

    dev_db_name = os.environ.get("DB_NAME", "enterprise_support_intelligence_db")
    os.environ["DB_NAME"] = f"{dev_db_name}_test"

    dev_redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/1")
    os.environ["REDIS_URL"] = _swap_redis_db_index(dev_redis_url, new_index=15)

    os.environ.setdefault("LLM_PROVIDER", "mock")  # unused by auth, kept for CI parity


_load_test_environment()

# `backend/` must be on sys.path for `app.*` to resolve. `python -m pytest`
# adds cwd automatically, but CI (backend-ci.yml) and most local setups
# invoke plain `pytest`, which does not — without this, conftest fails to
# import for every test in the suite, not just this one.
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

# Safe to import app.* only now that the test environment is finalized.
import psycopg  # noqa: E402
import redis as redis_sync  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import delete, select  # noqa: E402

from app.auth.security import hash_password  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.db.models import (  # noqa: E402
    Conversation,
    Customer,
    EscalationLog,
    IncidentLog,
    Message,
    NotificationLog,
    PasswordResetToken,
    SupportTicket,
    User,
    UserRole,
)
from app.db.session import async_session_maker, engine  # noqa: E402
from app.main import app  # noqa: E402

TEST_PASSWORD = "Test-Passw0rd!"


# ---------------------------------------------------------------------------
# 2. Database + Redis lifecycle (session-scoped, autouse)
# ---------------------------------------------------------------------------

def _maintenance_connection() -> psycopg.Connection:
    settings = get_settings()
    return psycopg.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        dbname="postgres",
        autocommit=True,
    )


def _drop_database(dbname: str) -> None:
    with _maintenance_connection() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(f'DROP DATABASE IF EXISTS "{dbname}" WITH (FORCE)')
            except Exception:
                # Postgres < 13 doesn't support WITH (FORCE); fall back.
                cur.execute(f'DROP DATABASE IF EXISTS "{dbname}"')


def _create_database(dbname: str) -> None:
    _drop_database(dbname)
    with _maintenance_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f'CREATE DATABASE "{dbname}"')


def _run_alembic_upgrade() -> None:
    """Run `alembic upgrade head` against the test database, in a subprocess
    (mirrors the CI step exactly — see module docstring).

    This can't be a plain `python -m alembic upgrade head` subprocess: that
    fresh interpreter has no "pytest" in its own sys.modules, so
    app/config.py's `_load_env()` guard doesn't trigger there — it would
    reload the project .env with override=True and silently reset DB_NAME
    back to the dev database before migrating, defeating the whole point
    of this fixture. Importing pytest first is a one-line sentinel that
    makes the subprocess match this process's env-loading behavior exactly.
    """
    script = (
        "import pytest\n"
        "from alembic.config import Config\n"
        "from alembic import command\n"
        "command.upgrade(Config('alembic.ini'), 'head')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=str(_BACKEND_DIR),
        env=os.environ.copy(),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "`alembic upgrade head` failed while building the test database:\n"
            f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
        )


def _flush_test_redis() -> None:
    settings = get_settings()
    if not settings.redis_url:
        return
    client = redis_sync.from_url(settings.redis_url)
    try:
        client.ping()
    except Exception as exc:
        pytest.exit(
            f"Redis at {settings.redis_url!r} is unreachable. The login-lockout "
            "and logout-blacklist tests require a running local Redis — "
            f"start it and retry. ({exc})",
            returncode=1,
        )
    client.flushdb()
    client.close()


@pytest.fixture(scope="session", autouse=True)
def _test_infrastructure():
    """Builds the disposable test database + Redis namespace once per test
    session, and tears both down afterward. See module docstring for the
    reasoning behind not reusing the dev database."""
    settings = get_settings()

    _create_database(settings.db_name)
    _run_alembic_upgrade()
    _flush_test_redis()

    yield

    # Close pooled connections before dropping the DB out from under them.
    asyncio.run(engine.dispose())
    _drop_database(settings.db_name)


# ---------------------------------------------------------------------------
# 3. Async HTTP client — one fake source IP per test node, so the shared
#    5/15min login rate limit (keyed by IP, §16.1) can't leak between tests.
# ---------------------------------------------------------------------------

def _fake_client_ip(nodeid: str) -> str:
    digest = hashlib.sha256(nodeid.encode()).digest()
    return f"10.{digest[0]}.{digest[1]}.{digest[2]}"


@pytest_asyncio.fixture(autouse=True)
async def _fresh_engine_pool_per_test():
    """pytest-asyncio gives each test its own event loop by default, but
    app.db.session.engine's connection pool is a module-level singleton
    created once at import time. A connection pooled under one test's loop
    is dead by the time a later test (running on a different loop) tries
    to reuse it ('Event loop is closed'). Disposing the pool after every
    test forces the next test to open fresh connections under its own
    loop — cheap here since these are simple auth queries, not a
    performance-sensitive path."""
    yield
    await engine.dispose()


@pytest_asyncio.fixture
async def client(request: pytest.FixtureRequest):
    """Async test client wrapping the FastAPI app directly over ASGI (no
    real network socket, no separate server process — the app is fully
    async so ASGITransport is the natural fit). Each test gets its own
    fake source IP so per-IP rate limiting is isolated per test."""
    fake_ip = _fake_client_ip(request.node.nodeid)
    transport = ASGITransport(app=app, client=(fake_ip, 12345))
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


# ---------------------------------------------------------------------------
# 4. Test users — created directly via the DB session, not through an
#    endpoint (none exists, by design — §22.1).
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def make_user():
    """Factory fixture: insert a user row directly via the DB session with
    a known password, return (User, raw_password). Each call gets a unique
    email so parallel fixtures across tests never collide on the unique
    constraint; rows are cleaned up after the test regardless."""
    created_ids: list[int] = []

    async def _make_user(
        role: UserRole = UserRole.support_agent,
        password: str = TEST_PASSWORD,
        is_active: bool = True,
    ) -> tuple[User, str]:
        email = f"{role.value}-{uuid4().hex[:12]}@test.local"
        async with async_session_maker() as session:
            user = User(
                email=email,
                password_hash=hash_password(password),
                role=role,
                is_active=is_active,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            created_ids.append(user.user_id)
            return user, password

    yield _make_user

    if created_ids:
        async with async_session_maker() as session:
            await session.execute(delete(User).where(User.user_id.in_(created_ids)))
            await session.commit()


@pytest_asyncio.fixture
async def support_agent_user(make_user):
    """A single ready-made support_agent user (email, password known)."""
    return await make_user(role=UserRole.support_agent)


@pytest_asyncio.fixture
async def admin_user(make_user):
    """A single ready-made admin user (email, password known)."""
    return await make_user(role=UserRole.admin)


@pytest_asyncio.fixture
async def cleanup_password_reset_tokens():
    """FK-teardown-ordering concern (same shape as cleanup_conversations/
    cleanup_escalations below): password_reset_tokens.user_id has no ON
    DELETE CASCADE (production code only ever soft-deactivates a user,
    never hard-deletes it — this constraint only matters for this
    disposable test DB's own hard-delete-based cleanup). Tests append the
    owning user_id here; must be requested AFTER support_agent_user/
    admin_user/make_user in the test's own parameter list so this
    fixture's teardown (LIFO) runs before make_user's."""
    user_ids: list[int] = []
    yield user_ids
    if user_ids:
        async with async_session_maker() as session:
            await session.execute(delete(PasswordResetToken).where(PasswordResetToken.user_id.in_(user_ids)))
            await session.commit()


# ---------------------------------------------------------------------------
# 4b. Test customers/tickets/incidents — course-provided tables (§21), same
#     "insert directly via the DB session" pattern as make_user, needed by
#     Stage 6's sql_tools whitelist tests and account_validation tests.
#     support_tickets.customer_id has ON DELETE CASCADE (db/models.py), so
#     deleting a customer row already cleans up its own tickets; incident_logs
#     has no FK back to customers at all (Stage 6's "third gap" — matched by
#     region, not customer_id) so it needs its own independent cleanup list.
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def make_customer():
    """Factory fixture: insert a customer row directly, return the Customer
    object. Each call gets a unique company_name so parallel tests never
    collide on anything customer_id-adjacent."""
    created_ids: list[int] = []

    async def _make_customer(**overrides) -> Customer:
        defaults = {
            "company_name": f"Test Co {uuid4().hex[:12]}",
            "subscription_tier": "standard",
            "account_status": "active",
            "sla_level": "standard",
            "region": "us-east",
        }
        defaults.update(overrides)
        async with async_session_maker() as session:
            customer = Customer(**defaults)
            session.add(customer)
            await session.commit()
            await session.refresh(customer)
            created_ids.append(customer.customer_id)
            return customer

    yield _make_customer

    if created_ids:
        async with async_session_maker() as session:
            await session.execute(delete(Customer).where(Customer.customer_id.in_(created_ids)))
            await session.commit()


@pytest_asyncio.fixture
async def make_ticket():
    """Factory fixture: insert a support_tickets row for a given customer_id."""
    created_ids: list[int] = []

    async def _make_ticket(customer_id: int, **overrides) -> SupportTicket:
        defaults = {
            "customer_id": customer_id,
            "issue_category": "billing",
            "severity_level": "Low",
            "ticket_status": "open",
        }
        defaults.update(overrides)
        async with async_session_maker() as session:
            ticket = SupportTicket(**defaults)
            session.add(ticket)
            await session.commit()
            await session.refresh(ticket)
            created_ids.append(ticket.ticket_id)
            return ticket

    yield _make_ticket

    if created_ids:
        async with async_session_maker() as session:
            await session.execute(delete(SupportTicket).where(SupportTicket.ticket_id.in_(created_ids)))
            await session.commit()


@pytest_asyncio.fixture
async def make_incident():
    """Factory fixture: insert an incident_logs row. No customer_id FK
    exists (Stage 6's "third gap") — incidents are matched to a customer
    by affected_region, so tests seed this with an explicit region."""
    created_ids: list[int] = []

    async def _make_incident(**overrides) -> IncidentLog:
        defaults = {
            "incident_type": "outage",
            "severity": "High",
            "affected_region": "us-east",
            "resolution_status": "investigating",
        }
        defaults.update(overrides)
        async with async_session_maker() as session:
            incident = IncidentLog(**defaults)
            session.add(incident)
            await session.commit()
            await session.refresh(incident)
            created_ids.append(incident.incident_id)
            return incident

    yield _make_incident

    if created_ids:
        async with async_session_maker() as session:
            await session.execute(delete(IncidentLog).where(IncidentLog.incident_id.in_(created_ids)))
            await session.commit()


# ---------------------------------------------------------------------------
# 4c. Test escalations/notifications (Stage 7, §21) — same "insert directly
#     via the DB session" pattern as make_customer/make_incident above.
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def make_escalation():
    """Factory fixture: insert an escalation_log row directly. Caller must
    supply handled_by_user_id (a real users.user_id FK — use
    support_agent_user/make_user)."""
    created_ids: list[int] = []

    async def _make_escalation(handled_by_user_id: int, **overrides) -> EscalationLog:
        defaults = {
            "trace_id": f"trace_{uuid4().hex[:12]}",
            "handled_by_user_id": handled_by_user_id,
            "ticket_context_json": {"query": "test query"},
            "reason": "test escalation",
        }
        defaults.update(overrides)
        async with async_session_maker() as session:
            escalation = EscalationLog(**defaults)
            session.add(escalation)
            await session.commit()
            await session.refresh(escalation)
            created_ids.append(escalation.escalation_id)
            return escalation

    yield _make_escalation

    if created_ids:
        async with async_session_maker() as session:
            # notification_log.escalation_id has no ON DELETE CASCADE
            # (db/models.py) — child rows first, then the parent.
            await session.execute(delete(NotificationLog).where(NotificationLog.escalation_id.in_(created_ids)))
            await session.execute(delete(EscalationLog).where(EscalationLog.escalation_id.in_(created_ids)))
            await session.commit()


# ---------------------------------------------------------------------------
# 5. Chat-endpoint cleanup — POST /chat (routes_chat.py) persists
#    Conversation/Message rows tied to handled_by_user_id. make_user's own
#    teardown deletes the User row directly, which violates
#    conversations.handled_by_user_id's FK constraint if those rows still
#    exist. Chat tests append the conversation_id from each response here;
#    fixture teardown order (LIFO) runs this before make_user's, as long as
#    this fixture is requested alongside support_agent_user/admin_user in
#    the same test.
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def cleanup_conversations():
    conversation_ids: list[str] = []
    yield conversation_ids
    if conversation_ids:
        async with async_session_maker() as session:
            await session.execute(delete(Message).where(Message.conversation_id.in_(conversation_ids)))
            await session.execute(delete(Conversation).where(Conversation.conversation_id.in_(conversation_ids)))
            await session.commit()


@pytest_asyncio.fixture
async def cleanup_escalations():
    """Same FK-teardown-ordering concern as cleanup_conversations above,
    for POST /chat calls that escalate (Stage 7): routes_chat.py inserts a
    real escalation_log row tied to handled_by_user_id. ChatResponse
    doesn't expose escalation_id directly, but it does expose trace_id
    (unique per request, and escalation_log.trace_id is set from the same
    value) — tests append the response's trace_id here; must be requested
    AFTER support_agent_user/admin_user in the test's own parameter list
    so this fixture's teardown (LIFO) runs before make_user's."""
    trace_ids: list[str] = []
    yield trace_ids
    if trace_ids:
        async with async_session_maker() as session:
            escalation_ids = (
                await session.execute(select(EscalationLog.escalation_id).where(EscalationLog.trace_id.in_(trace_ids)))
            ).scalars().all()
            if escalation_ids:
                await session.execute(delete(NotificationLog).where(NotificationLog.escalation_id.in_(escalation_ids)))
            await session.execute(delete(EscalationLog).where(EscalationLog.trace_id.in_(trace_ids)))
            await session.commit()
