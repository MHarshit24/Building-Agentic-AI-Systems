"""
tests/integration/test_classify_severity_not_over_triggered.py

Regression coverage for a real bug found this session (manual QA of a
full-50-query recalibration + live frontend testing), the flip side of
test_classify_severity_critical_reference.py's fix: gq_009, gq_011, and
gq_022 (all real golden_50.json entries with risk_level="Medium"/"High",
expected_escalation="No") were resolving severity_initial="Critical" and
auto-escalating even though none of them describe a live emergency or ask
what response/action a specific Critical item requires — they're either a
general policy question about the Critical severity TIER as a concept (no
specific item), or a plain status/information check on a named incident.

Widening classify_v1.py's rule (b) to cover "policy question about an
already-Critical item" (the earlier fix, above) apparently widened the net
too far — these three got swept in. ROLE_INSTRUCTIONS' rule (b) and
FEW_SHOT (Examples 9/10) were updated to carve both shapes back out
explicitly, without touching rule (b)'s original intent (still verified
by test_classify_severity_critical_reference.py's three cases, which this
file does not duplicate or replace — both should be run together to
confirm the carve-out didn't regress the original fix).

Real, live Azure calls every run — same eval-tier convention as the
sibling file this one deliberately mirrors.
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
            "gq_009",
            "What are the patch deployment timelines for a Critical severity security "
            "vulnerability?",
        ),
        (
            "gq_011",
            "What is the process for responsibly disclosing a discovered security "
            "vulnerability?",
        ),
        (
            "gq_022",
            "What is the resolution status of the EU outage incident?",
        ),
        (
            "gq_022b",
            "How long has the active security breach been ongoing, and has a root cause been "
            "identified yet?",
        ),
    ],
)
async def test_generic_or_status_query_does_not_over_trigger_critical(query_id, query):
    """gq_022b is a synthetic, not a real golden_50.json id — added to
    verify the carve-out generalizes past gq_022's own exact wording (see
    classify_v1.py's Example 11), not just pattern-matching one sentence.
    A live frontend re-test of gq_022's own exact text still showed
    Critical once after this fix (see this module's docstring) — real,
    acknowledged sampling non-determinism, not a claim this test makes
    the behavior deterministic; it confirms the fix measurably improves
    the odds, run repeatedly if you need a real hit-rate estimate."""
    from app.orchestration.nodes.classify import classify_node

    result = await classify_node({"query": query, "chat_history": []})

    assert result["severity_initial"] != "Critical", (
        f"{query_id}: expected severity_initial != Critical (golden risk_level is Medium/High, "
        f"expected_escalation=No) — got Critical (category={result.get('category')!r}). "
        f"This query is a generic policy/status question, not a live emergency or a request "
        f"about a specific Critical item's required action."
    )
