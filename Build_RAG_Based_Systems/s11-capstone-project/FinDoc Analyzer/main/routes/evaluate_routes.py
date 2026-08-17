"""
FinDoc Analyzer — GET /api/v1/evaluate  +  POST /api/v1/evaluate/ragas
Evaluation & SLO compliance dashboard.

Covers:
  Sprint9 — Langfuse tracing, LLM-based faithfulness/relevance, SLO thresholds
  Partial Fix — Full RAGAS batch evaluation endpoint
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, status
from pydantic import BaseModel

from main.models import EvaluateResponse, SLOMetrics
from main.evaluation.evaluation_service import (
    compute_slo_report,
    get_langfuse_client,
    run_ragas_evaluation,
    _query_log,
    RAGAS_AVAILABLE,
)

router = APIRouter()
logger = logging.getLogger(__name__)


# ── RAGAS batch eval request model ───────────────────────────────
class RAGASEvalRequest(BaseModel):
    questions:     List[str]
    answers:       List[str]
    contexts:      List[List[str]]
    ground_truths: Optional[List[str]] = None


class RAGASEvalResponse(BaseModel):
    ragas_available: bool
    scores:          Optional[dict]  = None
    message:         str


# ── GET /evaluate — live SLO dashboard ───────────────────────────
@router.get(
    "/evaluate",
    response_model=EvaluateResponse,
    status_code=status.HTTP_200_OK,
    summary="Live SLO & evaluation dashboard",
    description=(
        "Returns per-query faithfulness, relevance, context precision, "
        "latency (avg + p95), routing distribution, and SLO compliance. "
        "Sprint9 + RAGAS partial fix."
    ),
)
async def get_evaluation_report():
    try:
        langfuse         = get_langfuse_client()
        langfuse_enabled = langfuse is not None
        report           = compute_slo_report()

        metrics = SLOMetrics(
            total_queries_evaluated=report["total_queries_evaluated"],
            avg_faithfulness=report.get("avg_faithfulness"),
            avg_relevance=report.get("avg_relevance"),
            avg_latency_ms=report.get("avg_latency_ms"),
            routing_distribution=report.get("routing_distribution", {}),
            slo_passed=report.get("slo_passed", False),
            slo_details={
                **report.get("slo_details", {}),
                "avg_context_precision": report.get("avg_context_precision"),
                "p95_latency_ms":        report.get("p95_latency_ms"),
                "ragas_available":       report.get("ragas_available", False),
            },
        )

        if report["total_queries_evaluated"] == 0:
            msg = "No data yet — run some /query calls first"
        elif report["slo_passed"]:
            msg = "✓ All SLOs passing"
        else:
            failing = [
                k for k, v in report.get("slo_details", {}).items()
                if isinstance(v, dict) and not v.get("passed", True)
            ]
            msg = f"✗ SLO failing on: {', '.join(failing)}"

        return EvaluateResponse(
            status="ok",
            metrics=metrics,
            evaluation_dataset_size=len(_query_log),
            langfuse_enabled=langfuse_enabled,
            message=msg,
        )

    except Exception as e:
        logger.error(f"Evaluation report failed: {e}", exc_info=True)
        return EvaluateResponse(
            status="error",
            metrics=SLOMetrics(
                total_queries_evaluated=0,
                slo_passed=False,
                slo_details={"error": str(e)},
            ),
            evaluation_dataset_size=0,
            langfuse_enabled=False,
            message=f"Evaluation error: {str(e)}",
        )


# ── POST /evaluate/ragas — RAGAS batch evaluation ─────────────────
@router.post(
    "/evaluate/ragas",
    response_model=RAGASEvalResponse,
    status_code=status.HTTP_200_OK,
    summary="Run RAGAS batch evaluation",
    description=(
        "Runs RAGAS framework evaluation (faithfulness, answer_relevancy, "
        "context_precision) on a provided set of QA pairs. "
        "Requires: ragas + datasets packages installed. Sprint9 partial fix."
    ),
)
async def run_ragas_batch(request: RAGASEvalRequest):
    """
    RAGAS batch evaluation on custom QA dataset.
    Useful for offline benchmarking of the RAG pipeline.
    """
    if not RAGAS_AVAILABLE:
        return RAGASEvalResponse(
            ragas_available=False,
            scores=None,
            message=(
                "RAGAS not installed. Run: pip install ragas datasets\n"
                "LLM-based evaluation (faithfulness + relevance) runs automatically "
                "on every /query call and is visible at GET /evaluate."
            ),
        )

    if len(request.questions) != len(request.answers) or \
       len(request.questions) != len(request.contexts):
        from fastapi import HTTPException
        raise HTTPException(
            status_code=400,
            detail="questions, answers, and contexts must all have the same length",
        )

    scores = await run_ragas_evaluation(
        questions=request.questions,
        answers=request.answers,
        contexts=request.contexts,
        ground_truths=request.ground_truths,
    )

    if scores:
        return RAGASEvalResponse(
            ragas_available=True,
            scores=scores,
            message=f"RAGAS evaluation complete on {len(request.questions)} sample(s)",
        )
    return RAGASEvalResponse(
        ragas_available=True,
        scores=None,
        message="RAGAS evaluation failed — check logs for details",
    )
