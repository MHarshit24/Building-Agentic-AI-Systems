"""
tests/integration/test_incident_severity_relevance.py

Regression coverage for the REAL root cause of a severity over-triggering
bug this session initially (incorrectly) attributed to classify_v1.py.
classify_node's own severity_initial was verified reliable (10/10 real
Azure calls resolved Medium for the exact failing live query, both with
empty history and with the full real accumulated conversation history —
ruling out conversation-history bleed as the cause). The live "Critical"
result was traced to a completely different node: incident_severity_node,
which runs for every category="incident"/"security" query and reassesses
severity_final using get_active_incidents() — a SYSTEM-WIDE, region-
UNSCOPED tool (sql_tools/queries.py's own docstring: "deliberately NOT
region/customer-scoped at all").

With real seeded volume (~50 synthetic + 2 starter incidents), that list
is almost never empty and almost always contains a genuine Critical
incident somewhere in the system — entirely unrelated to whatever the
current query is actually about. incident_severity_v1.py's own original
Example 1 taught exactly this flawed pattern: a generic query + any
active incident's mere existence = raise to Critical, with no requirement
that the incident actually relate to what the query describes. Confirmed
directly against the real live failure: a Gamma Retail (APAC) customer
asking about a nonexistent "EU outage incident" still got severity_final
=Critical, because SOME unrelated real Critical incident (elsewhere,
wrong region) existed in the system-wide active list.

Fixed by requiring genuine relevance in ROLE_INSTRUCTIONS (a specific
active incident's own type/region/description must actually correspond
to what the query names or describes — not mere co-occurrence) and
replacing Example 1 with a genuinely-matching case, plus a new Example 3
demonstrating unrelated active incidents correctly NOT raising severity.

Real, live Azure calls — same eval-tier convention as this project's
other prompt-behavior regression tests. Seeds a real, unrelated Critical
incident via make_incident (a different region from the query) so the
"active incidents exist but don't match" scenario is genuinely exercised,
not assumed empty.
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
async def test_unrelated_active_incident_does_not_raise_severity(make_incident):
    from app.orchestration.nodes.incident_severity import incident_severity_node

    # A real, genuinely active, genuinely Critical incident — but in a
    # different region, unrelated to the query below. Its mere existence
    # in the system-wide active-incidents list must not raise severity.
    await make_incident(incident_type="data_loss", severity="Critical", affected_region="test-region-unrelated")

    state = {
        "query": "What is the resolution status of the EU outage incident?",
        "chat_history": [],
        "severity_initial": "Medium",
        "sql_results": [],  # this customer's own region has no matching incident on file either
    }

    result = await incident_severity_node(state)

    assert result["severity_final"] != "Critical", (
        f"expected severity_final to stay at (or near) the initial Medium estimate — no active "
        f"incident actually relates to an EU outage — got {result['severity_final']!r}. An "
        f"unrelated Critical incident existing elsewhere in the system must not raise severity "
        f"for a query about something else entirely."
    )


@pytest.mark.asyncio
async def test_genuinely_matching_active_incident_still_raises_severity(make_incident):
    """Contrast case: confirms the relevance-scoping fix didn't overcorrect
    into ignoring real, genuinely-matching evidence."""
    from app.orchestration.nodes.incident_severity import incident_severity_node

    await make_incident(incident_type="outage", severity="Critical", affected_region="test-region-matching")

    state = {
        "query": "Our test-region-matching service just went down — is this a known outage?",
        "chat_history": [],
        "severity_initial": "High",
        "sql_results": [],
    }

    result = await incident_severity_node(state)

    assert result["severity_final"] == "Critical", (
        f"expected severity_final=Critical — a genuinely matching active outage exists for the "
        f"exact region/symptom the query describes — got {result['severity_final']!r}."
    )
