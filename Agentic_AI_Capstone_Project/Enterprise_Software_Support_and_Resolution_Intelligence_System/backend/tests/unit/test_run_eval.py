"""
tests/unit/test_run_eval.py

Pure unit coverage for evaluation/run_eval.py's own additions beyond
calibrate_thresholds.py (§25 Stage 9) — latency-vs-target, Source
Attribution Rate, the raw Accuracy/LLM-judge mean, and the prompt-
version-override/restore behavior compare_prompt_versions() depends on.
Fully mocked (golden_runner, compute_correctness, ragas_metrics.
score_query, tracing.get_client) — zero real graph/judge calls, same
pattern as test_calibrate_thresholds_severity.py/test_calibrate_
thresholds_scoring.py, since evaluate_golden_query() (the function these
mocks intercept) is shared by both modules.
"""

from __future__ import annotations

import pytest

import evaluation.calibrate_thresholds as calibrate_thresholds_module
import evaluation.run_eval as run_eval_module
from app.observability import tracing
from evaluation.run_eval import compare_prompt_versions, run_eval


def _fake_query_entry(*, query_type: str = "Documentation", risk_level: str = "Low") -> dict:
    return {
        "id": "test_q",
        "query": "How do I configure X?",
        "query_type": query_type,
        "risk_level": risk_level,
        "expected_retrieval_mode": "RAG",
        "expected_escalation": "No",
        "ground_truth_answer": "Do X.",
        "expected_sources": [],
    }


def _fake_graph_result(
    *, retrieval_mode: str = "RAG", sources: list | None = None, groundedness_flag: bool = True
) -> dict:
    return {
        "final_answer": "Do X.",
        "confidence_score": 0.9,
        "retrieval_mode": retrieval_mode,
        "severity_final": None,
        "severity_initial": "Low",
        "escalation_flag": False,
        "retrieved_chunks": [],
        "retrieved_tables": [],
        "retrieved_diagrams": [],
        "sql_results": [],
        "sources": sources if sources is not None else ["some_source"],
        "groundedness_flag": groundedness_flag,
        "trace_id": None,
    }


_FAKE_RAGAS_SCORES = {"faithfulness": 0.8, "answer_relevance": 0.7, "context_precision": 0.9, "context_recall": 1.0}


async def _async_return(value):
    return value


def _patch_pipeline(monkeypatch, query_entries: list[dict], graph_results: list[dict], *, correct: bool = True):
    calls = {"index": 0}

    def _fake_load_golden_queries(sample):
        return query_entries

    def _fake_run_through_graph(entry):
        idx = calls["index"]
        calls["index"] += 1
        return _async_return(graph_results[idx])

    monkeypatch.setattr(calibrate_thresholds_module.golden_runner, "load_golden_queries", _fake_load_golden_queries)
    monkeypatch.setattr(
        calibrate_thresholds_module.golden_runner, "run_golden_query_through_graph", _fake_run_through_graph
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
    monkeypatch.setattr(tracing, "get_client", lambda: None)  # no-op Langfuse client for these tests


@pytest.mark.asyncio
async def test_run_eval_computes_source_attribution_and_accuracy_llm_judge(monkeypatch):
    entries = [_fake_query_entry(), _fake_query_entry()]
    results = [
        _fake_graph_result(sources=["src_a"], groundedness_flag=True),   # attributed
        _fake_graph_result(sources=[], groundedness_flag=True),          # NOT attributed (no sources)
    ]
    _patch_pipeline(monkeypatch, entries, results, correct=True)

    metrics = await run_eval(sample=2)

    assert metrics["source_attribution_rate"] == 0.5
    assert metrics["accuracy_llm_judge"] == 1.0
    assert metrics["sample_size"] == 2


@pytest.mark.asyncio
async def test_run_eval_accuracy_llm_judge_reflects_incorrect_answers(monkeypatch):
    entries = [_fake_query_entry()]
    results = [_fake_graph_result()]
    _patch_pipeline(monkeypatch, entries, results, correct=False)

    metrics = await run_eval(sample=1)

    assert metrics["accuracy_llm_judge"] == 0.0


@pytest.mark.asyncio
async def test_run_eval_latency_summary_grouped_by_retrieval_mode(monkeypatch):
    entries = [_fake_query_entry(), _fake_query_entry()]
    results = [
        _fake_graph_result(retrieval_mode="RAG"),
        _fake_graph_result(retrieval_mode="Critical"),
    ]
    _patch_pipeline(monkeypatch, entries, results, correct=True)

    metrics = await run_eval(sample=2)

    assert "RAG" in metrics["latency_by_mode"]
    assert "Critical" in metrics["latency_by_mode"]
    assert metrics["latency_by_mode"]["RAG"]["target_seconds"] == 2.0
    assert metrics["latency_by_mode"]["Critical"]["target_seconds"] == 3.5
    # Real latency will be near-zero here (fully mocked pipeline, no real
    # sleep/IO), so both should comfortably meet their own target.
    assert metrics["latency_by_mode"]["RAG"]["p95_meets_target"] is True
    assert metrics["latency_by_mode"]["Critical"]["p95_meets_target"] is True


@pytest.mark.asyncio
async def test_run_eval_prompt_version_override_restored_after_run(monkeypatch):
    from app.config import get_settings

    entries = [_fake_query_entry()]
    results = [_fake_graph_result()]
    _patch_pipeline(monkeypatch, entries, results, correct=True)

    settings = get_settings()
    original = settings.active_prompt_version

    seen_versions = []

    def _fake_run_through_graph(entry):
        seen_versions.append(get_settings().active_prompt_version)
        return _async_return(results[0])

    monkeypatch.setattr(
        calibrate_thresholds_module.golden_runner, "run_golden_query_through_graph", _fake_run_through_graph
    )

    metrics = await run_eval(sample=1, prompt_version="v2")

    assert seen_versions == ["v2"]
    assert metrics["prompt_version"] == "v2"
    assert get_settings().active_prompt_version == original  # restored, not left overridden


@pytest.mark.asyncio
async def test_run_eval_prompt_version_restored_even_if_the_run_raises(monkeypatch):
    from app.config import get_settings

    settings = get_settings()
    original = settings.active_prompt_version

    def _fake_load_golden_queries(sample):
        raise RuntimeError("boom")

    monkeypatch.setattr(calibrate_thresholds_module.golden_runner, "load_golden_queries", _fake_load_golden_queries)

    with pytest.raises(RuntimeError, match="boom"):
        await run_eval(sample=1, prompt_version="v2")

    assert get_settings().active_prompt_version == original


@pytest.mark.asyncio
async def test_compare_prompt_versions_runs_both_versions_and_reports_both(monkeypatch):
    entries = [_fake_query_entry()]
    results = [_fake_graph_result()]
    _patch_pipeline(monkeypatch, entries, results, correct=True)

    seen_versions = []

    def _fake_run_through_graph(entry):
        from app.config import get_settings

        seen_versions.append(get_settings().active_prompt_version)
        return _async_return(_fake_graph_result())

    monkeypatch.setattr(
        calibrate_thresholds_module.golden_runner, "run_golden_query_through_graph", _fake_run_through_graph
    )

    comparison = await compare_prompt_versions(sample=1, version_a="v1", version_b="v2")

    assert seen_versions == ["v1", "v2"]
    assert comparison["version_a"] == "v1"
    assert comparison["version_b"] == "v2"
    assert comparison["results_a"]["prompt_version"] == "v1"
    assert comparison["results_b"]["prompt_version"] == "v2"
