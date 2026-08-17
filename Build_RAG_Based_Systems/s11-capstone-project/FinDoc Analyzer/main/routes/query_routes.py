"""
FinDoc Analyzer — POST /api/v1/query
The core intelligence endpoint. All 10 sprints + all gap/partial fixes land here.

Sprint2/3  — RAG retrieval
Sprint4    — LlamaIndex query engine
Sprint5    — Multimodal context (chart image analysis)
Sprint6    — Fusion Retrieval + Guardrails (guardrails-ai + presidio + custom)
Sprint7    — SQL / Hybrid routing (NLSQLTableQueryEngine)
Sprint8    — MCP external tools
Sprint9    — Langfuse tracing + faithfulness / relevance / context_precision + RAGAS
Sprint10   — Auto + manual human handoff

Langfuse SDK: v4 API
  - langfuse.create_trace_id()          → generate trace ID
  - langfuse.start_observation(...)     → create a span/observation
  - langfuse.create_score(trace_id=...) → attach a named score
  - span.update(output=...)             → set span output
  - span.end()                          → close the span
  - langfuse.flush()                    → flush all pending events

Each pipeline step is wrapped in its own observation so the Langfuse UI
shows a full waterfall with timing and I/O for:
  input_guardrails → query_routing → rag_retrieval/sql_lookup/hybrid/mcp_call
  → output_guardrails → evaluation → handoff_decision
"""

import logging
import time
import secrets
import datetime
import os
from typing import Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks, status

from main.models import QueryRequest, QueryResponse, SourceNode
from main.services.query_router import route_and_execute
from main.guardrails.validators import FinancialGuardrailsService
from main.evaluation.evaluation_service import (
    get_langfuse_client,
    evaluate_faithfulness_score,
    evaluate_answer_relevance,
    evaluate_context_precision,
    log_query,
)
from main.handoff.handoff_service import (
    generate_handoff_reference_id,
    evaluate_score,
    evaluate_confidence_score,
    evaluate_explicit_user_request,
    send_handoff_email,
)

router     = APIRouter()
logger     = logging.getLogger(__name__)
guardrails = FinancialGuardrailsService()


# ── Langfuse v4 span helpers ──────────────────────────────────────

def _lf_start_span(langfuse, trace_id: str, name: str, input_data: dict = None):
    """
    Create a Langfuse v4 observation (span) on the given trace.
    Uses langfuse.start_observation() — v4 API.
    Returns the span object or None if Langfuse is unavailable.
    """
    if not langfuse or not trace_id:
        return None
    try:
        return langfuse.start_observation(
            trace_context={"trace_id": trace_id},
            name=name,
            input=input_data or {},
        )
    except Exception as e:
        logger.debug(f"Langfuse span creation failed ({name}): {e}")
        return None


def _lf_end_span(span, output_data: dict = None):
    """End a Langfuse v4 observation with output data."""
    if not span:
        return
    try:
        span.update(output=output_data or {})
        span.end()
    except Exception as e:
        logger.debug(f"Langfuse span end failed: {e}")


def _lf_score(langfuse, trace_id: str, name: str, value: float, comment: str = ""):
    """
    Attach a named score to a trace.
    Uses langfuse.create_score() — v4 API (replaces langfuse.score()).
    """
    if not langfuse or not trace_id or value is None:
        return
    try:
        langfuse.create_score(
            trace_id=trace_id,
            name=name,
            value=value,
            comment=comment,
        )
    except Exception as e:
        logger.debug(f"Langfuse score failed ({name}): {e}")


# ═══════════════════════════════════════════════════════════════════
# Query endpoint
# ═══════════════════════════════════════════════════════════════════

@router.post(
    "/query",
    response_model=QueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Query financial documents (intelligent routing)",
    description=(
        "Natural language financial query with automatic routing to "
        "RAG / SQL / Hybrid / MCP. Applies guardrails-ai + presidio + custom validators, "
        "evaluates faithfulness/relevance/context_precision, and triggers "
        "human handoff when confidence is low. "
        "Full Langfuse v4 span tracing for every pipeline step."
    ),
)
async def query_financial_documents(
    request: QueryRequest,
    background_tasks: BackgroundTasks,
):
    t_start      = time.time()
    session_id   = secrets.token_hex(8)
    trace_id: Optional[str] = None
    langfuse     = None
    llm_provider = os.getenv("LLM_PROVIDER", "azure")

    # ═══════════════════════════════════════════════════════════
    # Step 1 — Input guardrails (before trace init — fast check)
    # ═══════════════════════════════════════════════════════════
    is_valid, input_error = guardrails.validator.validate_input(request.question)
    if not is_valid:
        raise HTTPException(
            status_code=400,
            detail=f"Query blocked by guardrails: {input_error}"
        )

    # ═══════════════════════════════════════════════════════════
    # Step 2 — Initialise Langfuse v4 root trace
    # ═══════════════════════════════════════════════════════════
    langfuse = get_langfuse_client()
    if langfuse:
        try:
            # v4: generate a trace ID, then create the root observation
            trace_id = langfuse.create_trace_id()
            root_span = langfuse.start_observation(
                trace_context={"trace_id": trace_id},
                name="findoc_query",
                input={
                    "question":     request.question,
                    "routing_hint": request.routing_hint,
                    "user_email":   request.user_email,
                },
                metadata={
                    "session_id":    session_id,
                    "llm_provider":  llm_provider,
                    "timestamp_utc": datetime.datetime.now(datetime.UTC).isoformat(),
                },
            )
            logger.info(f"✓ Langfuse trace created: {trace_id}")
        except Exception as e:
            logger.error(f"Langfuse trace creation failed: {e}", exc_info=True)
            langfuse  = None
            trace_id  = None
            root_span = None
    else:
        root_span = None

    try:
        # ═══════════════════════════════════════════════════════
        # Step 3 — Input guardrails span
        # ═══════════════════════════════════════════════════════
        span_input_guard = _lf_start_span(
            langfuse, trace_id, "input_guardrails",
            {"question": request.question}
        )
        _lf_end_span(span_input_guard, {
            "valid":        True,
            "input_length": len(request.question),
        })

        # ═══════════════════════════════════════════════════════
        # Step 4 — Route and execute
        # ═══════════════════════════════════════════════════════
        span_routing = _lf_start_span(
            langfuse, trace_id, "query_routing",
            {"question": request.question, "routing_hint": request.routing_hint}
        )

        route_result = await route_and_execute(
            question=request.question,
            routing_hint=request.routing_hint,
        )

        answer       = route_result["answer"]
        routing_used = route_result["routing_used"]
        raw_nodes    = route_result.get("source_nodes", [])
        sql_query    = route_result.get("sql_query")

        _lf_end_span(span_routing, {
            "routing_used":       routing_used,
            "source_nodes_count": len(raw_nodes),
            "sql_query":          sql_query,
            "answer_preview":     answer[:200] if answer else "",
        })

        # ═══════════════════════════════════════════════════════
        # Step 5 — Per-route detailed span
        # ═══════════════════════════════════════════════════════
        route_span_name = {
            "rag":    "rag_retrieval",
            "sql":    "sql_lookup",
            "hybrid": "hybrid_retrieval",
            "mcp":    "mcp_call",
        }.get(routing_used, "retrieval")

        span_route_detail = _lf_start_span(
            langfuse, trace_id, route_span_name,
            {"question": request.question, "route": routing_used}
        )
        _lf_end_span(span_route_detail, {
            "chunks_retrieved": len(raw_nodes),
            "sql_generated":    sql_query,
            "answer_length":    len(answer),
        })

        # ═══════════════════════════════════════════════════════
        # Step 6 — Build context for eval + traceability
        # ═══════════════════════════════════════════════════════
        eval_context   = "\n\n".join(n.get("text", "") for n in raw_nodes)
        context_chunks = [n.get("text", "") for n in raw_nodes if n.get("text")]

        # ═══════════════════════════════════════════════════════
        # Step 7 — Output guardrails
        # ═══════════════════════════════════════════════════════
        span_output_guard = _lf_start_span(
            langfuse, trace_id, "output_guardrails",
            {"answer_length": len(answer)}
        )
        guard_result = guardrails.validate_and_annotate(
            question=request.question,
            answer=answer,
            source_context=eval_context,
        )
        final_answer     = guard_result.get("sanitized_answer", answer)
        pii_redacted     = guard_result.get("pii_redacted", False)
        output_warnings  = guard_result.get("output_warnings", [])
        disclaimer_added = guard_result.get("financial_disclaimer_added", False)

        _lf_end_span(span_output_guard, {
            "pii_redacted":               pii_redacted,
            "financial_disclaimer_added": disclaimer_added,
            "output_warnings":            output_warnings,
            "final_answer_length":        len(final_answer),
        })

        # ═══════════════════════════════════════════════════════
        # Step 8 — Evaluation metrics
        # ═══════════════════════════════════════════════════════
        span_eval = _lf_start_span(
            langfuse, trace_id, "evaluation",
            {"context_chunks": len(context_chunks), "answer_length": len(final_answer)}
        )

        faithfulness  = await evaluate_faithfulness_score(
            langfuse, trace_id, request.question, eval_context, final_answer
        )
        relevance     = await evaluate_answer_relevance(
            langfuse, trace_id, request.question, final_answer
        )
        ctx_precision = await evaluate_context_precision(
            request.question, context_chunks, final_answer
        )

        # ── Langfuse v4: create_score() for each eval metric ─────
        _lf_score(langfuse, trace_id, "faithfulness",      faithfulness,
                  f"Auto-evaluated | route={routing_used}")
        _lf_score(langfuse, trace_id, "answer_relevance",  relevance,
                  f"Auto-evaluated | route={routing_used}")
        _lf_score(langfuse, trace_id, "context_precision", ctx_precision,
                  f"Auto-evaluated | route={routing_used}")

        _lf_end_span(span_eval, {
            "faithfulness":      faithfulness,
            "relevance":         relevance,
            "context_precision": ctx_precision,
        })

        # ═══════════════════════════════════════════════════════
        # Step 9 — Handoff decision
        # ═══════════════════════════════════════════════════════
        span_handoff = _lf_start_span(
            langfuse, trace_id, "handoff_decision",
            {"faithfulness": faithfulness, "relevance": relevance, "route": routing_used}
        )

        no_chunks        = len(raw_nodes) == 0
        score_handoff    = evaluate_score(faithfulness, relevance, request.question, no_chunks)
        explicit_handoff = await evaluate_explicit_user_request(request.question)

        if routing_used in ("sql", "hybrid"):
            confidence_handoff = {"trigger": False, "confidence": 90}
        else:
            confidence_handoff = await evaluate_confidence_score(final_answer)
            logger.info(f"score_handoff={score_handoff}")
            logger.info(f"explicit_handoff={explicit_handoff}")
            logger.info(f"confidence_handoff={confidence_handoff}")

        is_investment_advice_handoff = (
            score_handoff["trigger"]
            and "investment advice" in score_handoff.get("reason", "")
        )
        if explicit_handoff["trigger"]:
            handoff, priority = explicit_handoff, "high"
        elif is_investment_advice_handoff:
            handoff, priority = score_handoff, "high"
        elif score_handoff["trigger"] and routing_used not in ("sql", "hybrid"):
            handoff, priority = score_handoff, "normal"
        elif confidence_handoff.get("trigger") and score_handoff["trigger"]:
            handoff, priority = confidence_handoff, "high"
        else:
            handoff, priority = {"trigger": False}, None

        handoff_triggered    = False
        handoff_reference_id = None

        if handoff["trigger"]:
            handoff_triggered    = True
            handoff_reference_id = generate_handoff_reference_id()
            timestamp_utc        = datetime.datetime.now(datetime.UTC).isoformat()

            handoff_context = {
                "reference_id":     handoff_reference_id,
                "trace_id":         trace_id,
                "timestamp_utc":    timestamp_utc,
                "session_id":       session_id,
                "priority":         priority,
                "trigger_reason":   handoff.get("reason", "unknown"),
                "question":         request.question,
                "generated_answer": final_answer,
                "evaluation_scores": {
                    "faithfulness":      faithfulness,
                    "relevance":         relevance,
                    "context_precision": ctx_precision,
                    "confidence":        confidence_handoff.get("confidence"),
                },
                "retrieved_chunks": "\n---\n".join(
                    f"[Score:{n.get('score', 0):.3f}] {n.get('text', '')[:300]}"
                    for n in raw_nodes
                ),
                "routing_used":  routing_used,
                "user_metadata": {"email": request.user_email},
            }

            background_tasks.add_task(send_handoff_email, handoff_context)
            logger.info(
                f"Handoff triggered: ref={handoff_reference_id} "
                f"reason={handoff['reason']}"
            )

            # Log handoff as a score on the trace
            _lf_score(langfuse, trace_id, "handoff_triggered", 1.0,
                      handoff.get("reason", ""))

            final_answer = (
                "I don't have sufficient confidence to answer this reliably. "
                "Your request has been escalated to a financial expert. "
                f"Reference ID: {handoff_reference_id}"
            )

        _lf_end_span(span_handoff, {
            "handoff_triggered":    handoff_triggered,
            "handoff_reference_id": handoff_reference_id,
            "handoff_reason":       handoff.get("reason") if handoff_triggered else None,
            "confidence":           confidence_handoff.get("confidence"),
        })

        # ═══════════════════════════════════════════════════════
        # Step 10 — Log for SLO store + close root span
        # ═══════════════════════════════════════════════════════
        latency_ms = (time.time() - t_start) * 1000

        background_tasks.add_task(
            log_query,
            request.question,
            final_answer,
            routing_used,
            latency_ms,
            faithfulness,
            relevance,
            ctx_precision,
            trace_id,
        )

        # Close the root observation with final output + metadata
        if root_span:
            try:
                root_span.update(
                    output={
                        "answer":               final_answer[:500],
                        "routing_used":         routing_used,
                        "handoff_triggered":    handoff_triggered,
                        "handoff_reference_id": handoff_reference_id,
                    },
                    metadata={
                        "latency_ms":        round(latency_ms, 2),
                        "faithfulness":      faithfulness,
                        "relevance":         relevance,
                        "context_precision": ctx_precision,
                        "pii_redacted":      pii_redacted,
                        "output_warnings":   output_warnings,
                        "llm_provider":      llm_provider,
                        "source_nodes":      len(raw_nodes),
                    },
                )
                root_span.end()
                langfuse.flush()
                logger.info(
                    f"✓ Langfuse trace flushed: {trace_id} "
                    f"(latency={latency_ms:.0f}ms)"
                )
            except Exception as e:
                logger.error(f"Langfuse root span close/flush failed: {e}")

        # ═══════════════════════════════════════════════════════
        # Step 11 — Build and return response
        # ═══════════════════════════════════════════════════════
        source_nodes = [
            SourceNode(
                chunk_id=n.get("chunk_id", ""),
                text=n.get("text", ""),
                score=float(n.get("score", 0.0)),
                source=n.get("source"),
                metadata=n.get("metadata", {}),
            )
            for n in raw_nodes
        ]

        return QueryResponse(
            question=request.question,
            answer=final_answer,
            routing_used=routing_used,
            source_nodes=source_nodes,
            sql_query=sql_query,
            validation_results={
                **guard_result,
                "faithfulness":      faithfulness,
                "relevance":         relevance,
                "context_precision": ctx_precision,
                "latency_ms":        round(latency_ms, 2),
                "llm_provider":      llm_provider,
            },
            handoff_triggered=handoff_triggered,
            handoff_reference_id=handoff_reference_id,
            trace_id=trace_id,
        )

    except HTTPException:
        if root_span:
            try:
                root_span.end()
                langfuse.flush()
            except Exception:
                pass
        raise

    except Exception as e:
        logger.error(f"Query processing failed: {e}", exc_info=True)

        # Record failure on the Langfuse trace before re-raising
        if root_span:
            try:
                root_span.update(output={"error": str(e), "error_type": type(e).__name__})
                root_span.end()
                langfuse.flush()
            except Exception:
                pass

        raise HTTPException(
            status_code=500,
            detail=f"Query processing failed: {str(e)}"
        )