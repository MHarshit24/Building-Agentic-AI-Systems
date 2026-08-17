"""
app/mcp_client/notification_client.py

The MCP client side of §7's notification integration — one new file
beyond §18's literal listing (which only names the server side,
`mcp_servers/notification_mcp/`), justified explicitly: `routes_chat.py`'s
`BackgroundTasks` target shouldn't need `StdioServerParameters`/
`ClientSession` protocol boilerplate inlined into the route file itself.

`notify_human()` is the ONE stable entrypoint the rest of the app calls
(§7: "The Escalation Manager Agent calls one stable tool (notify_human())
regardless of backend") — it spawns the notification server as a
subprocess over stdio for the duration of exactly one notification,
calls `send_escalation_email` then `log_notification` over that one
session, and lets the subprocess exit when the `async with` blocks close.

Subprocess-per-notification is the right cost/benefit call here
specifically: this only ever runs inside a FastAPI `BackgroundTask`,
already scheduled to execute *after* the user-facing response has
returned (§7) — subprocess spin-up latency doesn't count against any SLO
at all, unlike if this were on the request's own critical path.
"""

from __future__ import annotations

import json
import logging
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import CallToolResult, TextContent

from app.logging.structured_logger import log_event

logger = logging.getLogger(__name__)

_SERVER_PARAMS = StdioServerParameters(
    command=sys.executable,
    args=["-m", "mcp_servers.notification_mcp.server"],
)


def _tool_call_succeeded(result: CallToolResult) -> bool:
    """Found empirically, not assumed: this FastMCP version does NOT
    populate CallToolResult.structuredContent for a tool that returns a
    plain dict (confirmed via a direct diagnostic call — structuredContent
    came back None while the real {"success": true/false} JSON was in
    content[0].text instead). Parses content first: without this fix,
    every real send success was misread as "failed", the exact bug this
    project's own "prove it, don't assume it" discipline exists to catch."""
    if result.isError:
        return False
    if result.structuredContent is not None:
        return bool(result.structuredContent.get("success"))
    for block in result.content:
        if isinstance(block, TextContent):
            try:
                return bool(json.loads(block.text).get("success"))
            except (json.JSONDecodeError, AttributeError):
                continue
    return False


async def notify_human(escalation_id: int, ticket_context: dict, reason: str, summary: str) -> None:
    """Called by routes_chat.py via BackgroundTasks.add_task(...) — never
    awaited inline in the request-handling path (§7's non-blocking
    requirement). Never raises: a failed notification is caught, logged,
    and recorded in notification_log (§36) — it must never surface as an
    unhandled exception in a background task, since nothing is listening
    for one by the time this runs."""
    try:
        async with stdio_client(_SERVER_PARAMS) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                email_result = await session.call_tool(
                    "send_escalation_email",
                    {
                        "escalation_id": escalation_id,
                        "ticket_context": ticket_context,
                        "reason": reason or "",
                        "summary": summary or "",
                    },
                )
                status = "sent" if _tool_call_succeeded(email_result) else "failed"

                await session.call_tool(
                    "log_notification",
                    {"escalation_id": escalation_id, "channel": "email", "status": status},
                )
    except Exception as exc:
        # The MCP round-trip itself (subprocess spawn, protocol handshake)
        # failing is a different failure mode from the email send failing
        # cleanly inside the server (which already logs "failed" via
        # log_notification above) — this catches that outer case, where
        # notification_log may not have gotten a row written at all.
        log_event(logger, "ERROR", "notify_human_failed", escalation_id=escalation_id, error=str(exc))
