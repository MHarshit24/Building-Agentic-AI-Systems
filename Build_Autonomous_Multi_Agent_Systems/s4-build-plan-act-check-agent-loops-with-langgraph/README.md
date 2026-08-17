# Market Research Agent 

## Project Context

You're building a Market Research Agent, an AI-powered system that conducts market research by gathering real data from the web, performing analysis, and generating insights. The system uses a Plan-Act-Check pattern to generate upfront execution plans, execute steps systematically, verify each step's success, and replan when failures occur.

This practice focuses on building Plan-Act-Check agents with LangGraph — implementing planning nodes that decompose tasks into executable steps, execution nodes that follow plans systematically, verification nodes that check step success, replanning nodes that adjust failed plans, and conditional routing based on verification outcomes. You'll learn how to create state schemas with plan tracking fields, build planning prompts that generate structured execution plans, implement tool execution with result capture, design verification logic that evaluates step quality, and implement replanning mechanisms that adapt when verification fails.

## Problem Statement

Build a Plan-Act-Check-based market research agent that responds to research queries by creating a multi-step execution plan, executing research steps with real web searches, verifying each step's quality, and replanning if needed. You need to implement state schemas with plan and execution tracking fields, planning prompts that decompose queries into executable steps, graph nodes for planning, execution, verification, and replanning, conditional routing based on verification status, and FastAPI endpoints that process research queries and return structured results.

You will complete multiple implementation tasks to build this Plan-Act-Check agent:


## Task 1 — Implement Tools

### Goal

Build the tool functions that the agent will use to search the web and perform calculations.

### Requirements

1. Import required modules
2. Initialize DuckDuckGoSearchRun
3. Implement `search_web` tool function
4. Implement `calculate` tool function

**File:** `tools/tools.py`

## Task 2 — Implement Planning Node

### Goal

Build a planning node that decomposes user research queries into structured, executable multi-step plans.

### Requirements

1. Import required modules
2. Implement `planning_node` that extracts user request, builds planning prompt, invokes LLM, parses JSON response, normalizes plan format, and updates state

**File:** `nodes/planner.py`

## Task 3 — Implement Execution Node

### Goal

Build an execution node that executes individual steps from the plan using tools.

### Requirements

1. Import required modules
2. Implement `execution_node` that gets current step, invokes llm_with_tools, executes tools, and stores results

**File:** `nodes/executor.py`

## Task 4 — Implement Verification Node

### Goal

Build a verification node that checks if executed steps met success criteria.

### Requirements

1. Import required modules
2. Implement `verification_node` that evaluates step results, parses verification response, handles PASS/FAIL status, and updates state

**File:** `nodes/verifier.py`

## Task 5 — Implement Replanning Node

### Goal

Build a replanning node that adjusts plans when steps fail verification.

### Requirements

1. Import required modules
2. Define `MAX_REPLANS = 2` constant
3. Implement `replanning_node` that checks replan attempts, builds replanning prompt, invokes LLM, parses revised plan, and updates state

**File:** `nodes/replanner.py`

## Task 6 — Build Plan-Act-Check Graph

### Goal

Set up the routing logic and construct the complete LangGraph workflow with conditional routing.

### Requirements

1. Import required modules
2. Define `MAX_STEPS = 10` constant
3. Implement `should_continue` routing function
4. Build StateGraph with nodes, edges, and conditional routing

**File:** `graph/graph.py`

## Task 7 — Implement FastAPI Endpoint

### Goal

Build REST API endpoint that processes research queries and returns structured results.

### Requirements

1. Import required modules
2. Create FastAPI app
3. Implement `POST /research` endpoint


**File:** `main.py`

## Evaluation Criteria

Ensure you evaluate your solution against the below criteria:

1. **Tool Implementation**: search_web function is decorated with @tool, accepts query parameter, initializes DuckDuckGoSearchRun with timeout, invokes ddg_search.invoke(query), handles empty results, handles exceptions, and returns search result string. calculate function is decorated with @tool, accepts expression parameter, uses try-except block, evaluates expression safely using eval with restricted builtins, formats result with rounding, handles exceptions, and returns formatted result string.

2. **Planning Node Implementation**: planning_node function has correct signature accepting state parameter. Function extracts user_request from state messages, builds planning prompt with tool inventory and JSON format specification, invokes llm.invoke() with SystemMessage and HumanMessage, parses JSON from response.content (handles markdown fences), normalizes plan format (handles dict and string items), limits plan to 5 steps, updates state with plan and initialization values, and returns updated state. Function handles JSONDecodeError with fallback plan.

3. **Execution Node Implementation**: execution_node function has correct signature accepting state parameter. Function performs safety checks, gets current step information from plan, creates execution message, invokes llm_with_tools.invoke() with messages, appends response to messages, handles no tool call case, executes tool (search_web or calculate), stores execution result in execution_results, adds ToolMessage to messages, and returns updated state. Function handles all edge cases correctly.

4. **Verification Node Implementation**: verification_node function has correct signature accepting state parameter. Function performs safety checks, gets step info and execution result, builds verification prompt with expected vs actual comparison, invokes llm.invoke() for evaluation, parses JSON verification result (handles markdown fences), stores verification status, handles FAIL status (sets needs_replanning), handles PASS status (advances step or marks complete), and returns updated state. Function handles JSONDecodeError with default PASS status.

5. **Routing Function Implementation**: should_continue function has correct signature accepting state parameter and returns str. Function checks task_complete flag, checks max steps safety limit, checks needs_replanning flag, and returns appropriate string ("complete", "replan", or "execute"). Function handles all edge cases correctly.

6. **Graph Construction Implementation**: StateGraph is created with MarketResearchState schema. All nodes are registered (planner, executor, verifier, replanner). Entry point is set to "planner". Edges are added correctly (planner->executor, executor->verifier, replanner->executor). Conditional edges are added from "verifier" with should_continue function and proper mapping (execute->executor, replan->replanner, complete->END). Graph is compiled correctly and stored in app_graph variable.


---

## Implementation Notes

This section documents how each task was implemented, the key decisions made along the way, and the known limitations of the resulting system.

### Environment Configuration

This project does not use a project-level `.env` file. All Azure OpenAI credentials are loaded from the root `.env` at the top of the workspace, two directory levels above `llm.py`. The loader checks whether the root `.env` exists before attempting to load it, falling back to a plain `load_dotenv()` call if the path cannot be resolved, so the script does not hard-fail if the directory structure changes. Variable names follow a personal-name-first, assignment-name-fallback convention: the LLM deployment name is read from a personal environment variable first, falling back to the assignment's expected variable name if the personal one is not set. The API key, endpoint, and API version use the same variable names in both the personal and assignment conventions, so no fallback was needed for those three.

### Tools (Task 1)

The DuckDuckGo search tool is initialized once at module load time with a ten-second timeout to prevent the agent from hanging indefinitely on a slow or unresponsive search request. The search tool wraps its invocation in a try/except block, returning a clear message when the search returns no results and a descriptive error message if the underlying search call raises an exception, rather than letting the exception propagate up through the LangGraph node and crash the whole workflow. The calculate tool evaluates the given expression using Python's eval with both builtins and the local/global namespace restricted, so the expression cannot access arbitrary Python functions or modules, only basic arithmetic. The result is rounded to two decimal places and formatted as a result string; calculation failures are caught and returned as a descriptive error string rather than raised as exceptions.

During testing, an additional environment dependency was discovered: the installed version of langchain-community requires a separate `ddgs` package (the renamed successor to the older `duckduckgo-search` package) to back the DuckDuckGoSearchRun tool. This is not something the assignment code controls, but it is worth noting as a one-time `pip install ddgs` setup step for anyone re-running this project from a fresh environment.

### Planning Node (Task 2)

The planning node extracts the original user request from the first message in state, then prompts the LLM with a system message describing the expected JSON array format (each item carrying step, action, tool, and expected_output fields) and a human message containing the actual request. The LLM is instructed to choose between the two available tools, search_web and calculate, for each step. The response is parsed as JSON after stripping markdown code fences if the model wrapped its output in them. Each plan item is normalized into a consistent dictionary shape regardless of whether the LLM returned a string or a partially-formed dictionary, and the plan is capped at five steps even if the model produced more. If the JSON parse fails, a single-step fallback plan is constructed directly from the user's request so the workflow can still proceed rather than crashing at the very first node.

### Execution Node (Task 3)

The execution node looks up the current step from the plan using the current_step counter, builds an instruction message describing the action and the tool to use, and invokes the tool-bound LLM with the full conversation history plus this new instruction. If the model responds with a tool call, the node dispatches to either the calculate tool or the search_web tool based on the tool call's name and records the result. If the model responds without any tool call, its plain text response is recorded directly as the execution result instead, so a step is never silently dropped.

One refinement was made beyond the bare TODO instructions: the instruction message sent to the LLM was extended to include a short excerpt of the previous step's result whenever one exists, truncated to 500 characters. This was added after testing surfaced multi-step plans where a later step needed a number produced by an earlier step (for example, searching for a population figure in one step and then calculating a percentage of it in the next). Without this addition, the calculate tool had no way to know what number to use, since it only receives whatever expression the LLM decides to pass it. This change is a single-line addition to the message construction and does not alter the function's structure, its required behavior, or any other part of the codebase.

### Verification Node (Task 4)

The verification node retrieves the step that was just executed and its result, then asks the LLM to judge whether the result satisfies the step's expected_output, returning a PASS or FAIL status with a short reason. The response is parsed in the same fences-stripped, JSON-first manner as the planning node. If parsing fails, the node defaults to PASS rather than FAIL, since defaulting to FAIL on every parse error would otherwise force every malformed verifier response into an unnecessary replanning cycle. On a FAIL result, the needs_replanning flag is set so the graph routes to the replanner next. On a PASS result, the replan_attempts counter is reset to zero and the workflow either advances to the next step or marks the whole task complete if the verified step was the last one in the plan.

### Replanning Node (Task 5)

The replanning node increments the replan_attempts counter first, then checks it against MAX_REPLANS. If the cap has been exceeded, the node gives up on revising the current step, clears the needs_replanning flag, and advances the workflow past the failed step (or marks the task complete if it was the final step), ensuring the graph can never loop on a single step indefinitely. If attempts remain, the node prompts the LLM with the original plan, the specific step that failed, the verifier's stated reason for the failure, and a truncated excerpt of the failed execution result, asking for a revised JSON plan. The revised plan is normalized the same way as in the planning node and capped at five steps. If the LLM's revised plan cannot be parsed as JSON, the node falls back to simplifying the failed step's action into a generic search instruction rather than leaving the plan unusable.

### Routing and Graph Construction (Task 6)

The should_continue function checks, in order, whether the task is already marked complete, whether the step counter has exceeded the MAX_STEPS safety limit (forcing completion if so), whether the verifier flagged a need to replan, and otherwise defaults to continuing execution. The graph itself wires the four nodes together with planner as the entry point, a direct edge from planner to executor, a direct edge from executor to verifier, a direct edge from replanner back to executor, and a conditional edge out of verifier driven by should_continue that branches to executor, replanner, or the END node.

A state-management detail surfaced during testing that is worth recording here. The state schema marks messages, execution_results, and verification_status as Annotated lists using operator.add as their reducer. LangGraph appends whatever a node returns under one of these keys onto the existing list automatically; it does not replace the list. Early versions of the execution and verification nodes were returning the entire accumulated list (the existing list plus the new item) rather than just the new item, which caused LangGraph to append that whole accumulated list back onto itself on every pass through the graph, producing rapidly multiplying duplicate entries in execution_results and verification_status after only a few loop iterations. All four nodes were corrected to return only the new item(s) for these additive fields, and to return plain dictionaries containing only the keys each node actually changes, rather than returning the full state object on every call. This is consistent with the TODO's intent of returning state, since LangGraph treats a partial dictionary return as a state update in exactly the same way.

### FastAPI Endpoint (Task 7)

The /research endpoint validates that the query string is not empty or whitespace-only before doing any work, then constructs the initial state with an empty plan, a current_step of one, empty result and verification lists, and all control flags cleared. The graph is invoked inside a worker thread via asyncio.to_thread so the synchronous LangGraph call does not block the FastAPI event loop, wrapped in asyncio.wait_for with a timeout. The timeout was raised from an initial 60 seconds to 180 seconds after testing showed that live web searches across a multi-step plan, plus the LLM calls for planning, verification, and any replanning, can comfortably exceed one minute even for a single research query. Timeout and general exceptions are each caught separately and returned as structured error responses rather than allowing the request to fail with an unhandled exception.

### Known Limitations

The calculate tool only ever returns a bare numeric result string; it cannot explain its own reasoning or restate the inputs it used. When a planner-generated step asks for an explanation alongside a calculation (for example, asking the calculate step to also state which population figure was used), the verifier will correctly judge that expectation as unmet, since the tool structurally cannot provide it. This is a mismatch between what the planning prompt sometimes promises and what the calculate tool is capable of delivering, rather than a defect in the execution or verification logic itself.

Relatedly, when a calculation step fails verification and gets replanned, the LLM constructing the next attempt's instruction message has access to the full conversation history, including the previous (incorrect) execution result. In a small number of observed test runs, this caused the replanned calculation to drift further from the correct answer on each subsequent attempt rather than converging on it, since the model was reasoning over an increasingly noisy context rather than the original search data alone. The MAX_REPLANS cap prevents this from looping indefinitely, and the workflow always terminates and reports task_complete as true, but the final numeric result in such cases is not guaranteed to be accurate. Resolving this fully would require either having the calculate tool accept and echo back its reasoning, or restructuring how context is passed into the executor during replanning attempts, both of which go beyond what this assignment's TODOs specify and were left out to avoid expanding the implementation past the stated requirements.

Web search results returned by DuckDuckGo are unstructured snippet text rather than clean, single-fact answers, so steps that depend on extracting one specific figure (such as a population count) from a search result occasionally pull in a different figure than intended when multiple similar numbers appear close together in the returned snippets. This is a function of the underlying search tool's output format and is not something the agent's planning, execution, or verification logic can fully control.