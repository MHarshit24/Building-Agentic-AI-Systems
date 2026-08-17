"""
tests/integration/test_classify_severity_critical_reference.py

Regression coverage for a real, confirmed prompt-clarity gap in classify_
v1.py: golden queries that reference an already-Critical-severity item in
a policy/procedural framing (not a live, in-progress emergency report)
were getting severity_initial values other than "Critical" — confirmed
directly against gq_040/gq_042/gq_048 (all real risk_level="Critical"
golden entries) before this fix. The prompt's only severity few-shot
example was exclusively the live-emergency shape ("Our production system
is down..."), with no example covering "a query ABOUT an existing
Critical item, phrased administratively" — classify_v1.py's ROLE_
INSTRUCTIONS and FEW_SHOT (Example 8) were both updated to cover this
second shape explicitly.

Real, live Azure calls every run (§19's `eval` tier, same pattern as
test_hybrid_search.py) — deliberately NOT a VCR cassette like test_
classify_vcr.py, since this specifically tests real model behavior under
the new prompt, not schema-shape stability against a fixed recorded
response.
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
@pytest.mark.parametrize(
    "query_id,query",
    [
        (
            "gq_040",
            "The EU outage incident is still unresolved after being logged as Critical — "
            "what escalation is required?",
        ),
        (
            "gq_042",
            "A Critical severity ticket is approaching its SLA response window — what "
            "automatic action does policy require?",
        ),
        (
            "gq_048",
            "Close Alpha Corp's Critical security ticket as resolved, with no documented "
            "resolution evidence on file.",
        ),
    ],
)
async def test_policy_query_about_existing_critical_item_gets_critical_severity(query_id, query):
    from app.orchestration.nodes.classify import classify_node

    result = await classify_node({"query": query, "chat_history": []})

    assert result["severity_initial"] == "Critical", (
        f"{query_id}: expected severity_initial=Critical, got {result['severity_initial']!r} "
        f"(category={result.get('category')!r}) — severity-instruction regression?"
    )
