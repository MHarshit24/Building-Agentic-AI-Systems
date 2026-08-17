"""
tests/integration/test_compute_correctness_scoping.py

Regression coverage for a real, confirmed judge-prompt bug in evaluation/
calibrate_thresholds.py's compute_correctness(): fact extraction pulled
EVERY factual claim out of golden_50.json's ground_truth_answer, including
tangential context the query itself never asked about, then failed the
whole query if any one of those extra facts wasn't mentioned in an
otherwise fully correct, well-scoped real answer.

Confirmed directly against two real examples from this project's own
full-50-query golden run, both of which scored faithfulness=1.0 (nothing
hallucinated) yet correct=False under the OLD prompt:
  - gq_007: ground_truth_answer states the Free tier's rate limits; the
    real answer states them correctly and completely.
  - gq_013: the query asks only about PostgreSQL/Redis versions;
    ground_truth_answer also names Node.js/Python versions as surrounding
    context the query never asked for; the real answer correctly answers
    only what was asked.

A SECOND real bug was found running this exact test file for real (not
by inspection): gq_013's ground truth states "PostgreSQL 14.x or 15.x" —
a disjunction, either version satisfies the requirement. The original
prompt split this into two independent facts ("14.x is required", "15.x
is required"), and even after the scoping fix above, the real answer
(which correctly states "14.x or 15.x") still failed — the isolated
verification call for "15.x is required" correctly says no, since the
answer doesn't claim 15.x is *the* requirement, only that it's *a* valid
option. compute_correctness()'s extraction prompt now keeps a stated
alternative as ONE atomic fact instead of splitting it — see its own
docstring for the real evidence (a zero-cost scan of golden_50.json
found ~4-8 of 50 entries share this shape, not a one-off).

These tests call the REAL Groq judge (not a mock) with the exact real
query/ground_truth_answer/final_answer triples captured from real runs —
proving the FIXED prompts actually change model behavior, not just that
the code wires a mock's canned response through correctly. `eval`-marked
(real, costed Groq calls), same tier as test_classify_severity_critical_
reference.py.
"""

from __future__ import annotations

import pytest

from evaluation.calibrate_thresholds import compute_correctness
from evaluation import groq_judge_client as judge_client_module

pytestmark = pytest.mark.eval


@pytest.mark.asyncio
async def test_gq007_well_scoped_correct_answer_is_no_longer_penalized():
    query = "What is the API rate limit for the Free tier?"
    ground_truth_answer = "60 requests/minute, 10,000 requests/day, with a burst limit of 100 requests per 10 seconds."
    final_answer = (
        "For the Free tier the API rate limits are: 60 requests per minute, a daily quota "
        "of 10,000 requests, and a burst limit of 100 requests per 10 seconds. In terms of "
        "throughput/capacity, Free tier is limited to about 5 requests/second, up to 10 "
        "concurrent connections, and a 1 MB payload limit."
    )

    audit = await compute_correctness(query, ground_truth_answer, final_answer, judge=judge_client_module)

    assert audit.correct is True, (
        f"expected correct=True for a well-scoped, factually accurate answer, got False. "
        f"extracted_facts={audit.extracted_facts!r} fact_verdicts={audit.fact_verdicts!r}"
    )


@pytest.mark.asyncio
async def test_gq013_answer_not_penalized_for_omitting_facts_the_query_never_asked():
    """Also the disjunction-splitting regression test — gq_013's own
    ground truth ("PostgreSQL 14.x or 15.x") is the real example that
    exposed that second bug. See module docstring for the full history."""
    query = "What PostgreSQL and Redis versions are required for product version 3.5.x?"
    ground_truth_answer = (
        "PostgreSQL 14.x or 15.x, and Redis 7.0+ (alongside Node.js 18.x and Python "
        "3.10/3.11), per the version compatibility matrix."
    )
    final_answer = (
        "For ERIS version 3.5.x the required PostgreSQL versions are 14.x or 15.x, and the "
        "required Redis version is 7.0 or newer."
    )

    audit = await compute_correctness(query, ground_truth_answer, final_answer, judge=judge_client_module)

    assert audit.correct is True, (
        f"expected correct=True — the answer correctly addresses only what the query asked "
        f"(PostgreSQL/Redis), states the full '14.x or 15.x' alternative, and should not be "
        f"penalized for omitting Node.js/Python versions the query never requested, nor for "
        f"not separately re-asserting each PostgreSQL version as its own independent "
        f"requirement. extracted_facts={audit.extracted_facts!r} fact_verdicts={audit.fact_verdicts!r}"
    )
    extracted_lower = " ".join(audit.extracted_facts).lower()
    assert "node" not in extracted_lower and "python" not in extracted_lower, (
        f"extraction should be scoped to the query (PostgreSQL/Redis), not pull in "
        f"tangential Node.js/Python facts the query never asked about: {audit.extracted_facts!r}"
    )
    postgres_facts = [f for f in audit.extracted_facts if "postgres" in f.lower()]
    assert len(postgres_facts) <= 1, (
        f"the '14.x or 15.x' alternative should be kept as ONE atomic fact, not split into "
        f"separate independently-required facts per version: {audit.extracted_facts!r}"
    )
