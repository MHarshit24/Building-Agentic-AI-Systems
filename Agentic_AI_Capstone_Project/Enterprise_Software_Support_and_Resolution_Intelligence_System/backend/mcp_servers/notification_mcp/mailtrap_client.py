"""
mcp_servers/notification_mcp/mailtrap_client.py

Mailtrap SMTP sandbox client (§7) — the actual email-sending mechanism
`server.py`'s `send_escalation_email` tool calls into.

Uses stdlib `smtplib` wrapped in `asyncio.to_thread()`, not a new async
SMTP dependency (`aiosmtplib` etc.). `smtplib` is synchronous/blocking;
the same problem — and the same fix — already showed up once in this
codebase for Presidio's synchronous NLP calls (Stage 6's
`guardrails/pii.py` fix: calling a blocking library directly inside an
async function silently serializes whatever else is running on the same
event loop). This module runs inside `mcp_servers/notification_mcp/
server.py`'s own subprocess, which has nothing else concurrent competing
for its event loop the way the main app's Hybrid/Critical fan-out does —
but wrapping it the same way is free, consistent, and removes any future
risk if that ever changes.

Credentials (`SMTP_HOST`/`SMTP_PORT`/`SMTP_USERNAME`/`SMTP_PASSWORD`/
`APPLICATION_EMAIL`) already sit in the root `.env`, scaffolded into
`Settings` since an early stage, unused until now.
"""

from __future__ import annotations

import asyncio
import logging
import smtplib
from email.message import EmailMessage

from app.config import get_settings
from app.logging.structured_logger import log_event

logger = logging.getLogger(__name__)


def _send_email_sync(to: str, subject: str, body: str) -> None:
    settings = get_settings()

    message = EmailMessage()
    message["From"] = settings.application_email
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
        smtp.starttls()
        smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(message)


async def send_email(to: str, subject: str, body: str) -> bool:
    """Returns True on successful send, False on any failure — never
    raises, since a failed notification is a normal, expected, handled
    outcome (§36: caught, logged in notification_log with status=failed,
    eligible for exactly one future retry), not an exceptional one."""
    try:
        await asyncio.to_thread(_send_email_sync, to, subject, body)
        return True
    except Exception as exc:
        log_event(logger, "ERROR", "mailtrap_send_failed", error=str(exc), to=to)
        return False
