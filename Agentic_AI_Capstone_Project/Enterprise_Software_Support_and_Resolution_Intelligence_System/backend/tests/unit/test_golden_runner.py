"""
tests/unit/test_golden_runner.py

Regression coverage for a real, confirmed bug fix: golden_50.json is
strictly block-ordered by category (Documentation x15, then SQL x10,
Hybrid x10, High-Severity x10, Escalation x5 — confirmed by reading the
file directly), and load_golden_queries(sample=N) used to slice the
first N entries in file order. Since --sample is this project's own
permanent operating mode (5-10, per groq_judge_client.py's real
feasibility analysis) and the calibration minimum is 10 (calibrate_
thresholds.py's _MIN_CALIBRATION_SAMPLE_SIZE), EVERY realistic --sample
run drew exclusively from the Documentation block — incident_severity_
node, the SQL path, the Hybrid path, and the Escalation path never got
exercised at any sample size this project actually uses. Fixed with
_stratified_sample(), tested here both against real golden_50.json (the
directly-representative case) and against small synthetic data (to pin
down the exact allocation behavior without depending on the real file's
current contents).
"""

from __future__ import annotations

from evaluation import golden_runner
from evaluation.golden_runner import _stratified_sample, load_golden_queries


def test_sample_10_against_the_real_golden_set_includes_a_non_documentation_query():
    """The directly-representative regression test: --sample 10 against
    the REAL golden_50.json (not synthetic data) must include at least
    one query whose type isn't Documentation — proving the fix actually
    works against the file this project evaluates against, not just an
    idealized synthetic scenario."""
    sampled = load_golden_queries(sample=10)

    assert len(sampled) == 10
    query_types = {q["query_type"] for q in sampled}
    assert query_types != {"Documentation"}, (
        f"--sample 10 only drew from {query_types} — the exact bug this fix addresses"
    )
    assert len(query_types) > 1


def test_sample_1_still_returns_exactly_the_first_documentation_entry():
    """Backward-compatibility check: --sample 1 must still return gq_001
    alone, unchanged from the pre-fix behavior — this is the exact query
    this project's first real judge-model test already ran against, and
    the fix shouldn't silently change that specific, already-exercised
    case."""
    sampled = load_golden_queries(sample=1)

    assert len(sampled) == 1
    assert sampled[0]["id"] == "gq_001"
    assert sampled[0]["query_type"] == "Documentation"


def test_sample_covering_all_five_real_categories_includes_every_one():
    """--sample 10 (the calibration minimum) against the real golden set
    should cover every category present, not just avoid being 100%
    Documentation — a stronger claim than the "not all Documentation"
    test above."""
    sampled = load_golden_queries(sample=10)
    query_types = {q["query_type"] for q in sampled}

    assert query_types == {"Documentation", "SQL", "Hybrid", "High-Severity", "Escalation"}


def test_stratified_sample_guarantees_at_least_one_per_category_on_synthetic_data():
    """Pins down the exact allocation behavior against small, known
    synthetic data (3 categories, sizes 6/3/1) rather than depending on
    golden_50.json's current real counts — proves every category gets a
    slot, proportionally weighted toward the larger ones, once every
    category has its guaranteed minimum."""
    queries = (
        [{"id": f"a{i}", "query_type": "A"} for i in range(6)]
        + [{"id": f"b{i}", "query_type": "B"} for i in range(3)]
        + [{"id": f"c{i}", "query_type": "C"} for i in range(1)]
    )

    sampled = _stratified_sample(queries, sample=5)

    assert len(sampled) == 5
    by_type = {}
    for q in sampled:
        by_type[q["query_type"]] = by_type.get(q["query_type"], 0) + 1
    assert by_type.get("C", 0) == 1  # only 1 exists, gets its guaranteed slot
    assert by_type.get("B", 0) >= 1
    assert by_type.get("A", 0) >= 1
    assert by_type["A"] >= by_type["B"] >= by_type["C"]  # proportional to real size


def test_stratified_sample_with_fewer_slots_than_categories_covers_as_many_as_fit():
    """When sample < number of categories, one slot goes to as many
    categories as fit, in file order — rather than, say, crashing or
    returning an empty/malformed result."""
    queries = (
        [{"id": "a0", "query_type": "A"}]
        + [{"id": "b0", "query_type": "B"}]
        + [{"id": "c0", "query_type": "C"}]
        + [{"id": "d0", "query_type": "D"}]
    )

    sampled = _stratified_sample(queries, sample=2)

    assert len(sampled) == 2
    assert {q["query_type"] for q in sampled} == {"A", "B"}


def test_stratified_sample_returns_everything_when_sample_meets_or_exceeds_total():
    queries = [{"id": "a0", "query_type": "A"}, {"id": "b0", "query_type": "B"}]

    assert _stratified_sample(queries, sample=2) == queries
    assert _stratified_sample(queries, sample=5) == queries


def test_load_golden_queries_without_sample_returns_all_fifty_in_file_order():
    """No `sample` argument still returns everything, unstratified, in
    original file order — a full run isn't affected by this fix at all."""
    all_queries = golden_runner.load_golden_queries()

    assert len(all_queries) == 50
    assert all_queries[0]["id"] == "gq_001"
