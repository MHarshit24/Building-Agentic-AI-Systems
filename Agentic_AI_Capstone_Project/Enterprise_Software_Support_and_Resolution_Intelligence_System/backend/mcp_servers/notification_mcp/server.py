"""
mcp_servers/notification_mcp/server.py

The Escalation Notification MCP server (§7, §18) — a real, protocol-
compliant MCP server (`mcp[cli]`, already pinned in requirements.txt
specifically for this stage), not plain functions with MCP-flavored
naming. Exposes exactly the two tools §7's own file comment names:
`send_escalation_email()` and `log_notification()`.

Run as a subprocess over stdio transport (`app/mcp_client/
notification_client.py` spawns it via `StdioServerParameters`) — a real
client/server split with no Docker, no separately deployed/network-
addressed service. Only Mailtrap is implemented; Slack/PagerDuty are
documented (unbuilt) extension points (`docs/runbook.md`), not stubbed
code, per §7's own framing.

Each tool's real logic lives in a plain, undecorated async function
(`_send_escalation_email_impl`/`_log_notification_impl`) — directly
importable and callable in tests without going through the protocol at
all, since this module runs as a genuinely separate process once
spawned, and a test process's monkeypatch/mock calls can't reach into a
subprocess's own module state. The `@mcp_server.tool()`-decorated
functions are thin wrappers, only exercised by the one real end-to-end
(`@pytest.mark.eval`) test that spawns the actual subprocess.

`log_notification` runs INSIDE this process (its own `async_session_maker()`
session, same standalone-DB-access pattern `sql_tools/queries.py` already
uses) — matching §12's sequence diagram literally: `MCP->>DB:
log_notification` is drawn as the MCP participant writing to the
database, not the API layer.
"""

from __future__ import annotations

import logging

from mcp.server.fastmcp import FastMCP

from app.config import get_settings
from app.db.models import NotificationLog, NotificationStatus
from app.db.session import async_session_maker
from app.logging.structured_logger import log_event
from mcp_servers.notification_mcp.mailtrap_client import send_email

logger = logging.getLogger(__name__)

mcp_server = FastMCP("notification-mcp")


def _format_escalation_email(escalation_id: int, ticket_context: dict, reason: str, summary: str) -> tuple[str, str]:
    """Returns (subject, body). Plain text, not templated HTML — this is
    an internal handoff notification to the support team's own inbox,
    not a customer-facing message."""
    severity = ticket_context.get("severity_final") or ticket_context.get("severity_initial") or "Unknown"
    subject = f"[Escalation #{escalation_id}] {severity} severity — {ticket_context.get('category') or 'uncategorized'}"
    body = (
        f"Escalation ID: {escalation_id}\n"
        f"Trace ID: {ticket_context.get('trace_id')}\n"
        f"Conversation ID: {ticket_context.get('conversation_id')}\n"
        f"Customer ID: {ticket_context.get('customer_id')}\n"
        f"Handled by (user_id): {ticket_context.get('handled_by_user_id')}\n\n"
        f"Reason: {reason}\n\n"
        f"Summary for handling agent:\n{summary}\n\n"
        f"Original query:\n{ticket_context.get('query')}\n\n"
        f"Draft answer before escalation:\n{ticket_context.get('final_answer_draft') or '(none)'}\n"
    )
    return subject, body


async def _send_escalation_email_impl(escalation_id: int, ticket_context: dict, reason: str, summary: str) -> dict:
    settings = get_settings()
    subject, body = _format_escalation_email(escalation_id, ticket_context, reason, summary)
    success = await send_email(to=settings.support_email, subject=subject, body=body)
    return {"success": success}


async def _log_notification_impl(escalation_id: int, channel: str, status: str) -> None:
    async with async_session_maker() as db:
        db.add(NotificationLog(escalation_id=escalation_id, channel=channel, status=NotificationStatus(status)))
        await db.commit()
    log_event(logger, "INFO", "notification_logged", escalation_id=escalation_id, channel=channel, status=status)


@mcp_server.tool()
async def send_escalation_email(escalation_id: int, ticket_context: dict, reason: str, summary: str) -> dict:
    """Sends the escalation handoff email to the support team's inbox
    (settings.support_email). Returns {"success": bool} — never raises;
    a delivery failure is a normal, handled outcome (§36)."""
    return await _send_escalation_email_impl(escalation_id, ticket_context, reason, summary)


@mcp_server.tool()
async def log_notification(escalation_id: int, channel: str, status: str) -> None:
    """Records one notification attempt. status must be one of
    NotificationStatus's values ("sent"/"failed"/"failed_permanently")."""
    await _log_notification_impl(escalation_id, channel, status)


if __name__ == "__main__":
    mcp_server.run(transport="stdio")
