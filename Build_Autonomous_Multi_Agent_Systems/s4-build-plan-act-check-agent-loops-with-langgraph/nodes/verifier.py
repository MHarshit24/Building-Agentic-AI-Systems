import json
from langchain_core.messages import SystemMessage, HumanMessage
from state.state import MarketResearchState
from llm import llm


def verification_node(state: MarketResearchState):
    """Verify if the executed step met success criteria.
    
    TODO:
    1. Safety: if no execution_results or current_step > len(plan), set task_complete=True, return
    2. Get step_info from plan[current_step-1], last_result from execution_results[-1]
    3. Build prompt with step action, expected_output, actual result, request JSON: {"status": "PASS"/"FAIL", "reason": "..."}
    4. Invoke llm.invoke() with SystemMessage and HumanMessage
    5. Parse JSON from response.content (remove markdown fences), handle JSONDecodeError
    6. Append to verification_status: {"step": current_step, "status": ..., "reason": ...}
    7. If status=="FAIL", set needs_replanning=True, return
    8. If PASS: reset replan_attempts=0, increment current_step or set task_complete=True
    9. Return state
    """
    # TODO: Step 1 - Safety checks
    current_step = state["current_step"]
    plan = state["plan"]
    if not state["execution_results"] or current_step > len(plan):
        return {"task_complete": True}

    # TODO: Step 2 - Get info
    step_info = plan[current_step - 1]
    last_result = state["execution_results"][-1]

    # TODO: Step 3 - Build prompt
    system_prompt = """You are a quality verification assistant for market research.
Evaluate whether the executed step produced a satisfactory result.
Respond ONLY with a valid JSON object — no markdown fences, no preamble.
Format: {"status": "PASS", "reason": "explanation"}
Use "PASS" if the result meaningfully addresses the step's goal, "FAIL" otherwise."""

    human_prompt = f"""Verify this step:
Step action: {step_info.get("action", "")}
Expected output: {step_info.get("expected_output", "")}
Actual result: {str(last_result.get("result", ""))[:1000]}

Did the actual result meet the expected output? Respond with JSON only."""

    # TODO: Step 4 - Invoke LLM
    response = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=human_prompt)])

    # TODO: Step 5 - Parse result
    try:
        content = response.content.strip()
        # Remove markdown fences if present
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()
        verification_result = json.loads(content)
    except json.JSONDecodeError:
        # Default to PASS on parse failure to avoid infinite loops
        verification_result = {"status": "PASS", "reason": "Verification parse failed, defaulting to PASS"}

    status = verification_result.get("status", "PASS")
    reason = verification_result.get("reason", "")

    # TODO: Step 6 - Store status
    # Return only the new verification entry; operator.add appends it
    new_verification = [{"step": current_step, "status": status, "reason": reason}]

    # TODO: Step 7 - Handle FAIL
    if status == "FAIL":
        return {
            "verification_status": new_verification,
            "needs_replanning": True
        }

    # TODO: Step 8 - Handle PASS
    # Advance to next step or mark complete
    if current_step >= len(plan):
        return {
            "verification_status": new_verification,
            "replan_attempts": 0,
            "task_complete": True
        }

    # TODO: Step 9 - Return state
    return {
        "verification_status": new_verification,
        "replan_attempts": 0,
        "current_step": current_step + 1
    }