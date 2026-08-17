"""
app/prompts/escalate_v1.py

Prompt builder for the Escalation Manager Agent (§3 roster #7, §39.3's
EscalationOutput schema). §32.2 template order: ROLE_INSTRUCTIONS ->
OUTPUT_SCHEMA -> FEW_SHOT -> (no TOOL_DEFS; escalate_node makes no tool
calls of its own — it only reads already-known state, never fetches
anything new) -> dynamic context (the full decision picture: category,
severity, confidence, groundedness, retrieval_mode, any draft answer
that existed before escalation, and why the loop guards fired if they
did) -> history -> query.

Two audiences, kept explicitly separate in ROLE_INSTRUCTIONS: escalation_reason
is an internal/audit string (-> escalation_log.reason); human_handoff_summary
is written for the human agent picking up the ticket (-> the notification
email body / ticket_context_json). Neither is customer-facing — the
customer-facing final_answer stays Stage 5's fixed/templated text,
untouched by this prompt's output (see escalate.py's own docstring).
"""

from app.prompts._shared import INJECTION_DEFENSE_CLAUSE, JSON_ONLY_CLAUSE

ROLE_INSTRUCTIONS = (
    "You are the Escalation Manager Agent for an enterprise software support system. This "
    "query has already been decided to require human handling — your job is not to decide "
    "whether to escalate (that decision is already made), only to draft two pieces of text "
    "for what happens next:\n\n"
    "1. escalation_reason: a short, precise, internal audit note explaining WHY this escalated "
    "(e.g. severity, confidence tier, an explicit human request, or a repeated loop-back). This "
    "goes into a permanent audit log, not to the customer or the human agent directly.\n"
    "2. human_handoff_summary: a concise briefing FOR THE HUMAN SUPPORT AGENT who will pick "
    "this up — what the customer asked, what the system found (or failed to find), and "
    "anything genuinely useful for them to know before responding. Write this for a colleague, "
    "not for the customer.\n\n"
    "Do not draft a customer-facing message — that is handled separately and is not your job "
    "here.\n\n"
    f"{INJECTION_DEFENSE_CLAUSE}"
)

OUTPUT_SCHEMA = (
    "Output schema:\n"
    '{"escalation_reason": str, "human_handoff_summary": str}\n\n'
    f"{JSON_ONLY_CLAUSE}"
)

FEW_SHOT = (
    "Example 1 (low confidence, no draft answer):\n"
    "Category: usage | Severity: Low | Confidence tier: Low (0.42) | Groundedness: false\n"
    "Query: \"How do I migrate my custom plugin configs between major versions?\"\n"
    'Output: {"escalation_reason": "Low confidence (0.42) — evidence was insufficient to '
    'answer safely, escalated per the always-escalate-on-Low-confidence rule.", '
    '"human_handoff_summary": "Customer is asking how to migrate custom plugin configs across '
    "major versions. Retrieved documentation didn't clearly cover this scenario, so the system "
    'declined to guess. May need a manual walkthrough of the migration tooling."}\n\n'
    "Example 2 (Critical severity, explicit human request):\n"
    "Category: incident | Severity: Critical | Confidence tier: High (0.91) | Explicit human "
    "request: true\n"
    "Query: \"Our production system is down — I need to talk to a person right now.\"\n"
    'Output: {"escalation_reason": "Critical severity always escalates regardless of '
    'confidence, and the customer also explicitly requested a human.", "human_handoff_summary": '
    '"Customer reports a production outage and explicitly asked for a human. Treat as urgent — '
    'this bypassed automated retrieval entirely per the explicit-request short-circuit."}'
)


def build_prompt(static_ctx: dict, dynamic_ctx: dict) -> list[dict]:
    """
    static_ctx: unused.
    dynamic_ctx: {"query": str, "history": list[dict], "category": str | None,
                  "severity": str | None, "confidence_tier": str | None,
                  "confidence_score": float | None, "groundedness_flag": bool | None,
                  "retrieval_mode": str | None, "explicit_human_request": bool,
                  "draft_answer": str | None, "retrieval_retry_count": int,
                  "reflection_loopback_count": int}
    """
    query = dynamic_ctx["query"]
    history = dynamic_ctx.get("history") or []

    static_section = "\n\n".join([ROLE_INSTRUCTIONS, OUTPUT_SCHEMA, FEW_SHOT])

    decision_picture = (
        f"Category: {dynamic_ctx.get('category') or '(unknown)'} | "
        f"Severity: {dynamic_ctx.get('severity') or '(unknown)'} | "
        f"Confidence tier: {dynamic_ctx.get('confidence_tier') or '(none)'} "
        f"({dynamic_ctx.get('confidence_score')}) | "
        f"Groundedness: {dynamic_ctx.get('groundedness_flag')} | "
        f"Retrieval mode: {dynamic_ctx.get('retrieval_mode') or '(none)'} | "
        f"Explicit human request: {dynamic_ctx.get('explicit_human_request', False)} | "
        f"Retrieval retries: {dynamic_ctx.get('retrieval_retry_count', 0)} | "
        f"Reflection loop-backs: {dynamic_ctx.get('reflection_loopback_count', 0)}"
    )
    draft_answer = dynamic_ctx.get("draft_answer") or "(no draft answer was produced before escalating)"

    dynamic_parts = [f"Decision context:\n{decision_picture}", f"Draft answer so far, if any:\n{draft_answer}"]
    if history:
        history_text = "\n".join(f"{turn.get('role', 'user')}: {turn.get('content', '')}" for turn in history)
        dynamic_parts.append(f"Conversation history:\n{history_text}")
    dynamic_parts.append(f"Query: {query}")

    return [
        {"role": "static", "content": static_section},
        {"role": "dynamic", "content": "\n\n".join(dynamic_parts)},
    ]
