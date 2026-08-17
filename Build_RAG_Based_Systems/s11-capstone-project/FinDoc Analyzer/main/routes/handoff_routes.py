"""
FinDoc Analyzer — POST /api/v1/handoff
Manual human escalation endpoint.

Covers:
  Sprint10 — Human handoff with full context transfer, email notification
"""

import logging
import datetime
import secrets
from fastapi import APIRouter, HTTPException, BackgroundTasks, status

from main.models import HandoffRequest, HandoffResponse
from main.handoff.handoff_service import generate_handoff_reference_id, send_handoff_email

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post(
    "/handoff",
    response_model=HandoffResponse,
    status_code=status.HTTP_200_OK,
    summary="Trigger manual human escalation",
    description=(
        "Escalates a financial query to a human expert for review. "
        "Bundles the full context (question, answer, sources, eval scores) "
        "and sends a notification email to the support team. "
        "Sprint10: Human Handoff with full context transfer."
    ),
)
async def trigger_handoff(
    request: HandoffRequest,
    background_tasks: BackgroundTasks,
):
    """
    Manual handoff trigger — called when:
    - User explicitly requests expert review
    - Frontend UI has a 'Talk to an Expert' button
    - External system detects high-risk query

    Sprint10: send_handoff_email with full context package.
    """
    try:
        reference_id  = generate_handoff_reference_id()
        timestamp_utc = datetime.datetime.now(datetime.UTC).isoformat()
        session_id    = request.session_id or secrets.token_hex(8)

        # Build full context package (Sprint10)
        handoff_context = {
            "reference_id":    reference_id,
            "trace_id":        session_id,
            "timestamp_utc":   timestamp_utc,
            "session_id":      session_id,
            "priority":        "high",
            "trigger_reason":  request.reason or "Manual escalation by user",
            "question":        request.question,
            "generated_answer": request.answer,
            "evaluation_scores": request.evaluation_scores or {},
            "retrieved_chunks": "\n---\n".join(
                f"[Score: {n.score:.3f}] {n.text[:300]}"
                for n in (request.source_nodes or [])
            ) or "No source chunks provided",
            "routing_used":    "manual_handoff",
            "user_metadata":   {"email": request.user_email},
        }

        # Send email asynchronously in background (Sprint10 pattern)
        background_tasks.add_task(send_handoff_email, handoff_context)

        logger.info(
            f"✓ Manual handoff created: ref={reference_id}, "
            f"user={request.user_email}, reason={request.reason}"
        )

        return HandoffResponse(
            reference_id=reference_id,
            status="escalated",
            message=(
                f"Your query has been escalated to our financial expert team. "
                f"Reference ID: {reference_id}. "
                "You will be contacted within 1 business day."
            ),
            email_sent=True,  # Will be sent in background
            timestamp_utc=timestamp_utc,
        )

    except Exception as e:
        logger.error(f"Handoff creation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Handoff creation failed: {str(e)}")
