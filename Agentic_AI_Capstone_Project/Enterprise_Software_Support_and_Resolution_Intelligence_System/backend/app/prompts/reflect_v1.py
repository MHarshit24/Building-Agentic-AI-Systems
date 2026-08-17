"""
app/prompts/reflect_v1.py

Prompt builder for the Reflection Agent (§3 roster #6, §39.3's
ReflectionOutput schema). §32.2 template order: ROLE_INSTRUCTIONS ->
OUTPUT_SCHEMA -> FEW_SHOT (incl. a grounded-refusal / low-confidence
example per §14) -> (no TOOL_DEFS; reflect is read-only, takes no
tools) -> dynamic context (the draft answer + evidence it was built
from) -> history -> query.

This prompt asks ONLY for the LLM's own self-critique half of §14
point 3's "dual-check groundedness" — the rule-based citation-overlap
check is separate, non-LLM code in reflect.py itself, and the two are
blended there, not inside this prompt.
"""

from app.prompts._shared import INJECTION_DEFENSE_CLAUSE, JSON_ONLY_CLAUSE

ROLE_INSTRUCTIONS = (
    "You are the Reflection Agent for an enterprise software support system. You are given "
    "a draft answer, the retrieved evidence it was supposedly built from, and the original "
    "query. Judge two things, honestly and critically — this is a self-critique step, not a "
    "second attempt at answering:\n\n"
    "1. groundedness_flag: does the draft answer's content actually follow from the retrieved "
    "evidence, with no claims that go beyond what the evidence supports?\n"
    "2. confidence_score: your own confidence (0.0-1.0) that this draft answer correctly and "
    "completely answers the query, given the evidence quality.\n\n"
    "Be skeptical of vague, overly general, or confident-sounding answers that don't clearly "
    "trace back to specific retrieved evidence — that's exactly the failure mode this check "
    "exists to catch.\n\n"
    f"{INJECTION_DEFENSE_CLAUSE}"
)

OUTPUT_SCHEMA = (
    "Output schema:\n"
    '{"confidence_score": float (0.0-1.0), "groundedness_flag": bool, '
    '"confidence_tier": "High" | "Medium" | "Low"}\n\n'
    "confidence_tier is your own rough read of confidence_score against these bands: "
    "High >= 0.85, Medium 0.70-0.849, Low < 0.70 — provided for reference, the system computes "
    "the authoritative tier itself from the final blended score.\n\n"
    f"{JSON_ONLY_CLAUSE}"
)

FEW_SHOT = (
    "Example 1 (well-grounded, high confidence):\n"
    "Draft answer: \"A 429 error means the rate limit was exceeded. Wait 60 seconds and "
    "implement exponential backoff.\"\n"
    "Evidence: [table_6] \"429 | Rate limit exceeded | Wait 60s, implement exponential "
    "backoff\"\n"
    'Output: {"confidence_score": 0.95, "groundedness_flag": true, "confidence_tier": "High"}\n\n'
    "Example 2 (ungrounded refusal correctly reported, §14):\n"
    "Draft answer: \"I don't have enough information to answer that.\"\n"
    "Evidence: (no evidence retrieved)\n"
    'Output: {"confidence_score": 0.3, "groundedness_flag": false, "confidence_tier": "Low"}'
)


def build_prompt(static_ctx: dict, dynamic_ctx: dict) -> list[dict]:
    """
    static_ctx: unused.
    dynamic_ctx: {"query": str, "history": list[dict], "draft_answer": str, "evidence": str}
    """
    query = dynamic_ctx["query"]
    history = dynamic_ctx.get("history") or []
    draft_answer = dynamic_ctx.get("draft_answer") or "(no draft answer produced)"
    evidence = dynamic_ctx.get("evidence") or "(no evidence retrieved)"

    static_section = "\n\n".join([ROLE_INSTRUCTIONS, OUTPUT_SCHEMA, FEW_SHOT])

    dynamic_parts = [f"Draft answer:\n{draft_answer}", f"Evidence it was built from:\n{evidence}"]
    if history:
        history_text = "\n".join(f"{turn.get('role', 'user')}: {turn.get('content', '')}" for turn in history)
        dynamic_parts.append(f"Conversation history:\n{history_text}")
    dynamic_parts.append(f"Query: {query}")

    return [
        {"role": "static", "content": static_section},
        {"role": "dynamic", "content": "\n\n".join(dynamic_parts)},
    ]
