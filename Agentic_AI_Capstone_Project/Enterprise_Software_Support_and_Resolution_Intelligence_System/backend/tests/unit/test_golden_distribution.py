"""
tests/unit/test_golden_distribution.py

L1 pure-logic test (§19) — no LLM, no DB, no I/O beyond reading the JSON
file itself. Guards golden_queries/golden_50.json against silently drifting
out of the course-mandated shape (§24.4 / capstone_software_support_dataset.md
Part 3): the exact 15/10/10/10/5 category distribution, and all four
mandatory per-query labels present and within their allowed value sets on
every single entry — so a mislabeled or miscounted golden set fails here
immediately, rather than silently skewing every downstream SLO that reads
those labels (query-routing accuracy, risk-classification accuracy,
escalation recall, §24.4).
"""

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

_GOLDEN_PATH = Path(__file__).resolve().parents[2] / "golden_queries" / "golden_50.json"

# §24.4's required distribution — exactly 50, split across the 5 course
# categories this way. Not derived from the file itself, since the whole
# point is to catch the file drifting away from this fixed target.
_EXPECTED_DISTRIBUTION = {
    "Documentation": 15,
    "SQL": 10,
    "Hybrid": 10,
    "High-Severity": 10,
    "Escalation": 5,
}

# §24.4's four mandatory labels and their allowed value sets.
_VALID_RISK_LEVELS = {"Low", "Medium", "High", "Critical"}
_VALID_RETRIEVAL_MODES = {"RAG", "SQL", "Hybrid", "Critical"}
_VALID_ESCALATION = {"Yes", "No"}


def _load_queries() -> list[dict]:
    with open(_GOLDEN_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data["queries"]


def test_golden_file_contains_exactly_50_queries():
    assert len(_load_queries()) == 50


def test_golden_query_ids_are_unique():
    ids = [q["id"] for q in _load_queries()]
    assert len(ids) == len(set(ids))


def test_golden_distribution_matches_mandated_15_10_10_10_5():
    counts = Counter(q["query_type"] for q in _load_queries())
    assert dict(counts) == _EXPECTED_DISTRIBUTION


def test_every_query_has_all_four_mandatory_labels_populated():
    required = ["query_type", "risk_level", "expected_retrieval_mode", "expected_escalation"]
    for q in _load_queries():
        for field in required:
            assert field in q, f"{q.get('id')} missing required label {field!r}"
            assert q[field], f"{q.get('id')} has empty required label {field!r}"


def test_every_query_type_is_one_of_the_five_mandated_categories():
    for q in _load_queries():
        assert q["query_type"] in _EXPECTED_DISTRIBUTION, f"{q['id']} has unrecognized query_type {q['query_type']!r}"


def test_every_risk_level_is_within_allowed_values():
    for q in _load_queries():
        assert q["risk_level"] in _VALID_RISK_LEVELS, f"{q['id']} has invalid risk_level {q['risk_level']!r}"


def test_every_expected_retrieval_mode_is_within_allowed_values():
    for q in _load_queries():
        assert q["expected_retrieval_mode"] in _VALID_RETRIEVAL_MODES, (
            f"{q['id']} has invalid expected_retrieval_mode {q['expected_retrieval_mode']!r}"
        )


def test_every_expected_escalation_is_yes_or_no():
    for q in _load_queries():
        assert q["expected_escalation"] in _VALID_ESCALATION, (
            f"{q['id']} has invalid expected_escalation {q['expected_escalation']!r}"
        )


def test_all_escalation_category_queries_expect_escalation_yes():
    # §24.4: the 5 Escalation-Scenarios queries are labeled by
    # Expected Escalation: Yes first and foremost — escalation is the
    # whole point of this category, not a mixed outcome.
    for q in _load_queries():
        if q["query_type"] == "Escalation":
            assert q["expected_escalation"] == "Yes", f"{q['id']} is Escalation category but not expected_escalation=Yes"


def test_every_query_has_query_text_and_ground_truth_answer():
    for q in _load_queries():
        assert q.get("query"), f"{q['id']} missing query text"
        assert q.get("ground_truth_answer"), f"{q['id']} missing ground_truth_answer"
        assert q.get("expected_sources"), f"{q['id']} missing expected_sources"


def test_all_eight_mandatory_high_risk_scenarios_are_represented():
    # README.md's "High-Risk Scenario Examples" — 8 mandatory scenarios
    # that must appear somewhere across the 50 queries (tagged via the
    # optional high_risk_scenario field where applicable).
    mandatory_scenarios = {
        "Production outage affecting premium customers",
        "Security vulnerability exposure in deployed API",
        "Subscription downgrade impacting active integrations",
        "Account suspension due to payment failure during incident",
        "Data loss complaint without supporting logs",
        "Multiple tickets indicating systemic failure pattern",
        "Incident log shows unresolved critical alert",
        "Conflicting documentation guidance across versions",
    }
    present = {q["high_risk_scenario"] for q in _load_queries() if q.get("high_risk_scenario")}
    missing = mandatory_scenarios - present
    assert not missing, f"missing mandatory high-risk scenarios: {missing}"
