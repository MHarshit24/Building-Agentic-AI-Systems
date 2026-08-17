"""
tests/integration/test_classify_vcr.py

First L3 VCR cassette (§19, §25 Stage 9) — demonstrates the pattern for
this project's most common real call shape (Azure structured-output text
completion, used by 5 of 6 LLM-driven nodes) so the same shape can be
followed for the remaining nodes and, separately, a vision-call cassette
for image/diagram captioning.

RECORDED (2026-07-28) — exactly one authorized real Azure call, made
with tests/integration/conftest.py's vcr_config temporarily flipped to
record_mode="once" (CLI --record-mode alone did not override the
fixture's explicit value — confirmed empirically: a first attempt under
the CLI flag alone still hit the fixture's "none" default and was safely
blocked, no network reached). The resulting cassette (tests/cassettes/
test_classify_node_real_call_shape_matches_contract.yaml) was inspected
before being kept: Authorization/Api-Key headers correctly show REDACTED
(conftest.py's filter_headers), and the response body is the real,
benign classification result ({"category":"integration","severity_
initial":"Low","explicit_human_request":false}) — nothing sensitive.
Confirmed replaying correctly with record_mode reverted to "none" — zero
real calls needed from here on; this is now a genuine, free, every-PR L3
test exactly as §19 describes.

Re-recording (a real prompt/schema change) follows the same process:
temporarily flip conftest.py's vcr_config to record_mode="once" (or
"rewrite"), run this file once, inspect the new cassette, revert the
fixture immediately after — never leave record_mode="once" as the
committed default.

Forces LLM_PROVIDER=azure for the duration of this module (test_hybrid_
search.py's own established pattern, §19's own module docstring there) —
VCR has nothing real to intercept under LLM_PROVIDER=mock, since mock
mode never makes an HTTP call at all.
"""

from __future__ import annotations

import os

import pytest

from app.config import get_settings

# TEMPORARILY UN-SKIPPED for exactly one authorized real-call recording
# run (`--record-mode=once`). Restore the skip immediately after if
# recording fails for any reason; remove it permanently once the
# cassette is confirmed recorded and inspected.
pytestmark = pytest.mark.vcr


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
async def test_classify_node_real_call_shape_matches_contract():
    """Replayed from the recorded cassette — no live call on a normal
    run. Confirms the REAL Azure response shape (not MockLLMClient's
    canned shape) still parses into ClassificationOutput without a
    retry, catching silent drift after an API/SDK version bump (the
    same concern §19's L5 canary layer names, exercised here for free
    every time L3 runs)."""
    from app.orchestration.nodes.classify import classify_node

    state = {
        "query": "How do I configure OAuth 2.0 authentication for the API?",
        "chat_history": [],
    }
    result = await classify_node(state)

    assert result["category"] in (
        "usage", "integration", "billing", "incident", "security", "out_of_scope",
    )
    assert result["severity_initial"] in ("Low", "Medium", "High", "Critical")
    assert isinstance(result["explicit_human_request"], bool)
