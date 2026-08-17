"""
app/sql_tools/queries.py

The whitelisted, parametrized-only SQL functions Account Validation Agent
(§3 roster #4) and Incident Severity Agent (§3 roster #5) call. This is
the entire mechanism behind §24.3's "SQL injection via natural language:
structurally impossible" claim — not a documented intention, an actual
Python-level guarantee: every function below accepts only typed `int`
(or no) parameters, never a `str` that could carry a WHERE-clause
fragment, and every query is built with SQLAlchemy's
`select(Model).where(Model.column == python_value)` — never `text()`,
never string formatting/f-strings/concatenation anywhere near a query.
The LLM never sees these as callable tools it invokes with query-derived
arguments; `account_validation_node`/`incident_severity_node` call them
directly, deterministically, in plain Python, before the LLM ever runs
(see those modules' own docstrings — same "tools are pre-fetched, not
LLM-invoked" shape doc_retrieval.py already established in Stage 5).

Each returned dict is tagged with `_source_table`/`_record_id` —
deterministic bookkeeping `respond_node` reads to build `sql`-type
`SourceRef` entries (Stage 6 Deviation L), never derived from LLM output.

get_incidents() and get_active_incidents() both read incident_logs, which
has NO customer_id (or any FK back to customers/support_tickets) — only
affected_region (Stage 6's "third gap", found by reading this schema
directly, not assumed from Blueprint.md's prose). Consequences:
  - get_incidents(customer_id) is customer-*relevant*, not customer-
    *specific* — it resolves the customer's own region, then matches
    incidents affecting that region. account_validation_v1.py's prompt
    must (and does) frame these results as "incidents affecting your
    region," never "your incidents," since the underlying join can't
    support genuine per-account specificity the way get_tickets can.
  - get_active_incidents() is deliberately NOT region/customer-scoped at
    all — Incident Severity's own tool, a system-wide "what's currently
    active" check, independent of any one customer's region.
"active" is defined schema-level as `end_time IS NULL` for both — not a
guess at resolution_status's exact string vocabulary, which isn't
documented anywhere in Blueprint.md or visible in models.py's generic
String columns.
"""

from __future__ import annotations

from sqlalchemy import select

from app.db.models import Customer, IncidentLog, SupportTicket
from app.db.session import async_session_maker


def _require_int(customer_id: int) -> None:
    """A real, driver-independent runtime guarantee, not just a type hint
    (type hints aren't enforced at runtime): the "structurally impossible"
    injection-defense claim (§24.3) shouldn't rest on trusting that asyncpg
    happens to reject a mismatched parameter type — this function refuses
    to even attempt a query if customer_id isn't genuinely an int, closing
    that off at the Python level before SQLAlchemy/asyncpg ever get involved."""
    if not isinstance(customer_id, int):
        raise TypeError(f"customer_id must be an int, got {type(customer_id).__name__}: {customer_id!r}")


def _customer_to_dict(row: Customer) -> dict:
    return {
        "_source_table": "customers",
        "_record_id": row.customer_id,
        "customer_id": row.customer_id,
        "company_name": row.company_name,
        "subscription_tier": row.subscription_tier,
        "account_status": row.account_status,
        "sla_level": row.sla_level,
        "renewal_date": row.renewal_date.isoformat() if row.renewal_date else None,
        "region": row.region,
    }


def _ticket_to_dict(row: SupportTicket) -> dict:
    return {
        "_source_table": "support_tickets",
        "_record_id": row.ticket_id,
        "ticket_id": row.ticket_id,
        "customer_id": row.customer_id,
        "issue_category": row.issue_category,
        "severity_level": row.severity_level,
        "ticket_status": row.ticket_status,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
        "assigned_team": row.assigned_team,
        "escalation_flag": row.escalation_flag,
    }


def _incident_to_dict(row: IncidentLog) -> dict:
    return {
        "_source_table": "incident_logs",
        "_record_id": row.incident_id,
        "incident_id": row.incident_id,
        "incident_type": row.incident_type,
        "severity": row.severity,
        "affected_region": row.affected_region,
        "start_time": row.start_time.isoformat() if row.start_time else None,
        "end_time": row.end_time.isoformat() if row.end_time else None,
        "resolution_status": row.resolution_status,
        # root_cause deliberately excluded here: it's the one free-text field
        # in this schema that could plausibly carry PII a human typed in
        # (Stage 6's Gap 2) — account_validation_node's prompt formatting
        # includes it separately, run through guardrails/pii.redact_pii()
        # before ever reaching the LLM's context, rather than living
        # unredacted in this dict that respond_node also reads for sources.
        "escalation_flag": row.escalation_flag,
    }


async def get_customer(customer_id: int) -> dict | None:
    """Whitelisted lookup — the only argument is a typed int, sourced from
    state["customer_id"] (the authenticated request's own field), never
    from LLM output or raw query text."""
    _require_int(customer_id)
    async with async_session_maker() as db:
        result = await db.execute(select(Customer).where(Customer.customer_id == customer_id))
        row = result.scalar_one_or_none()
    return _customer_to_dict(row) if row else None


async def get_tickets(customer_id: int) -> list[dict]:
    """Whitelisted, genuinely customer-specific (real FK) — support_tickets
    directly references customers.customer_id."""
    _require_int(customer_id)
    async with async_session_maker() as db:
        result = await db.execute(
            select(SupportTicket)
            .where(SupportTicket.customer_id == customer_id)
            .order_by(SupportTicket.ticket_id.desc())
        )
        rows = result.scalars().all()
    return [_ticket_to_dict(row) for row in rows]


async def get_incidents(customer_id: int) -> list[dict]:
    """Whitelisted, but region-relevant rather than customer-specific — see
    this module's own docstring for why (incident_logs has no customer_id
    FK). Returns unresolved (end_time IS NULL) incidents affecting the
    customer's own region; empty list if the customer has no region set
    or doesn't exist."""
    _require_int(customer_id)
    async with async_session_maker() as db:
        customer_result = await db.execute(select(Customer.region).where(Customer.customer_id == customer_id))
        region = customer_result.scalar_one_or_none()
        if not region:
            return []

        result = await db.execute(
            select(IncidentLog)
            .where(IncidentLog.affected_region == region, IncidentLog.end_time.is_(None))
            .order_by(IncidentLog.start_time.desc())
        )
        rows = result.scalars().all()
    return [_incident_to_dict(row) for row in rows]


async def get_active_incidents() -> list[dict]:
    """Whitelisted, system-wide (no arguments at all) — Incident Severity
    Agent's own tool (§3 roster #5), deliberately independent of any one
    customer's region: a live, currently-active picture to cross-reference
    against the query's own described symptoms."""
    async with async_session_maker() as db:
        result = await db.execute(
            select(IncidentLog).where(IncidentLog.end_time.is_(None)).order_by(IncidentLog.start_time.desc())
        )
        rows = result.scalars().all()
    return [_incident_to_dict(row) for row in rows]
