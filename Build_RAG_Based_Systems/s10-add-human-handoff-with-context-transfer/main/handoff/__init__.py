"""
Human Handoff Module
Handles automatic human handoff triggers based on evaluation scores and user requests.
"""

from main.handoff.handoff_service import (
    evaluate_score,
    send_handoff_email,
    generate_handoff_reference_id,
    evaluate_explicit_user_request,
    evaluate_confidence_score,
)

__all__ = [
    "evaluate_score",
    "send_handoff_email",
    "generate_handoff_reference_id",
    "evaluate_explicit_user_request",
    "evaluate_confidence_score",
]

