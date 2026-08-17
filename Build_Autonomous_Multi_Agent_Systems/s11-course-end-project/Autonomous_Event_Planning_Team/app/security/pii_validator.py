"""Responsible for PII validation and sensitive data checks.

Routes free-text scrubbing to whichever engine app.config.Settings.pii_engine
names. Only "presidio" is implemented; any other value (or an empty brief
field) is left untouched rather than raising, since this is a defense-in-
depth measure and must never block a legitimate planning request.
"""

from app.config import get_settings
from app.schemas.domain import EventBrief
from app.security.presidio_engine import scrub as presidio_scrub


def sanitize_text(text: str) -> str:
    if get_settings().pii_engine == "presidio":
        return presidio_scrub(text)
    return text


def sanitize_brief(brief: EventBrief) -> EventBrief:
    """Return a copy of brief with its free-text fields PII-scrubbed."""
    updates = {
        "objective": sanitize_text(brief.objective),
        "constraints": [sanitize_text(c) for c in brief.constraints],
    }
    if brief.venue_preference:
        updates["venue_preference"] = sanitize_text(brief.venue_preference)

    return brief.model_copy(update=updates)
