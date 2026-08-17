# Runbook

Operational notes and documented (not stubbed) extension points. The full
deployment runbook (environments, rollback, scaling) is Stage 10 work per
the roadmap (§25) — this file is seeded early, in Stage 7, specifically
for the notes below, which belong here rather than in `README.md`.

## Escalation notification channels (§7)

Only Mailtrap (email) is implemented for this capstone —
`mcp_servers/notification_mcp/server.py`'s `send_escalation_email` tool.
Slack and PagerDuty are **documented, unbuilt extension points**, not
stubbed code: adding either would mean a new tool on the same MCP server
(e.g. `send_slack_message`), called from the same `notify_human()` client
wrapper (`app/mcp_client/notification_client.py`) that already
orchestrates `send_escalation_email` + `log_notification` — no change to
`escalate_node`, `routes_chat.py`'s dispatch, or the `notification_log`
schema (`channel` is already a plain string, not a fixed enum, precisely
so a new channel value never needs a migration).

## MCP transport: stdio (subprocess), not a networked service

The notification MCP server runs as a real, protocol-compliant server
(`mcp[cli]`) over **stdio transport** — `app/mcp_client/
notification_client.py` spawns `python -m
mcp_servers.notification_mcp.server` as a subprocess for the duration of
one notification, not a separately deployed/network-addressed process.
`MCP_NOTIFICATION_URL` (`.env.example`) is HTTP-shaped and currently
unread by any code — a forward-looking hook for the day a notification
backend genuinely needs to live behind a real network boundary
(`FastMCP.run(transport="streamable-http")` supports this without a
rewrite). Stdio is the right transport for an in-process/subprocess
integration today, and this deliberately doesn't pull in Docker or any
separately-deployed service — consistent with `docker-compose.yml` itself
still being deferred to Stage 10.

## Right-to-erasure / hard-delete for conversations — deferred, not stubbed

Only reversible archival is implemented for conversations (`POST
/conversations/{id}/archive`) — a genuine hard-delete, the kind a real
GDPR-style "right to erasure" request would require, is a **documented,
deliberately-unbuilt extension point**, not an oversight. Building it
correctly needs a decision this capstone has no real basis to make yet:
what happens to `escalation_log`/`notification_log` rows whose `trace_id`
points at a message being erased — null out the dangling reference
(losing the record of which message triggered a real escalation), or
cascade-delete the escalation/notification row too (destroying one audit
trail to satisfy erasure of a different one)? Either answer is
defensible, but picking one without a real erasure request in hand risks
shaping it wrong for whatever the actual legal/product requirement turns
out to need. No such request has ever been received for this capstone,
and ongoing production data-lifecycle policy beyond what's built is
already an accepted out-of-scope boundary here (§22.1's same treatment
of user-provisioning lifecycle) — this is the same category of
deferral, named rather than silently skipped.

## Scheduled retry job (§36) — deferred to Stage 10

A failed notification is logged in `notification_log` with
`status="failed"` and is eligible for exactly one retry
(`app.db.models.is_eligible_for_retry`). The actual **scheduled
execution** of that retry (cron / APScheduler / whatever process
re-invokes `send_escalation_email` for eligible rows) is infrastructure-
shaped, the same category of thing as `docker-compose.yml`, and is
deferred to Stage 10 alongside it — not silently skipped. The data model
and the retry-eligibility decision logic are real and tested today;
only the scheduler that acts on them doesn't exist yet.
