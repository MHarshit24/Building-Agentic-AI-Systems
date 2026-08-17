"""
tests/unit/test_sql_tools_whitelist.py

L1 tests (§19 — pure logic, no LLM) proving §24.3's "SQL injection via
natural language: structurally impossible" claim empirically, not just
asserting it. Two layers:

  1. Signature inspection (fast, no DB): every whitelisted function's
     parameters are int-typed — no str parameter exists anywhere that
     could carry a WHERE-clause fragment.
  2. Empirical attack-payload tests (against the real disposable test DB,
     via conftest.py's make_customer/make_ticket/make_incident fixtures):
     call each function with classic injection-shaped strings as the
     customer_id argument, and assert (a) the call is safely rejected
     (queries.py's own _require_int guard, not a driver-behavior guess)
     and (b) the customers table's row count is unchanged afterward —
     proving no DDL/DML from the payload ever executed, not just that
     the function "handled" the bad input gracefully.
"""

from __future__ import annotations

import typing
from datetime import datetime

import pytest
from sqlalchemy import func, select

from app.db.models import Customer
from app.db.session import async_session_maker
from app.sql_tools.queries import get_active_incidents, get_customer, get_incidents, get_tickets

INJECTION_PAYLOADS = [
    "1 OR 1=1",
    "1; DROP TABLE customers; --",
    "1 UNION SELECT * FROM users",
    "' OR '1'='1",
]


async def _customer_count() -> int:
    async with async_session_maker() as db:
        result = await db.execute(select(func.count()).select_from(Customer))
        return result.scalar_one()


class TestSignaturesAreIntOnly:
    @pytest.mark.parametrize("fn", [get_customer, get_tickets, get_incidents])
    def test_customer_id_parameter_is_int_typed(self, fn):
        hints = typing.get_type_hints(fn)
        assert hints["customer_id"] is int

    def test_get_active_incidents_takes_no_arguments(self):
        import inspect

        sig = inspect.signature(get_active_incidents)
        assert list(sig.parameters) == []


class TestInjectionPayloadsAreRejected:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("fn", [get_customer, get_tickets, get_incidents])
    @pytest.mark.parametrize("payload", INJECTION_PAYLOADS)
    async def test_string_payload_raises_before_any_query_runs(self, fn, payload):
        count_before = await _customer_count()

        with pytest.raises(TypeError):
            await fn(payload)

        count_after = await _customer_count()
        assert count_after == count_before, (
            "customers row count changed after an injection-payload attempt — "
            "something executed against the database that shouldn't have"
        )


class TestWhitelistedFunctionsWorkCorrectly:
    """Not just safe — actually correct, so the whitelist isn't a security
    theater that happens to also be useless."""

    @pytest.mark.asyncio
    async def test_get_customer_returns_the_seeded_row(self, make_customer):
        customer = await make_customer(company_name="Acme Corp", region="us-west")

        result = await get_customer(customer.customer_id)

        assert result is not None
        assert result["customer_id"] == customer.customer_id
        assert result["company_name"] == "Acme Corp"
        assert result["_source_table"] == "customers"
        assert result["_record_id"] == customer.customer_id

    @pytest.mark.asyncio
    async def test_get_customer_nonexistent_id_returns_none(self):
        result = await get_customer(999_999_999)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_tickets_returns_only_this_customers_tickets(self, make_customer, make_ticket):
        customer_a = await make_customer()
        customer_b = await make_customer()
        await make_ticket(customer_a.customer_id, issue_category="billing")
        await make_ticket(customer_b.customer_id, issue_category="integration")

        result = await get_tickets(customer_a.customer_id)

        assert len(result) == 1
        assert result[0]["customer_id"] == customer_a.customer_id
        assert result[0]["issue_category"] == "billing"
        assert result[0]["_source_table"] == "support_tickets"

    @pytest.mark.asyncio
    async def test_get_incidents_matches_by_region_not_customer_id(self, make_customer, make_incident):
        customer = await make_customer(region="eu-central")
        matching = await make_incident(affected_region="eu-central", end_time=None)
        await make_incident(affected_region="ap-south", end_time=None)  # different region, must not match

        result = await get_incidents(customer.customer_id)

        assert len(result) == 1
        assert result[0]["incident_id"] == matching.incident_id
        assert result[0]["affected_region"] == "eu-central"
        assert result[0]["_source_table"] == "incident_logs"

    @pytest.mark.asyncio
    async def test_get_incidents_excludes_resolved_incidents(self, make_customer, make_incident):
        customer = await make_customer(region="ca-central")
        # IncidentLog.start_time/end_time are TIMESTAMP WITHOUT TIME ZONE
        # (naive) columns — a tz-aware datetime here raises asyncpg.DataError.
        await make_incident(affected_region="ca-central", end_time=datetime.now())

        result = await get_incidents(customer.customer_id)

        assert result == []

    @pytest.mark.asyncio
    async def test_get_active_incidents_is_not_region_scoped(self, make_customer, make_incident):
        await make_incident(affected_region="sa-east", end_time=None)
        await make_incident(affected_region="af-south", end_time=None)

        result = await get_active_incidents()

        regions = {r["affected_region"] for r in result}
        assert "sa-east" in regions
        assert "af-south" in regions
