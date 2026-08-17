"""Graph nodes and building logic for the support agent with checkpointing."""

from langgraph.graph import StateGraph
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage, AIMessage
from schemas import SupportAgentState


def greeting_node(state: SupportAgentState) -> dict:
    """
    Ask for user's name - sends initial greeting if this is the first interaction.
    
    TODO:
    1. If user_name exists, return {}
    2. Return messages: [AIMessage("Hi! What's your name?")] and conversation_stage: "greeting"
    """
    # TODO: Implement greeting_node logic
    # If name is already known, skip greeting
    if state.get("user_name"):
        return {}
    return {
        "messages": [AIMessage(content="Hi! What's your name?")],
        "conversation_stage": "greeting"
    }


def identify_issue_node(state: SupportAgentState) -> dict:
    """
    Extract user name and ask for issue.
    
    TODO:
    1. Extract name from last HumanMessage if user_name missing
    2. If name extracted, return user_name, messages, conversation_stage: "identifying"
    3. If user_name exists but issue_type missing and last message is AI, ask for issue
    4. Otherwise return {}
    """
    # TODO: Implement identify_issue_node logic
    messages = state.get("messages", [])
    user_name = state.get("user_name")

    # Extract name from last HumanMessage if user_name is not yet known
    if not user_name:
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                extracted_name = msg.content.strip()
                return {
                    "user_name": extracted_name,
                    "messages": [AIMessage(content=f"Thanks, {extracted_name}! What issue can I help you with today?")],
                    "conversation_stage": "identifying"
                }
        return {}

    # If user_name exists but issue hasn't been asked yet, prompt for it
    if not state.get("issue_type") and messages and isinstance(messages[-1], AIMessage):
        return {
            "messages": [AIMessage(content=f"Hi {user_name}! What issue can I help you with today?")],
            "conversation_stage": "identifying"
        }

    return {}


def resolve_node(state: SupportAgentState) -> dict:
    """
    Identify issue type and provide acknowledgment.
    
    TODO:
    1. If issue_type missing, get last HumanMessage
    2. Identify issue: "order" if "order" in content, "refund" if "refund" in content, else "other"
    3. Return issue_type, messages, conversation_stage: "resolved"
    4. Otherwise return {}
    """
    # TODO: Implement resolve_node logic
    # Skip if issue is already identified
    if state.get("issue_type"):
        return {}

    # Only classify an issue once the user's name is already known AND the
    # conversation was previously waiting for an issue description.
    # We detect this by checking that the second-to-last message (the AI
    # prompt asking for the issue) came from a prior turn — i.e. the last
    # AI message before the current HumanMessage asks about the issue.
    # If user_name is missing it means we are still on the naming turn, so skip.
    if not state.get("user_name"):
        return {}

    messages = state.get("messages", [])

    # Walk backwards: find the last HumanMessage and the AI message before it.
    # If the AI message before the last HumanMessage is the issue-prompt, we
    # know the user's current message is their issue description.
    last_human_idx = None
    for i in range(len(messages) - 1, -1, -1):
        if isinstance(messages[i], HumanMessage):
            last_human_idx = i
            break

    if last_human_idx is None:
        return {}

    # Check the AI message immediately before the last HumanMessage
    ai_before = None
    for i in range(last_human_idx - 1, -1, -1):
        if isinstance(messages[i], AIMessage):
            ai_before = messages[i]
            break

    # The "What issue..." prompt is set by identify_issue_node in a previous turn.
    # If the AI message before the current human turn contains the issue-prompt
    # phrase, we know this human message is the issue description.
    if ai_before is None or "what issue" not in ai_before.content.lower():
        return {}

    # Classify the issue from the last HumanMessage
    content = messages[last_human_idx].content.lower()
    if "order" in content:
        issue_type = "order"
    elif "refund" in content:
        issue_type = "refund"
    else:
        issue_type = "other"

    return {
        "issue_type": issue_type,
        "messages": [AIMessage(content=f"Got it! I've noted your {issue_type} issue and will help you resolve it.")],
        "conversation_stage": "resolved"
    }


def build_graph(checkpointer=None):
    """
    Build and compile the support agent graph.
    
    TODO:
    1. Create StateGraph with SupportAgentState
    2. Add nodes: "greeting", "identify_issue", "resolve"
    3. Add edges: greeting -> identify_issue -> resolve
    4. Set entry point: "greeting"
    5. Set finish point: "resolve"
    6. Use MemorySaver if checkpointer is None
    7. Compile and return graph
    """
    # TODO: Implement build_graph function
    # Use MemorySaver for in-memory checkpointing if none provided
    if checkpointer is None:
        checkpointer = MemorySaver()

    graph = StateGraph(SupportAgentState)

    # Register conversation nodes
    graph.add_node("greeting", greeting_node)
    graph.add_node("identify_issue", identify_issue_node)
    graph.add_node("resolve", resolve_node)

    # Wire up the linear conversation flow
    graph.add_edge("greeting", "identify_issue")
    graph.add_edge("identify_issue", "resolve")

    graph.set_entry_point("greeting")
    graph.set_finish_point("resolve")

    return graph.compile(checkpointer=checkpointer)