from langchain_core.messages import HumanMessage, ToolMessage
from state.state import MarketResearchState
from llm import llm_with_tools
from tools.tools import search_web, calculate


def execution_node(state: MarketResearchState):
    """Execute the current step from the plan.
    
    TODO:
    1. Safety check: if no plan or current_step > len(plan), set task_complete=True, return
    2. Get step_info from state["plan"][current_step - 1], extract action, tool_name
    3. Create exec_message = f"Execute this step: {action} using {tool_name}"
    4. Invoke llm_with_tools.invoke(state["messages"] + [HumanMessage(content=exec_message)])
    5. Append response to state["messages"]
    6. If no response.tool_calls, append to execution_results and return
    7. Get tool_call from response.tool_calls[0], invoke search_web or calculate
    8. Append to execution_results: {"step": current_step, "action": action, "result": result}
    9. Append ToolMessage(content=result, tool_call_id=tool_call["id"]) to messages
    10. Return state
    """
    # TODO: Step 1 - Safety check
    current_step = state["current_step"]
    plan = state["plan"]
    if not plan or current_step > len(plan):
        return {"task_complete": True}

    # TODO: Step 2 - Get step info
    step_info = plan[current_step - 1]
    action = step_info.get("action", "")
    tool_name = step_info.get("tool", "search_web")

    # TODO: Step 3 - Create message
    # Include the most recent result so multi-step chains (e.g. search -> calculate) have data to work with
    last_result_context = ""
    if state["execution_results"]:
        last_result_context = f"\n\nResult from previous step: {str(state['execution_results'][-1]['result'])[:500]}"

    exec_message = f"Execute this step: {action} using {tool_name}{last_result_context}"

    # TODO: Step 4 - Invoke LLM
    response = llm_with_tools.invoke(state["messages"] + [HumanMessage(content=exec_message)])

    # TODO: Step 5 - Add response to messages
    # Return only the new message; operator.add will append it to the existing list
    new_messages = [response]

    # TODO: Step 6 - Handle no tool call
    if not response.tool_calls:
        return {
            "messages": new_messages,
            "execution_results": [{"step": current_step, "action": action, "result": response.content}]
        }

    # TODO: Step 7 - Execute tool
    tool_call = response.tool_calls[0]
    tool_args = tool_call.get("args", {})
    if tool_call.get("name") == "calculate":
        expression = tool_args.get("expression", "")
        result = calculate.invoke(expression)
    else:
        query = tool_args.get("query", "")
        result = search_web.invoke(query)

    # TODO: Step 8 - Store result
    # TODO: Step 9 - Add ToolMessage
    # Return only new items for all Annotated[List, operator.add] fields
    new_messages.append(ToolMessage(content=result, tool_call_id=tool_call["id"]))

    # TODO: Step 10 - Return state
    return {
        "messages": new_messages,
        "execution_results": [{"step": current_step, "action": action, "result": result}]
    }