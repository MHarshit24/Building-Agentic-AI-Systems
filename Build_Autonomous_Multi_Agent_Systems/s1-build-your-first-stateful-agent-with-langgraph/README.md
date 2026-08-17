# Quick Commerce Support Agent

## Project Context

You're building a Quick Commerce Support Agent, an AI-powered system that helps customers with order issues, refunds, and general inquiries through multi-turn conversations.

This practice focuses on building stateful agents with LangGraph — implementing state management, graph nodes, and checkpointing to maintain conversation context across multiple interactions. You'll learn how to create state schemas with reducers, build graph nodes that process conversation state, and implement REST APIs that persist conversation history using thread-based checkpointing.

## Problem Statement

Build a multi-turn conversational support agent using LangGraph with checkpointing capabilities. The system must support stateful conversations, extract user information, identify issue types, and maintain conversation context across multiple API calls. You need to implement state schemas, graph nodes for conversation flow, and FastAPI endpoints that handle thread-based state persistence.

You will complete multiple implementation tasks to build this support agent:

## Task 1 — Define State and API Schemas

### Goal

Build the foundational data structures for state management and API request/response models.

### Requirements

1. Implement `SupportAgentState` TypedDict with messages, user_name, issue_type, conversation_stage
2. Implement `MessageRequest` Pydantic model with message and thread_id
3. Implement `MessageResponse` Pydantic model with messages, user_name, issue_type, conversation_stage, thread_id
4. Implement `ConversationStateResponse` Pydantic model with thread_id, user_name, issue_type, conversation_stage, message_count

**File:** `schemas.py`

### Implementation Details

**SupportAgentState** is defined as a `TypedDict` — a lightweight typing construct that LangGraph uses to track what fields the graph state holds. The `messages` field is wrapped in `Annotated[list, add_messages]`, where `add_messages` is a LangGraph reducer that automatically appends new messages to the existing list rather than replacing it. This is what makes multi-turn conversation history accumulate correctly across invocations. The remaining three fields — `user_name`, `issue_type`, and `conversation_stage` — are plain strings with no reducer, so each node's return value overwrites whatever was previously stored.

**MessageRequest** uses Pydantic's `BaseModel` to validate and parse incoming JSON. The `message` field is required, while `thread_id` is `Optional[str]` defaulting to `None` — this allows clients to omit the thread ID on the first message and let the server generate one.

**MessageResponse** and **ConversationStateResponse** are both response models. Fields that may not yet exist at certain conversation stages — such as `user_name` and `issue_type` before they have been captured — are marked `Optional` with a default of `None`. This prevents Pydantic validation errors when the graph has only partially progressed through the conversation flow. `messages` in `MessageResponse` is typed as `List[dict]` because LangChain message objects are serialised into plain `{"type": ..., "content": ...}` dicts before being returned to the client.

## Task 2 — Implement Graph Nodes and Builder

### Goal

Build graph nodes that handle conversation flow and create the compiled graph with checkpointing.

### Requirements

1. Implement `greeting_node()` to send greeting if user_name missing
2. Implement `identify_issue_node()` to extract name and ask for issue
3. Implement `resolve_node()` to identify issue type and acknowledge
4. Implement `build_graph()` to create graph with nodes, edges, entry/finish points, and checkpointing

**File:** `graph.py`

### Implementation Details

**greeting_node** is the entry point of every graph invocation. Its only responsibility is to send the initial greeting if the conversation has not yet captured a name. It checks `state.get("user_name")` — if a name is already present (i.e. this is a returning conversation), it immediately returns an empty dict `{}` so that no state is changed and no duplicate greeting is sent. If `user_name` is absent, it returns an `AIMessage` with the greeting text alongside `conversation_stage: "greeting"`. Returning an empty dict rather than `None` is important — LangGraph merges node return values into the state, and `None` would cause a runtime error.

**identify_issue_node** handles two distinct situations depending on what the state contains when the node runs. If `user_name` is missing, it scans the message list in reverse to find the most recent `HumanMessage` and treats its content as the user's name. It then returns the extracted name, a thank-you `AIMessage` asking for the issue description, and sets `conversation_stage` to `"identifying"`. If `user_name` is already present but `issue_type` has not yet been set, and the last message in the history is an `AIMessage` (meaning the agent spoke last and is waiting for the user), it sends another prompt for the issue. This second branch handles edge cases where a conversation was resumed mid-flow. In all other situations it returns `{}` to leave the state unchanged.

**resolve_node** is the trickiest node because it must distinguish between a "name turn" and an "issue turn" — both of which arrive as `HumanMessage` objects. The node uses two guards to ensure it only fires at the right moment. First, if `issue_type` is already set, it returns `{}` immediately to avoid overwriting a previously classified issue. Second, it inspects the message history to find the `AIMessage` that immediately preceded the current `HumanMessage`. Only if that AI message contains the phrase "what issue" — which is the exact prompt sent by `identify_issue_node` in the previous turn — does it proceed to classify. This design relies on message history as a reliable signal of conversational context rather than `conversation_stage`, because `conversation_stage` reflects the pre-invocation checkpoint state and would not yet reflect updates made by earlier nodes within the same invocation. Once classification proceeds, the node checks the `HumanMessage` content case-insensitively for the keywords "order" and "refund", falling back to "other", and returns the result alongside a confirmation `AIMessage` and `conversation_stage: "resolved"`.

**build_graph** wires all three nodes into a `StateGraph` and compiles it with a checkpointer. The graph follows a strict linear topology: `greeting → identify_issue → resolve`. The entry point is set to `"greeting"` so every invocation starts there, and the finish point is set to `"resolve"` so the graph terminates after the resolve node runs. If no external checkpointer is passed in, a `MemorySaver` instance is created — this stores conversation snapshots in process memory keyed by `thread_id`. Compiling the graph with a checkpointer is what enables LangGraph to restore the previous state at the start of each `invoke` call, making multi-turn conversations possible without any database.

## Task 3 — Implement FastAPI Endpoints

### Goal

Build REST API endpoints that process chat messages and retrieve conversation state with checkpointing support.

### Requirements

1. Implement `get_graph()` singleton function
2. Implement `POST /chat` endpoint to process messages with checkpointing
3. Implement `GET /conversation/{thread_id}` endpoint to retrieve conversation state

**File:** `main.py`

### Implementation Details

**get_graph** implements the singleton pattern using a module-level `_graph` variable initialised to `None`. On the first call, it invokes `build_graph()` and stores the result in `_graph`. Every subsequent call returns the same cached instance. This matters because `MemorySaver` is stateful — it holds all conversation checkpoints in memory. If a new graph were created on each request, every `thread_id` would lose its history between calls.

**POST /chat** is the main conversation endpoint. If the incoming `MessageRequest` does not include a `thread_id`, the endpoint generates one using `uuid.uuid4()` so the client can reference the same conversation in future requests. It then builds a LangGraph config dict in the form `{"configurable": {"thread_id": thread_id}}` — this is the standard LangGraph pattern for associating an invocation with a specific checkpoint. Before invoking the graph, it calls `graph.get_state(config)` to peek at the existing checkpoint. Whether this is a first message or a follow-up, the graph is invoked with the new `HumanMessage` wrapped in the state dict. After invocation, the returned LangChain message objects are serialised into plain `{"type": ..., "content": ...}` dicts because Pydantic cannot automatically serialise LangChain message types. The full `MessageResponse` is then returned, including all state fields and the `thread_id` so the client knows which thread to use on the next turn. Any unexpected exception is caught and re-raised as an `HTTPException` with a 500 status code.

**GET /conversation/{thread_id}** is a read-only endpoint for inspecting saved conversation state. It calls `graph.get_state(config)` with the provided `thread_id` and checks whether `state.values` is populated. If it is empty or `None`, the thread does not exist in the checkpoint store and a 404 is raised. Otherwise, it reads the state fields directly and computes `message_count` as the length of the `messages` list. This endpoint is useful for debugging and for clients that need to resume a conversation after a page reload without re-sending their last message. `HTTPException` is re-raised as-is inside the except block so that 404s are not accidentally swallowed by the generic 500 handler.

## Evaluation Criteria

Ensure you evaluate your solution against the below criteria:

1. **State Schema Definition**: SupportAgentState TypedDict is defined with messages (Annotated[list, add_messages]), user_name, issue_type, and conversation_stage fields. All Pydantic models (MessageRequest, MessageResponse, ConversationStateResponse) are properly defined with correct field types and optional/required annotations. All models can be instantiated and serialized to JSON.

2. **greeting_node Implementation**: greeting_node function has correct signature (state: SupportAgentState) -> dict. Function checks if user_name exists in state and returns empty dict {} when it does. Returns dict with messages containing AIMessage("Hi! What's your name?") and conversation_stage: "greeting" when user_name is missing. Function does not return None.

3. **identify_issue_node Implementation**: identify_issue_node function has correct signature (state: SupportAgentState) -> dict. Function accesses state messages and extracts name from last HumanMessage when user_name is missing. Returns dict with user_name, AIMessage with thanks message, and conversation_stage: "identifying" when name is extracted. Returns empty dict {} when conditions are not met. Function does not return None.

4. **resolve_node Implementation**: resolve_node function has correct signature (state: SupportAgentState) -> dict. Function checks if issue_type is missing and accesses last HumanMessage from state. Identifies issue type correctly: "order" if "order" in content (case-insensitive), "refund" if "refund" in content (case-insensitive), else "other". Returns dict with issue_type, AIMessage with acknowledgment, and conversation_stage: "resolved". Returns empty dict {} when issue_type already exists. Function does not return None.

5. **build_graph Implementation**: build_graph function has correct signature (checkpointer=None). Creates StateGraph with SupportAgentState schema. Adds all three nodes: "greeting", "identify_issue", "resolve". Connects nodes with edges: greeting -> identify_issue -> resolve. Sets entry point to "greeting" and finish point to "resolve". Uses MemorySaver() if checkpointer is None. Compiles graph with checkpointer and returns compiled graph. Function does not return None.

6. **get_graph Singleton Implementation**: get_graph() function implements singleton pattern correctly by checking _graph global variable and caching build_graph() result. Function returns the same graph instance on subsequent calls. Function does not return None.

7. **POST /chat Endpoint Implementation**: POST /chat endpoint is decorated with @app.post("/chat", response_model=MessageResponse) and accepts MessageRequest parameter. Endpoint handles thread_id generation using uuid.uuid4() if not provided in request. Creates config dict with thread_id: {"configurable": {"thread_id": thread_id}}. Gets current state from graph using graph.get_state(config). Handles first message (initializes state) vs subsequent messages (invokes with HumanMessage). Converts messages to dict format with "type" and "content" keys. Returns MessageResponse with all state fields (messages, user_name, issue_type, conversation_stage, thread_id). Endpoint handles exceptions gracefully with HTTPException.

8. **GET /conversation/{thread_id} Endpoint Implementation**: GET /conversation/{thread_id} endpoint is decorated with @app.get("/conversation/{thread_id}", response_model=ConversationStateResponse) and accepts thread_id path parameter. Endpoint creates config dict with thread_id: {"configurable": {"thread_id": thread_id}}. Retrieves state from checkpoint using graph.get_state(config). Raises HTTPException(status_code=404) when state.values is None (conversation not found). Returns ConversationStateResponse with all state fields (thread_id, user_name, issue_type, conversation_stage, message_count). Endpoint handles exceptions gracefully.