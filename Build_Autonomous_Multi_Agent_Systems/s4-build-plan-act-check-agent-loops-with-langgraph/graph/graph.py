from langgraph.graph import StateGraph, END
from state.state import MarketResearchState
from nodes.planner import planning_node
from nodes.executor import execution_node
from nodes.verifier import verification_node
from nodes.replanner import replanning_node

MAX_STEPS = 10  # Safety limit for total execution steps


def should_continue(state: MarketResearchState) -> str:
    """Route based on state to determine next action.
    
    TODO:
    1. If task_complete is True, return "complete"
    2. If current_step > MAX_STEPS, set task_complete=True, return "complete"
    3. If needs_replanning is True, return "replan"
    4. Return "execute"
    """
    # TODO: Step 1 - Check complete
    if state.get("task_complete", False):
        return "complete"

    # TODO: Step 2 - Check max steps
    # Note: should_continue is a conditional-edge function; LangGraph only uses its
    # return value to pick the next node and does not merge any state mutation made
    # here back into the graph state. The state dict is read-only for routing purposes.
    if state.get("current_step", 1) > MAX_STEPS:
        return "complete"

    # TODO: Step 3 - Check replanning
    if state.get("needs_replanning", False):
        return "replan"

    # TODO: Step 4 - Return execute
    return "execute"


# TODO: Step 1 - Create workflow = StateGraph(MarketResearchState)
# TODO: Step 2 - Add nodes: planner, executor, verifier, replanner
# TODO: Step 3 - Set entry point: "planner"
# TODO: Step 4 - Add edges: planner->executor, executor->verifier, replanner->executor
# TODO: Step 5 - Add conditional edges from verifier with should_continue, mapping: {"execute": "executor", "replan": "replanner", "complete": END}
# TODO: Step 6 - Compile: app_graph = workflow.compile()

workflow = StateGraph(MarketResearchState)

workflow.add_node("planner", planning_node)
workflow.add_node("executor", execution_node)
workflow.add_node("verifier", verification_node)
workflow.add_node("replanner", replanning_node)

workflow.set_entry_point("planner")

workflow.add_edge("planner", "executor")
workflow.add_edge("executor", "verifier")
workflow.add_edge("replanner", "executor")

workflow.add_conditional_edges(
    "verifier",
    should_continue,
    {
        "execute": "executor",
        "replan": "replanner",
        "complete": END
    }
)

app_graph = workflow.compile()