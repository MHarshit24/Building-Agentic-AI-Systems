import os
import logging
import uvicorn
from pathlib import Path
from fastapi import FastAPI
from langgraph.graph import StateGraph, END
from langchain_openai import AzureChatOpenAI
from langchain_core.messages import HumanMessage, ToolMessage, SystemMessage
from dotenv import load_dotenv

from state import CustomerSupportState
from tools import get_account_info, calculate
from prompts import REASONING_PROMPT

# Load environment variables from root .env (4 levels up from this file),
# falling back to load_dotenv() if not found
BASE_DIR = Path(__file__).resolve().parents[2]
base_env_path = BASE_DIR / ".env"
if base_env_path.exists():
    load_dotenv(dotenv_path=base_env_path)
else:
    load_dotenv()

# Configure logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Multi-Tool Banking Customer Support ReAct Agent ", description="A customer support agent that uses tools to answer customer queries")

# Initialize LLM with tools
# TODO: Initialize AzureChatOpenAI with:
#   - api_key from environment variable AZURE_OPENAI_API_KEY
#   - azure_endpoint from environment variable AZURE_OPENAI_ENDPOINT
#   - model from environment variable AZURE_OPENAI_MODEL (default: "gpt-4o-mini")
#   - api_version from environment variable AZURE_OPENAI_API_VERSION
#   - temperature=0
# TODO: Bind tools [get_account_info, calculate] to the LLM using .bind_tools()
llm = AzureChatOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    azure_deployment=os.getenv("AZURE_OPENAI_LLM_DEPLOYMENT", os.getenv("AZURE_OPENAI_MODEL", "gpt-4o-mini")),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    temperature=0,
)
llm = llm.bind_tools([get_account_info, calculate])

# ---------------- Reasoning Node ----------------
def reasoning_node(state: CustomerSupportState):
    """
    Reasoning node that decides next action or provides final answer.
    
    TODO:
    1. Build the reasoning prompt by formatting REASONING_PROMPT with:
       - thought_history from state
       - action_log from state
       - observation_results from state
    2. Get messages from state and convert to list
    3. Prepend a SystemMessage with the formatted prompt to the messages list
    4. Invoke the LLM with the messages
    5. Extract thought if present in response.content:
       - Check if content starts with "THOUGHT"
       - Extract the thought (remove "THOUGHT:" and strip)
       - If there's a newline, only take the first line
       - Append to state["thought_history"]
       - Log using logger.info(f"THOUGHT: {thought}")
    6. Check if task is complete:
       - If response.content contains "FINAL ANSWER", set state["task_complete"] = True
    7. Return {"messages": [response]}
    """
    # TODO: Implement reasoning_node logic
    formatted_prompt = REASONING_PROMPT.format(
        thought_history=state["thought_history"],
        action_log=state["action_log"],
        observation_results=state["observation_results"],
    )
    messages = list(state["messages"])
    messages = [SystemMessage(content=formatted_prompt)] + messages
    response = llm.invoke(messages)
    if isinstance(response.content, str) and response.content.strip().startswith("THOUGHT"):
        thought = response.content.strip().replace("THOUGHT:", "", 1).strip()
        if "\n" in thought:
            thought = thought.split("\n")[0]
        state["thought_history"].append(thought)
        logger.info(f"THOUGHT: {thought}")
    if isinstance(response.content, str) and "FINAL ANSWER" in response.content:
        state["task_complete"] = True
    return {"messages": [response]}

# ---------------- Tool Execution Node ----------------
def tool_execution_node(state: CustomerSupportState):
    """
    Execute the selected tool and return the observation.
    
    TODO:
    1. Get the last message from state["messages"]
    2. Safety check: if last_message has no tool_calls, return {"messages": []}
    3. Initialize an empty list for tool_messages
    4. Loop through all tool_calls in last_message.tool_calls:
       a. Extract tool_name and tool_args from tool_call
       b. Create action dict with "tool" and "input" keys
       c. Append action to state["action_log"]
       d. Log using logger.info(f"ACTION: {action}")
       e. Execute the appropriate tool:
          - If tool_name == "get_account_info": invoke get_account_info with tool_args
          - Elif tool_name == "calculate": invoke calculate with tool_args
          - Else: result = f"Unknown tool: {tool_name}"
       f. Append result to state["observation_results"]
       g. Log using logger.info(f"OBSERVATION: {result}")
       h. Create a ToolMessage with:
          - content=result
          - tool_call_id=tool_call["id"]
       i. Append ToolMessage to tool_messages list
    5. Return {"messages": tool_messages}
    """
    # TODO: Implement tool_execution_node logic
    last_message = state["messages"][-1]
    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        return {"messages": []}
    tool_messages = []
    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        action = {"tool": tool_name, "input": tool_args}
        state["action_log"].append(action)
        logger.info(f"ACTION: {action}")
        if tool_name == "get_account_info":
            result = get_account_info.invoke(tool_args)
        elif tool_name == "calculate":
            result = calculate.invoke(tool_args)
        else:
            result = f"Unknown tool: {tool_name}"
        state["observation_results"].append(result)
        logger.info(f"OBSERVATION: {result}")
        tool_messages.append(ToolMessage(content=result, tool_call_id=tool_call["id"]))
    return {"messages": tool_messages}

# ---------------- Loop Condition ----------------
def should_continue(state: CustomerSupportState) -> str:
    """
    Decide if agent should continue reasoning or finish.
    
    Returns:
        "continue" if tool call detected, "end" if final answer or max iterations
    
    TODO:
    1. Check if state["task_complete"] is True - if yes, return "end"
    2. Get the last message from state["messages"]
    3. Check if last_message.content contains "FINAL ANSWER" - if yes, return "end"
    4. Check if last_message has tool_calls:
       - If yes, check if len(state["action_log"]) >= 6 (max iterations)
       - If max iterations reached, return "end"
       - Otherwise, return "continue"
    5. Check if last_message is a ToolMessage - if yes, return "continue"
    6. Default: return "end" (safety fallback)
    """
    # TODO: Implement should_continue logic
    if state.get("task_complete"):
        return "end"
    last_message = state["messages"][-1]
    if isinstance(last_message.content, str) and "FINAL ANSWER" in last_message.content:
        return "end"
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        if len(state["action_log"]) >= 6:
            return "end"
        return "continue"
    if isinstance(last_message, ToolMessage):
        return "continue"
    return "end"

# ---------------- Build Graph ----------------
# TODO: Build the ReAct graph:
# 1. Create StateGraph with CustomerSupportState
# 2. Add node "reasoning" with reasoning_node function
# 3. Add node "tool_execution" with tool_execution_node function
# 4. Set entry point to "reasoning"
# 5. Add conditional edges from "reasoning" using should_continue function:
#    - "continue" -> "tool_execution"
#    - "end" -> END
# 6. Add edge from "tool_execution" back to "reasoning"
# 7. Compile the graph
graph = StateGraph(CustomerSupportState)
graph.add_node("reasoning", reasoning_node)
graph.add_node("tool_execution", tool_execution_node)
graph.set_entry_point("reasoning")
graph.add_conditional_edges(
    "reasoning",
    should_continue,
    {"continue": "tool_execution", "end": END},
)
graph.add_edge("tool_execution", "reasoning")
react_graph = graph.compile()

# ---------------- API ----------------
@app.post("/support/query")
def support_query(query: str):
    """
    Handle customer support queries through the ReAct agent.
    
    Returns only the final answer. Thoughts, actions, and observations are logged to the terminal.
    
    TODO:
    1. Log the query using logger.info()
    2. Initialize state with:
       - messages: [HumanMessage(content=query)]
       - thought_history: []
       - action_log: []
       - observation_results: []
       - task_complete: False
    3. Invoke react_graph with the state
    4. Extract final answer from result["messages"]:
       - Loop through messages in reverse order
       - Find message with "FINAL ANSWER" in content
       - Extract the part after "FINAL ANSWER:"
       - Clean up any lines that start with "THOUGHT:" or "ACTION:"
    5. If no FINAL ANSWER found, use the last message content as fallback
    6. Log the final answer using logger.info()
    7. Return {"answer": final_answer}
    """
    # TODO: Implement support_query logic
    logger.info(f"Query: {query}")
    state = {
        "messages": [HumanMessage(content=query)],
        "thought_history": [],
        "action_log": [],
        "observation_results": [],
        "task_complete": False,
    }
    result = react_graph.invoke(state)
    final_answer = None
    for message in reversed(result["messages"]):
        if isinstance(message.content, str) and "FINAL ANSWER" in message.content:
            raw = message.content.split("FINAL ANSWER:", 1)[1]
            lines = [
                line for line in raw.splitlines()
                if not line.strip().startswith("THOUGHT:") and not line.strip().startswith("ACTION:")
            ]
            final_answer = "\n".join(lines).strip()
            break
    if final_answer is None:
        final_answer = result["messages"][-1].content
    logger.info(f"Final Answer: {final_answer}")
    return {"answer": final_answer}

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )