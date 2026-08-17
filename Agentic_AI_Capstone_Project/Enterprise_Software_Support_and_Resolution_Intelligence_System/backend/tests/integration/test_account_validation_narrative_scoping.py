"""
tests/integration/test_account_validation_narrative_scoping.py

Regression coverage for a real bug found via manual frontend QA:
account_validation_node's narrative unconditionally padded every answer
with a summary of the customer's other tickets and region-wide incidents,
even when the query asked a narrow, single-fact question (e.g. "what is
this customer's account status and subscription tier?"). Confirmed
directly against real Beta Systems/Gamma Retail account-status queries —
the real answer always appended unrelated ticket/incident detail ("There
are multiple ongoing incidents affecting your region...") the query never
asked for, consistent with the low context_precision (77%) already
measured in this project's own eval.

account_validation_v1.py's own FEW_SHOT already had an Example 3
demonstrating narrow scoping, but only for a case with ZERO ticket data
available at all — it never demonstrated the harder case (real ticket AND
incident data present, but irrelevant to a narrow query). ROLE_
INSTRUCTIONS was strengthened with an explicit "real data being available
doesn't mean it belongs in the narrative" rule, and a new Example 1b
demonstrates exactly that harder case, contrasted against Example 1
(now given an explicit broad/open-ended query to justify ITS full-detail
narrative, removing the ambiguity that made "summarize everything" look
like the default instead of the exception).

Uses this suite's own make_customer/make_ticket/make_incident fixtures
(tests/conftest.py) to seed a real customer + a real, unrelated ticket +
a real, region-matching incident directly in the disposable per-session
test database — NOT the real seeded dev customer_id 1/Alpha Corp this bug
was originally found against manually: the test DB starts empty each
session, so a hardcoded customer_id=1 here would hit get_customer()
returning None ("I don't have an account on file...") and never actually
exercise the narrative-scoping prompt at all (confirmed by running
exactly that version of this test first — it failed with that generic
no-account message, not a narrative-scoping assertion failure, which is
what caught this gap). A narrow account-status query against a customer
whose only real ticket/incident are unambiguously about a different topic
gives a clean, checkable signal: the real narrative must not mention
"ticket" OR "incident" if the fix holds.

A real, second bug in this exact test file's own first version, caught by
live manual QA (not by this test — the gap this update closes): the
original version of this test only seeded a ticket, never an incident.
get_incidents() returns real, non-empty data for almost any customer with
a region on file, so the incident-padding half of the kitchen-sink bug
("Separately, there are multiple ongoing incidents affecting your
region...") was never exercised here at all, even though it was — and
still partly is — the more persistent half of the real bug in production.

Real, live Azure calls every run — same eval-tier convention as this
project's other prompt-behavior regression tests.
"""

from __future__ import annotations

import os

import pytest

from app.config import get_settings

pytestmark = pytest.mark.eval


@pytest.fixture(scope="module", autouse=True)
def _use_real_llm_provider():
    original_env = os.environ.get("LLM_PROVIDER")
    os.environ["LLM_PROVIDER"] = "azure"
    get_settings.cache_clear()

    yield

    if original_env is None:
        os.environ.pop("LLM_PROVIDER", None)
    else:
        os.environ["LLM_PROVIDER"] = original_env
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_narrow_account_query_does_not_pad_narrative_with_unrelated_tickets(
    make_customer, make_ticket, make_incident
):
    from app.orchestration.nodes.account_validation import account_validation_node

    customer = await make_customer(
        subscription_tier="Enterprise", account_status="Active", sla_level="Priority", region="apac-test"
    )
    await make_ticket(customer.customer_id, issue_category="Integration", severity_level="High", ticket_status="Open")
    # Region-matched, unresolved (end_time defaults to None) — exactly the
    # shape get_incidents(customer.customer_id) will return for real.
    await make_incident(incident_type="outage", severity="Critical", affected_region="apac-test")

    state = {
        "query": "What is this customer's current account status and subscription tier?",
        "chat_history": [],
        "customer_id": customer.customer_id,
        "retrieval_mode": "SQL",
    }

    result = await account_validation_node(state)
    narrative = result["account_narrative"].lower()

    assert "enterprise" in narrative and "active" in narrative, (
        f"expected the actual asked-for facts (Enterprise tier, Active status) to be present: "
        f"{result['account_narrative']!r}"
    )
    assert "ticket" not in narrative, (
        f"narrative padded with unrelated ticket detail the query never asked about: "
        f"{result['account_narrative']!r}"
    )
    assert "incident" not in narrative, (
        f"narrative padded with an unrelated regional-incident mention the query never asked "
        f"about — the real, persistent half of the kitchen-sink bug: {result['account_narrative']!r}"
    )


@pytest.mark.asyncio
async def test_broad_account_summary_query_still_includes_tickets(make_customer, make_ticket, make_incident):
    """Contrast case, same shape: an explicitly broad/open-ended query
    should still get the fuller picture — confirms the narrow-scoping fix
    didn't overcorrect into omitting real, relevant data when it WAS asked
    for."""
    from app.orchestration.nodes.account_validation import account_validation_node

    customer = await make_customer(
        subscription_tier="Enterprise", account_status="Active", sla_level="Priority", region="apac-test"
    )
    await make_ticket(customer.customer_id, issue_category="Integration", severity_level="High", ticket_status="Open")
    await make_incident(incident_type="outage", severity="Critical", affected_region="apac-test")

    state = {
        "query": "Give me a general summary of this customer's account, including any open tickets.",
        "chat_history": [],
        "customer_id": customer.customer_id,
        "retrieval_mode": "SQL",
    }

    result = await account_validation_node(state)
    narrative = result["account_narrative"].lower()

    assert "ticket" in narrative, (
        f"expected ticket detail to be included for an explicitly broad account-summary "
        f"request: {result['account_narrative']!r}"
    )
