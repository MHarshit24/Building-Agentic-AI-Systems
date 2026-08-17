import json
from langchain_core.messages import SystemMessage, HumanMessage
from state.state import MarketResearchState
from llm import llm

MAX_REPLANS = 2


def replanning_node(state: MarketResearchState):
    """Generate an adjusted plan when a step fails verification.
    
    TODO:
    1. Increment state["replan_attempts"]
    2. If replan_attempts > MAX_REPLANS, set needs_replanning=False, advance/complete, return
    3. Get failed_step from plan[current_step-1], verification_info from verification_status[-1]
    4. Build prompt with original plan (json.dumps), failed step details, failure reason, execution result[:500]
    5. Invoke llm.invoke() with SystemMessage and HumanMessage
    6. Parse JSON from response.content (remove markdown fences)
    7. Normalize revised_plan items to dicts with step, action, tool, expected_output
    8. Set state["plan"] = normalized_plan[:5], state["needs_replanning"] = False
    9. Handle JSONDecodeError: simplify failed step action, set needs_replanning=False
    10. Return state
    """
    # TODO: Step 1 - Increment attempts
    new_replan_attempts = state["replan_attempts"] + 1

    # TODO: Step 2 - Check max attempts
    current_step = state["current_step"]
    plan = state["plan"]
    if new_replan_attempts > MAX_REPLANS:
        if current_step >= len(plan):
            return {"replan_attempts": new_replan_attempts, "needs_replanning": False, "task_complete": True}
        return {"replan_attempts": new_replan_attempts, "needs_replanning": False, "current_step": current_step + 1}

    # TODO: Step 3 - Get context
    failed_step = plan[current_step - 1]
    verification_info = state["verification_status"][-1] if state["verification_status"] else {}
    last_execution = state["execution_results"][-1] if state["execution_results"] else {}

    # TODO: Step 4 - Build prompt
    system_prompt = """You are a market research replanning assistant.
A step in the research plan has failed verification. Revise the plan to fix the issue.
Keep completed steps as-is, revise the failed step and any subsequent steps as needed.
Respond ONLY with a valid JSON array — no markdown fences, no preamble.
Format:
[
  {
    "step": 1,
    "action": "Description of what to do",
    "tool": "search_web",
    "expected_output": "What a successful result looks like"
  }
]"""

    human_prompt = f"""Revise this research plan:
Original plan: {json.dumps(plan)}
Failed step ({current_step}): {json.dumps(failed_step)}
Failure reason: {verification_info.get("reason", "Unknown")}
Execution result (truncated): {str(last_execution.get("result", ""))[:500]}

Provide a revised JSON plan that addresses the failure."""

    # TODO: Step 5 - Invoke LLM
    response = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=human_prompt)])

    # TODO: Step 6 - Parse plan
    try:
        content = response.content.strip()
        # Remove markdown fences if present
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()
        revised_plan = json.loads(content)

        # TODO: Step 7 - Normalize plan
        normalized_plan = []
        for item in revised_plan:
            if isinstance(item, dict):
                normalized_plan.append({
                    "step": item.get("step", len(normalized_plan) + 1),
                    "action": item.get("action", ""),
                    "tool": item.get("tool", "search_web"),
                    "expected_output": item.get("expected_output", "")
                })
            elif isinstance(item, str):
                normalized_plan.append({
                    "step": len(normalized_plan) + 1,
                    "action": item,
                    "tool": "search_web",
                    "expected_output": "Relevant information found"
                })

        # TODO: Step 8 - Update state
        return {
            "plan": normalized_plan[:5],
            "needs_replanning": False,
            "replan_attempts": new_replan_attempts
        }

    except json.JSONDecodeError:
        # TODO: Step 9 - Handle error: simplify the failed step action and move on
        simplified_action = f"Search for general information about: {failed_step.get('action', 'the topic')}"
        new_plan = list(plan)
        new_plan[current_step - 1] = {
            "step": current_step,
            "action": simplified_action,
            "tool": "search_web",
            "expected_output": "Any relevant information found"
        }
        # TODO: Step 10 - Return state
        return {
            "plan": new_plan,
            "needs_replanning": False,
            "replan_attempts": new_replan_attempts
        }