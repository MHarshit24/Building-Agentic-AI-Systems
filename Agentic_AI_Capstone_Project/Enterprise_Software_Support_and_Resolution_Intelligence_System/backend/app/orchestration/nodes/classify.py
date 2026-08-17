"""
app/orchestration/nodes/classify.py

Intent Classification Agent (§3 roster #1). Always runs — first node in
the graph. Full agent implementation lives in this one file: prompt
assembly (classify_v1.build_prompt), the LLM call
(call_llm_structured), and the state-update return — no separate
agents/ layer anywhere in this codebase (confirmed against §18's
folder structure before writing this).

reasoning_effort="minimal" per §13's table: fixed-enum output, no
multi-step reasoning needed.
"""

from __future__ import annotations

from app.llm.structured_output import call_llm_structured
from app.prompts._shared import flatten_messages
from app.prompts.loader import get_build_prompt
from app.schemas.agent_contracts import ClassificationOutput
from app.schemas.state import SupportGraphState

REASONING_EFFORT = "minimal"


async def classify_node(state: SupportGraphState) -> dict:
    """Reads: query, chat_history. Writes: category, severity_initial,
    explicit_human_request (§4; the latter is README §5's "explicit
    request for human support" escalation trigger — read by graph.py's
    post-classify short-circuit, independent of severity/confidence_tier)."""
    build_prompt = get_build_prompt("classify")
    messages = build_prompt(
        static_ctx={},
        dynamic_ctx={"query": state["query"], "history": state.get("chat_history") or []},
    )
    prompt = flatten_messages(messages)

    result: ClassificationOutput = await call_llm_structured(
        prompt, ClassificationOutput, reasoning_effort=REASONING_EFFORT
    )

    return {
        "category": result.category,
        "severity_initial": result.severity_initial,
        "explicit_human_request": result.explicit_human_request,
    }
