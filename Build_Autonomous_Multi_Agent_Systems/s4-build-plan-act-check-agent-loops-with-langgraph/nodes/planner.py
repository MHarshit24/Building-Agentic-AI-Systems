import json
from langchain_core.messages import SystemMessage, HumanMessage
from state.state import MarketResearchState
from llm import llm


def planning_node(state: MarketResearchState):
    """Generate a multi-step execution plan for market research.
    
    TODO:
    1. Extract user_request from state["messages"][0].content
    2. Build prompt asking LLM to decompose into 3-5 steps with JSON format
    3. Invoke llm.invoke() with SystemMessage and HumanMessage
    4. Parse JSON from response.content (remove markdown fences if present)
    5. Normalize plan items to dicts with step, action, tool, expected_output
    6. Limit to plan[:5]
    7. Update state["plan"], state["current_step"]=1, flags=False, replan_attempts=0
    8. Return state
    """
    # TODO: Step 1 - Extract request
    user_request = state["messages"][0].content

    # TODO: Step 2 - Build prompt
    system_prompt = """You are a market research planning assistant. 
Decompose the user's research request into 3-5 concrete, executable steps.
Each step must specify which tool to use: search_web or calculate.
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

    human_prompt = f"Create a research plan for: {user_request}"

    # TODO: Step 3 - Invoke LLM
    response = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=human_prompt)])

    # TODO: Step 4 - Parse JSON
    try:
        content = response.content.strip()
        # Remove markdown fences if present
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()
        plan = json.loads(content)
    except json.JSONDecodeError:
        # Fallback plan if LLM returns invalid JSON
        plan = [
            {
                "step": 1,
                "action": f"Search for information about: {user_request}",
                "tool": "search_web",
                "expected_output": "Relevant search results about the topic"
            }
        ]

    # TODO: Step 5 - Normalize plan
    normalized_plan = []
    for item in plan:
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

    # TODO: Step 6 - Limit steps
    normalized_plan = normalized_plan[:5]

    # TODO: Step 7 - Update state
    # Planner sets non-additive fields directly; messages already initialized in main.py
    updated_state = {
        "plan": normalized_plan,
        "current_step": 1,
        "task_complete": False,
        "needs_replanning": False,
        "replan_attempts": 0
    }

    # TODO: Step 8 - Return state
    return updated_state