"""
tests/unit/test_calibrate_thresholds_severity.py

Regression coverage for a real, confirmed bug fix: evaluation/
calibrate_thresholds.py's run_calibration() used to compare raw
severity_final against golden_50.json's risk_level, which is wrong on
any query where incident_severity_node correctly didn't run (§3:
conditional on incident/security category or Critical mode) — the
majority of any real run, not an edge case. severity_final is None by
design in that case; the fix resolves through app.orchestration.nodes.
router.resolve_effective_severity() instead, matching every other place
in this codebase that needs "the system's actual severity assessment"
(graph.py's post-reflect edge, escalate_node, respond_node's
flagged_for_review — none of them read severity_final raw either).

This is a pure unit test: golden_runner, compute_correctness, and
ragas_metrics.score_query are monkeypatched to fixed, controlled values
(no real graph run, no real judge call) so the test isolates exactly the
comparison logic being fixed, using the same scenario the first real
--sample 1 run against gq_001 actually hit: category="integration"
(non-incident/security), so severity_final stays None while
severity_initial correctly matches the golden risk_level.
"""

from __future__ import annotations

import pytest

import evaluation.calibrate_thresholds as calibrate_thresholds_module
from evaluation.calibrate_thresholds import run_calibration


def _fake_query_entry(risk_level: str) -> dict:
    return {
        "id": "test_q",
        "query": "How do I configure X?",
        "query_type": "Documentation",
        "risk_level": risk_level,
        "expected_retrieval_mode": "RAG",
        "expected_escalation": "No",
        "ground_truth_answer": "Do X.",
        "expected_sources": [],
    }


def _fake_graph_result(*, severity_final: str | None, severity_initial: str | None) -> dict:
    return {
        "final_answer": "Do X.",
        "confidence_score": 0.9,
        "retrieval_mode": "RAG",
        "severity_final": severity_final,
        "severity_initial": severity_initial,
        "escalation_flag": False,
        "retrieved_chunks": [],
        "retrieved_tables": [],
        "retrieved_diagrams": [],
        "sql_results": [],
    }


_FAKE_RAGAS_SCORES = {"faithfulness": 1.0, "answer_relevance": 1.0, "context_precision": 1.0, "context_recall": 1.0}


async def _async_return(value):
    return value


def _patch_pipeline(monkeypatch, query_entry: dict, graph_result: dict) -> None:
    monkeypatch.setattr(calibrate_thresholds_module.golden_runner, "load_golden_queries", lambda sample: [query_entry])
    monkeypatch.setattr(
        calibrate_thresholds_module.golden_runner,
        "run_golden_query_through_graph",
        lambda entry: _async_return(graph_result),
    )
    monkeypatch.setattr(
        calibrate_thresholds_module,
        "compute_correctness",
        lambda *a, **k: _async_return(
            calibrate_thresholds_module.CorrectnessAudit(correct=True, extracted_facts=[], fact_verdicts=[])
        ),
    )
    monkeypatch.setattr(
        calibrate_thresholds_module.ragas_metrics,
        "score_query",
        lambda *a, **k: _async_return(dict(_FAKE_RAGAS_SCORES)),
    )


@pytest.mark.asyncio
async def test_matches_via_severity_initial_fallback_when_severity_final_is_none(monkeypatch):
    """The real gq_001 scenario: incident_severity_node didn't run
    (non-incident/security category), so severity_final is None, but
    severity_initial ("Low") correctly matches the golden risk_level
    ("Low"). Before the fix, this scored risk_classification_accuracy as
    0.0 (None != "Low") despite the system's effective severity
    assessment being correct — the exact bug this test guards."""
    query_entry = _fake_query_entry(risk_level="Low")
    graph_result = _fake_graph_result(severity_final=None, severity_initial="Low")
    _patch_pipeline(monkeypatch, query_entry, graph_result)

    metrics = await run_calibration(sample=1, judge=object())

    assert metrics["risk_classification_accuracy"] == 1.0


@pytest.mark.asyncio
async def test_correctly_scores_a_genuine_mismatch_as_incorrect(monkeypatch):
    """Sanity check the other direction: the fallback shouldn't make
    every record trivially "correct" — a real mismatch between the
    resolved effective severity and the golden risk_level must still
    score as incorrect."""
    query_entry = _fake_query_entry(risk_level="High")
    graph_result = _fake_graph_result(severity_final=None, severity_initial="Low")
    _patch_pipeline(monkeypatch, query_entry, graph_result)

    metrics = await run_calibration(sample=1, judge=object())

    assert metrics["risk_classification_accuracy"] == 0.0


@pytest.mark.asyncio
async def test_prefers_severity_final_over_severity_initial_when_both_set(monkeypatch):
    """resolve_effective_severity() itself already guards this
    (test_router.py), but confirms run_calibration() actually calls it
    rather than, say, checking severity_initial first by accident: when
    incident_severity_node DID run and set a real severity_final, that
    value — not severity_initial — must be what gets compared against
    the golden risk_level."""
    query_entry = _fake_query_entry(risk_level="Critical")
    graph_result = _fake_graph_result(severity_final="Critical", severity_initial="Low")
    _patch_pipeline(monkeypatch, query_entry, graph_result)

    metrics = await run_calibration(sample=1, judge=object())

    assert metrics["risk_classification_accuracy"] == 1.0
