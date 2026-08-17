"""
tests/unit/test_calibrate_thresholds_scoring.py

Regression coverage for a real, confirmed gap: §15's own tracing
convention ("langfuse.create_score() attaches task_success +
confidence_score post-eval") was never actually wired up — tracing.
safe_create_score() existed and was unit-tested in isolation
(test_tracing.py) since the original Stage 8 tracing work, but was never
called from evaluation/calibrate_thresholds.py or ragas_metrics.py. Now
wired into run_calibration()'s per-query loop, attaching all six real
per-query signals it already has on hand after compute_correctness() and
ragas_metrics.score_query() run: task_success, confidence_score, and the
four RAGAS scores (extended beyond the two §15 names, since the RAGAS
scores are already computed at real judge-call cost regardless —
attaching them is free at this point, not a new call).

Extends test_tracing.py's own fake-Langfuse-client pattern (a
_FakeClient with a configurable create_score() failure mode) rather than
mocking tracing.safe_create_score() itself — this exercises the REAL
safe_create_score() implementation against a fake Langfuse client, the
same way test_tracing.py's own tests do, so this test proves the actual
integration works, not just that calibrate_thresholds.py calls a
function named safe_create_score.
"""

from __future__ import annotations

import pytest

import evaluation.calibrate_thresholds as calibrate_thresholds_module
from app.observability import tracing
from evaluation.calibrate_thresholds import run_calibration


class _FakeScoringClient:
    """Records every create_score() call for assertion; fail_score=True
    simulates a genuine Langfuse-side failure on every call, mirroring
    test_tracing.py's own _FakeClient shape."""

    def __init__(self, *, fail_score: bool = False) -> None:
        self.fail_score = fail_score
        self.score_calls: list[dict] = []

    def create_score(self, **kwargs) -> None:
        self.score_calls.append(kwargs)
        if self.fail_score:
            raise RuntimeError("boom-score")


def _fake_query_entry() -> dict:
    return {
        "id": "test_q",
        "query": "How do I configure X?",
        "query_type": "Documentation",
        "risk_level": "Low",
        "expected_retrieval_mode": "RAG",
        "expected_escalation": "No",
        "ground_truth_answer": "Do X.",
        "expected_sources": [],
    }


def _fake_graph_result(*, trace_id: str | None) -> dict:
    return {
        "final_answer": "Do X.",
        "confidence_score": 0.85,
        "retrieval_mode": "RAG",
        "severity_final": None,
        "severity_initial": "Low",
        "escalation_flag": False,
        "retrieved_chunks": [],
        "retrieved_tables": [],
        "retrieved_diagrams": [],
        "sql_results": [],
        "trace_id": trace_id,
    }


_FAKE_RAGAS_SCORES = {
    "faithfulness": 0.8,
    "answer_relevance": 0.7,
    "context_precision": 0.9,
    "context_recall": 1.0,
}


async def _async_return(value):
    return value


def _patch_pipeline(monkeypatch, query_entry: dict, graph_result: dict, *, correct: bool = True) -> None:
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
            calibrate_thresholds_module.CorrectnessAudit(correct=correct, extracted_facts=[], fact_verdicts=[])
        ),
    )
    monkeypatch.setattr(
        calibrate_thresholds_module.ragas_metrics,
        "score_query",
        lambda *a, **k: _async_return(dict(_FAKE_RAGAS_SCORES)),
    )


@pytest.mark.asyncio
async def test_run_calibration_attaches_all_six_scores_with_correct_trace_id_name_and_value(monkeypatch):
    query_entry = _fake_query_entry()
    graph_result = _fake_graph_result(trace_id="trace_real_123")
    _patch_pipeline(monkeypatch, query_entry, graph_result, correct=True)

    client = _FakeScoringClient()
    monkeypatch.setattr(tracing, "get_client", lambda: client)

    await run_calibration(sample=1, judge=object())

    assert len(client.score_calls) == 6
    by_name = {call["name"]: call["value"] for call in client.score_calls}
    assert by_name == {
        "task_success": 1.0,
        "confidence_score": 0.85,
        "faithfulness": 0.8,
        "answer_relevance": 0.7,
        "context_precision": 0.9,
        "context_recall": 1.0,
    }
    assert all(call["trace_id"] == "trace_real_123" for call in client.score_calls)


@pytest.mark.asyncio
async def test_run_calibration_attaches_task_success_zero_when_answer_is_incorrect(monkeypatch):
    query_entry = _fake_query_entry()
    graph_result = _fake_graph_result(trace_id="trace_real_456")
    _patch_pipeline(monkeypatch, query_entry, graph_result, correct=False)

    client = _FakeScoringClient()
    monkeypatch.setattr(tracing, "get_client", lambda: client)

    await run_calibration(sample=1, judge=object())

    by_name = {call["name"]: call["value"] for call in client.score_calls}
    assert by_name["task_success"] == 0.0


@pytest.mark.asyncio
async def test_run_calibration_survives_langfuse_failing_on_every_score_call(monkeypatch):
    """The defensive-wrapper contract, exercised under six failures per
    query, not just one: a genuine Langfuse outage on every single score
    attachment must never break the real golden-eval run mid-pass —
    run_calibration() must still complete and return correct metrics."""
    query_entry = _fake_query_entry()
    graph_result = _fake_graph_result(trace_id="trace_real_789")
    _patch_pipeline(monkeypatch, query_entry, graph_result, correct=True)

    client = _FakeScoringClient(fail_score=True)
    monkeypatch.setattr(tracing, "get_client", lambda: client)

    metrics = await run_calibration(sample=1, judge=object())

    # All 6 attempts were made (and each failed) — the run wasn't short-circuited early.
    assert len(client.score_calls) == 6
    # The real metrics computation is completely unaffected by the score-attachment failures.
    assert metrics["task_success_rate"] == 1.0
    assert metrics["faithfulness"] == 0.8


@pytest.mark.asyncio
async def test_run_calibration_skips_score_attachment_when_trace_id_is_missing(monkeypatch):
    """Defensive guard for the (currently never-expected, per golden_
    runner.py's own real behavior) case of a missing trace_id — must not
    call create_score() with trace_id=None, and must not crash."""
    query_entry = _fake_query_entry()
    graph_result = _fake_graph_result(trace_id=None)
    _patch_pipeline(monkeypatch, query_entry, graph_result, correct=True)

    client = _FakeScoringClient()
    monkeypatch.setattr(tracing, "get_client", lambda: client)

    metrics = await run_calibration(sample=1, judge=object())

    assert client.score_calls == []
    assert metrics["task_success_rate"] == 1.0
