# Banking Customer Support ReAct Agent 

## Project Context

You're building a Banking Customer Support ReAct Agent, an AI-powered system that helps bank customers with account queries by reactively using tools step by step. The system uses a ReAct (Reasoning + Acting) pattern to reason about customer queries, decide which tools to use, execute them, observe results, and provide clear answers.

This practice focuses on building ReAct agents with LangGraph — implementing reasoning-action-observation loops, tool integration, and conditional routing based on tool calls vs final answers. You'll learn how to create state schemas with ReAct tracking fields, build reasoning nodes that generate explicit decision traces, implement tool execution nodes, design prompts that elicit structured reasoning, and implement loop control with completion criteria.

## Problem Statement

Build a ReAct-based customer support agent for a bank that answers user queries by looking up account information, performing calculations when needed, and producing clear answers based on tool observations. You need to implement state schemas with ReAct tracking fields, reasoning prompts, graph nodes for reasoning and tool execution, conditional routing based on tool calls vs final answers, and FastAPI endpoints that process customer queries.

You will complete multiple implementation tasks to build this ReAct agent:

## Task 1 — Define State Schema

### Goal

Build the foundational data structure for ReAct state management with tracking fields for thoughts, actions, and observations.

### Requirements

1. Import `TypedDict`, `List`, `Dict`, `Annotated` from `typing` and `operator` module
2. Define `CustomerSupportState` TypedDict with:
   - `messages: Annotated[List, operator.add]` - Conversation history
   - `thought_history: Annotated[List[str], operator.add]` - Agent's reasoning traces
   - `action_log: Annotated[List[Dict], operator.add]` - Tools called and their inputs
   - `observation_results: Annotated[List[str], operator.add]` - Tool outputs
   - `task_complete: bool` - Termination flag

**File:** `state.py`

## Task 2 — Create Reasoning Prompt

### Goal

Design a system prompt that guides the agent through ReAct-style reasoning and tool usage.

### Requirements

1. Create `REASONING_PROMPT` string template with:
   - Role definition as bank customer support assistant
   - Context placeholders: `{thought_history}`, `{action_log}`, `{observation_results}`
   - Available tools section: `get_account_info` and `calculate` with usage instructions
   - ReAct-style loop instructions: THINK → DECIDE → Use tool → OBSERVE → Continue
   - Thinking guidelines and output format (THOUGHT, FINAL ANSWER)
   - Important notes about tool calling and step-by-step reasoning

**File:** `prompts.py`

## Task 3 — Implement Tools

### Goal

Build the tool functions that the agent will use to gather information and perform calculations.

### Requirements

1. Import `tool` decorator from `langchain_core.tools`
2. Keep the `ACCOUNT_DB` dictionary (already provided)
3. Implement `get_account_info(account_id: str) -> str`:
   - Get account from `ACCOUNT_DB` using `account_id.upper()` as key
   - Return formatted string with account type, balance (formatted with commas), and interest rate
   - Return error message if account not found
4. Implement `calculate(expression: str) -> str`:
   - Use try-except block to safely evaluate the expression using `eval()`
   - Return formatted result or error message

**File:** `tools.py`

## Task 4 — Build ReAct Graph

### Goal

Set up the LLM, implement graph nodes, routing logic, and construct the complete LangGraph workflow.

### Requirements

1. **Initialize LLM with Tools:**
   - Initialize `AzureChatOpenAI` with credentials from environment variables
   - Set `temperature=0` and default model to "gpt-4o-mini"
   - Bind tools `[get_account_info, calculate]` to the LLM using `.bind_tools()`

2. **Implement Reasoning Node:**
   - Implement `reasoning_node(state: CustomerSupportState)` function that:
     - Formats `REASONING_PROMPT` with state fields (thought_history, action_log, observation_results)
     - Prepends `SystemMessage` with formatted prompt to messages
     - Invokes LLM with messages
     - Extracts thought from response if present, appends to `state["thought_history"]`, and logs it
     - Sets `state["task_complete"] = True` if "FINAL ANSWER" in response content
     - Returns `{"messages": [response]}`

3. **Implement Tool Execution Node:**
   - Implement `tool_execution_node(state: CustomerSupportState)` function that:
     - Gets last message from state and checks for `tool_calls`
     - Loops through all `tool_calls`:
       - Extracts tool name and args, creates action dict, appends to `state["action_log"]`, and logs action
       - Executes appropriate tool (get_account_info or calculate)
       - Appends result to `state["observation_results"]` and logs observation
       - Creates `ToolMessage` with result and `tool_call_id`
     - Returns `{"messages": tool_messages}`

4. **Implement Loop Condition:**
   - Implement `should_continue(state: CustomerSupportState) -> str` function that:
     - Returns "end" if `task_complete` is True or "FINAL ANSWER" in last message content
     - Returns "continue" if last message has `tool_calls` (check max 6 iterations)
     - Returns "continue" if last message is a `ToolMessage`
     - Returns "end" as default fallback

5. **Build the Graph:**
   - Create `StateGraph` with `CustomerSupportState`
   - Add nodes: "reasoning" and "tool_execution"
   - Set entry point to "reasoning"
   - Add conditional edges from "reasoning" using `should_continue` function:
     - "continue" -> "tool_execution"
     - "end" -> END
   - Add edge from "tool_execution" back to "reasoning"
   - Compile the graph

**File:** `main.py`

## Task 5 — Implement FastAPI Endpoint

### Goal

Build REST API endpoint that processes customer queries and returns final answers.

### Requirements

1. Build graph using the graph construction code (from Task 4)
2. Implement `POST /support/query` endpoint that:
   - Accepts `query: str` parameter
   - Initializes state with messages, thought_history, action_log, observation_results, task_complete
   - Invokes `react_graph` with the state
   - Extracts final answer from result messages (find "FINAL ANSWER" and clean up formatting)
   - Logs query and final answer
   - Returns `{"answer": final_answer}`

**File:** `main.py`

## Evaluation Criteria

Ensure you evaluate your solution against the below criteria:

1. **State Schema Definition**: CustomerSupportState TypedDict is defined with messages (Annotated[List, operator.add]), thought_history (Annotated[List[str], operator.add]), action_log (Annotated[List[Dict], operator.add]), observation_results (Annotated[List[str], operator.add]), and task_complete (bool) fields. All imports (TypedDict, List, Dict, Annotated, operator) are correctly included.

2. **LLM Initialization**: AzureChatOpenAI is initialized with all required parameters from environment variables (api_key, azure_endpoint, model with default, api_version, temperature=0). Tools [get_account_info, calculate] are bound to LLM using .bind_tools().

3. **Reasoning Node Implementation**: reasoning_node function has correct signature accepting state parameter. Function formats REASONING_PROMPT with state fields, gets messages from state, prepends SystemMessage with prompt, invokes LLM, extracts thought if present, appends to thought_history, logs thought, checks for FINAL ANSWER and sets task_complete, and returns {"messages": [response]}. Function does not return None or empty dict.

4. **Tool Execution Node Implementation**: tool_execution_node function has correct signature accepting state parameter. Function gets last message, checks for tool_calls, loops through all tool_calls, extracts tool_name and tool_args, creates action dict, appends to action_log, logs action, executes appropriate tool, appends result to observation_results, logs observation, creates ToolMessage with correct tool_call_id, and returns {"messages": tool_messages}. Function handles all tool_calls, not just the first one.

5. **Loop Condition Implementation**: should_continue function has correct signature accepting state parameter and returns str. Function checks task_complete flag, checks for FINAL ANSWER in content, checks for tool_calls and max iterations, checks for ToolMessage, and returns appropriate string ("continue" or "end"). Function handles all edge cases correctly.

6. **Graph Construction Implementation**: StateGraph is created with CustomerSupportState schema. All nodes are registered (reasoning, tool_execution). Entry point is set to "reasoning". Conditional edges are added from "reasoning" with should_continue function and proper mapping. Edge is added from "tool_execution" back to "reasoning". Graph is compiled correctly. Function does not return None.


---

## Implementation Notes

### Environment & Configuration

Environment variables are loaded from the root `.env` file located at `Building_Agentic_AI_Systems/` (two levels up from `main.py`) using a path-safe fallback pattern — if the root `.env` is not found at the expected path, `load_dotenv()` is called without arguments so the server still starts. The variables used are `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_VERSION`, and `AZURE_OPENAI_LLM_DEPLOYMENT`. The deployment name is resolved with a two-level fallback: `AZURE_OPENAI_LLM_DEPLOYMENT` is tried first, then `AZURE_OPENAI_MODEL`, and finally the hardcoded default `"gpt-4o-mini"`, matching the requirement specified in the task. There is no project-level `.env` in this assignment directory.

### Task 1 — State Schema

`CustomerSupportState` is a `TypedDict` with five fields. The four list fields — `messages`, `thought_history`, `action_log`, and `observation_results` — are all wrapped in `Annotated` with `operator.add` as the reducer. This is essential for LangGraph: it means each node returns a partial update and LangGraph appends to the existing list rather than overwriting it, which is how the thought history and action log accumulate correctly across the ReAct loop. `task_complete` is a plain `bool` that acts as the termination signal.

### Task 2 — Reasoning Prompt

`REASONING_PROMPT` in `prompts.py` serves as the system message injected at the start of every LLM call inside the reasoning node. It defines the agent's role, lists both tools with their argument signatures and when to use them, and embeds the current ReAct state via three placeholders (`{thought_history}`, `{action_log}`, `{observation_results}`) so the model always has full context of what it has already done. The output format section instructs the model to prefix reasoning lines with `THOUGHT:` and to end with `FINAL ANSWER:` — both of which are parsed programmatically by the reasoning node and the endpoint respectively. A key instruction tells the model not to repeat tool calls already present in the action log, which prevents redundant API calls in multi-step queries.

### Task 3 — Tools

Both tools use the `@tool` decorator from `langchain_core.tools`, which registers them with LangChain's tool-calling infrastructure and makes them bindable to the LLM. `get_account_info` normalises the account ID to uppercase before the lookup so queries like `"acc001"` work correctly. The balance is formatted with Python's `:,` specifier to produce comma-separated output. `calculate` wraps `eval()` in a try-except so malformed expressions return a readable error string rather than crashing the node.

### Task 4 — ReAct Graph

**LLM initialisation:** `AzureChatOpenAI` is instantiated with `temperature=0` to ensure deterministic, factual responses — important for a customer-facing support agent. `.bind_tools()` is called immediately after, attaching both tools to the model so the LLM can emit structured tool-call objects in its responses.

**Reasoning node:** On every invocation, the node formats `REASONING_PROMPT` with the current state lists, prepends it as a `SystemMessage`, and invokes the bound LLM. If the response content starts with `"THOUGHT"`, the thought text is extracted (only the first line, in case the model continues with a tool call on the next line), appended to `thought_history`, and logged. If the response contains `"FINAL ANSWER"`, `task_complete` is set to `True` to signal the loop to stop cleanly on the next routing check.

**Tool execution node:** The node reads all `tool_calls` from the last message (not just the first) so the LLM can batch multiple tool calls in a single turn — this is what allowed Test 4 to fetch ACC001 and ACC003 simultaneously in one reasoning step. Each tool call produces a `ToolMessage` keyed by `tool_call_id`, which is required by the OpenAI tool-calling protocol so the model can match observations back to the correct call.

**Loop condition:** `should_continue` is evaluated after every reasoning node invocation. It checks termination signals in priority order: `task_complete` flag first, then `"FINAL ANSWER"` in content, then presence of `tool_calls` (with a hard cap of 6 iterations to prevent infinite loops), then whether the last message is a `ToolMessage` (which means control should return to reasoning). The default fallback returns `"end"` to ensure the graph always terminates.

**Graph wiring:** The graph has two nodes (`reasoning` and `tool_execution`) with a conditional edge out of `reasoning` driven by `should_continue`, and an unconditional edge from `tool_execution` back to `reasoning`. This creates the classic ReAct cycle: reason → act → observe → reason → … → final answer.

### Task 5 — FastAPI Endpoint

The `POST /support/query` endpoint initialises a fresh state dict on every request with empty lists for all ReAct tracking fields and `task_complete` set to `False`. After the graph finishes, the endpoint scans messages in reverse order to find the last one containing `"FINAL ANSWER"`, splits on that marker, and strips any lines beginning with `THOUGHT:` or `ACTION:` that the model may have included before the answer text. If no `FINAL ANSWER` is found (edge case safety net), it falls back to the last message's content. Both the incoming query and the extracted final answer are logged at `INFO` level, so the terminal shows the full ReAct trace alongside clean input/output bookends.

### Verification

All four test queries were executed via Swagger UI and confirmed correct:

- Account balance lookup for ACC001 returned ₹1,50,000 with account type and interest rate correctly retrieved via `get_account_info`.
- Two-year interest calculation on ACC002 chained `get_account_info` and `calculate` across separate reasoning steps, correctly producing ₹26,000.
- Lookup of a non-existent account ACC999 returned a clear not-found message without errors.
- Interest rate comparison between ACC001 and ACC003 batched both `get_account_info` calls in a single tool execution turn, then correctly concluded the rates are equal.

Terminal logs confirmed `THOUGHT`, `ACTION`, and `OBSERVATION` entries on every query, validating that the full ReAct loop executed as intended.