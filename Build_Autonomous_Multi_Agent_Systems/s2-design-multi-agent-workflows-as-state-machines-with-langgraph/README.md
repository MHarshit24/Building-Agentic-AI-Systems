# Multi-Agent Loan Application Assessment System

## Project Context

You're building a Multi-Agent Loan Application Assessment System, an AI-powered workflow that processes loan applications through specialized reviewer agents. The system uses LLM-based triage to classify loan types and routes applications to appropriate reviewers, with parallel processing for complex assessments.

This practice focuses on building multi-agent workflows with LangGraph — implementing conditional routing (LO1) and parallel execution (LO2). You'll learn how to create state schemas with reducers for parallel state merging, build graph nodes that process loan applications, implement conditional routing based on state, and execute parallel tasks using fork-join patterns.

## Problem Statement

Build a multi-agent loan application assessment workflow using LangGraph with conditional routing and parallel execution capabilities. The system must support LLM-based loan type classification, route to specialized reviewer agents based on loan type, execute parallel reviews for home loans, and aggregate findings into a final decision report. You need to implement state schemas with parallel state merging, graph nodes for different loan reviewers, conditional routing functions, and FastAPI endpoints that process loan applications.

You will complete multiple implementation tasks to build this assessment system:

## Task 1 — Define State Schema

### Goal

Build the foundational data structure for state management with support for parallel state merging.

### Requirements

1. mport TypedDict, Annotated, and operator
2. Define LoanApplicationState with loan_type, applicant_info, mergeable findings, and final_decision

**File:** `state/loan_state.py`

### Implementation

`LoanApplicationState` is defined as a `TypedDict` with four fields. `loan_type` and `final_decision` are plain strings, and `applicant_info` is a plain dict holding all request fields passed in from the API. The `findings` field is declared as `Annotated[list, operator.add]` — this is the critical design choice that makes parallel execution work. When two nodes (like `credit_score_reviewer` and `property_assessor`) both return a `findings` key simultaneously, LangGraph uses the `operator.add` reducer to merge the two lists by concatenation rather than overwriting one with the other.

## Task 2 — Implement Triage Agent

### Goal

Build an LLM-based agent that classifies loan applications into different types.

### Requirements

1. Create get_llm() for AzureChatOpenAI
2. Error if env vars missing
3. Classify loan_purpose → home/personal/auto, validate, update state

**File:** `nodes/triage_agent.py`

### Implementation

A `get_llm()` helper is defined separately from `triage_agent` to keep credential loading and LLM construction isolated. It loads the root `.env` from `Building_Agentic_AI_Systems/` using `Path(__file__).resolve().parents[4]`, with a fallback to `load_dotenv()` if the file is not found. The primary variable for the deployment name is `AZURE_OPENAI_LLM_DEPLOYMENT`, with `AZURE_OPENAI_DEPLOYMENT_NAME` as a fallback via a nested `os.getenv` call. A `ValueError` is raised immediately if any of the four required variables are missing, so misconfiguration surfaces at startup rather than silently failing mid-request.

The `triage_agent` function extracts `loan_purpose` from `state["applicant_info"]` and sends it to the LLM with a tightly scoped prompt that asks for exactly one word — home, personal, or auto. The raw response is stripped and lowercased before validation. If the LLM returns anything outside those three values, it defaults to `"personal"`. The classified type is written to `state["loan_type"]` and the full updated state is returned so LangGraph can pass it downstream.

## Task 3 — Implement Routing Function

### Goal

Build a routing function that determines the next node based on loan type classification.

### Requirements

1. Read loan_type and route to correct reviewer
2. Return valid conditional edge key

**File:** `routing/route_loan_type.py`

### Implementation

`route_loan_type` reads `loan_type` from state and converts it to lowercase defensively before checking. Substring matching (`"home" in loan_type`) is used rather than exact equality, making the function tolerant of minor LLM response variations. The order of checks matters — home is checked first, then personal, then auto, with `"final_aggregator"` as the fallback for any unrecognised value. The return strings match exactly the node names registered in the graph, which is a requirement for `add_conditional_edges` to resolve them correctly.

## Task 4 — Implement Reviewer Nodes

### Goal

Build specialized reviewer nodes that process different loan types and return findings.

### Requirements

1. Home reviewer: pass-through
2. Credit reviewer: analyze credit score → findings
3. Property assessor: validate property → findings
4. Personal reviewer: income + credit → findings
5. Auto reviewer: vehicle details → findings

**Files:** `nodes/home_loan_reviewer.py`, `nodes/credit_score_reviewer.py`, `nodes/property_assessor.py`, `nodes/personal_loan_reviewer.py`, `nodes/auto_loan_reviewer.py`

### Implementation

**home_loan_reviewer** acts purely as a coordinator — it returns the state unchanged. Its only role in the graph is to serve as the fan-out origin point from which two parallel edges depart toward `credit_score_reviewer` and `property_assessor`. No findings are generated here.

**credit_score_reviewer** reads `credit_score` from `applicant_info` and produces a single finding string based on four tiers: 750 and above is excellent, 650–749 is good, 550–649 is fair, and below 550 is poor. It returns `{"findings": [finding]}` so the `operator.add` reducer can merge it with findings from the parallel branch.

**property_assessor** reads `property_value` and `property_address` from `applicant_info`. If both are present it confirms the property as verified. If only the value is present it flags a missing address. If neither is provided it reports incomplete details. Returns `{"findings": [finding]}` in the same format as the credit reviewer.

**personal_loan_reviewer** runs independently (not in parallel) and generates two findings — one for income and one for credit score. Income is assessed across three bands (above 5000 is strong, 2500–5000 is moderate, below 2500 is low), and credit is assessed across three bands (700 and above is good standing, 550–699 is marginal, below 550 is poor). Both findings are returned together as `{"findings": [income_finding, credit_finding]}`.

**auto_loan_reviewer** also runs independently and generates two findings — one validating the vehicle make and model, and one assessing the loan-to-value ratio based on `vehicle_value`. If make or model is missing, the finding flags incomplete details. If vehicle value is zero, the eligibility finding requests a valuation. Returns `{"findings": [vehicle_finding, eligibility_finding]}`.

## Task 5 — Implement Final Aggregator

### Goal

Build an aggregator node that combines all findings into a final decision report.

### Requirements

1. Collect and deduplicate findings
2. Build final decision report and update state

**File:** `nodes/final_aggregator.py`

### Implementation

`final_aggregator` reads the merged `findings` list from state and deduplicates it by iterating with a `seen` set, preserving the original order. This guards against duplicate entries that can occasionally appear due to LangGraph's state merge behaviour in the fan-in step. The formatted decision report is built as a multi-line string containing the loan type (capitalised), total finding count, and a numbered list of all unique findings. The report is written to `state["final_decision"]` and the full updated state is returned.

## Task 6 — Implement Graph Construction

### Goal

Build the LangGraph workflow with conditional routing and parallel execution.

### Requirements

1. Register all nodes in StateGraph
2. Add conditional routing and parallel edges
3. Fan-in to final aggregator and END

**File:** `graph/build_graph.py`

### Implementation

All imports are placed inside `build_graph()` to avoid circular import issues that arise when modules in `nodes/` and `routing/` are imported at module load time. A `StateGraph` is instantiated with `LoanApplicationState` as the schema, which tells LangGraph how to handle state merging — particularly the `operator.add` reducer on `findings`.

All seven nodes are registered with `add_node`. The entry point is set to `"triage_agent"`. Conditional routing from `triage_agent` is wired using `add_conditional_edges` with `route_loan_type` as the routing function and an explicit mapping dict that covers all four possible return values including the fallback to `"final_aggregator"`.

The parallel fan-out for home loans uses two separate `add_edge` calls from `"home_loan_reviewer"` to `"credit_score_reviewer"` and `"property_assessor"` respectively — list syntax cannot be used on the destination side. The fan-in back to `"final_aggregator"` uses list syntax on the source side: `add_edge(["credit_score_reviewer", "property_assessor"], "final_aggregator")` — this is LangGraph's join pattern that waits for both parallel branches to complete before proceeding. Personal and auto paths connect directly to `"final_aggregator"` with single edges. A final edge connects `"final_aggregator"` to `END`. The compiled graph is returned via `builder.compile()`.

## Task 7 — Implement FastAPI Endpoint

### Goal

Build REST API endpoint that processes loan applications and returns assessment results.

### Requirements

1. Define request model
2. Initialize state and invoke graph
3. Return loan_type, findings, final_decision

**File:** `main.py`

### Implementation

The graph is built once at module level by calling `build_graph()` immediately after the FastAPI app is instantiated. This means the graph is compiled and ready before any request arrives, rather than being rebuilt on every call.

`LoanApplicationRequest` defines `loan_purpose` as a required string with no default, and all other fields as optional with sensible defaults — `credit_score` as `int = 0`, `monthly_income` and numeric value fields as `float = 0`, and string fields like `property_address`, `vehicle_make`, and `vehicle_model` as `str = ""`. This allows callers to omit irrelevant fields depending on the loan type.

The `/assess-loan` endpoint constructs the initial state dict with `loan_type` and `final_decision` as empty strings, `findings` as an empty list, and `applicant_info` as a dict containing all eight request fields. The graph is invoked synchronously with `graph.invoke(initial_state)`. Findings are deduplicated a second time in the endpoint response (in addition to inside `final_aggregator`) as an extra safeguard against state merge edge cases. The response returns only `loan_type`, `findings`, and `final_decision` — the `applicant_info` field is intentionally excluded from the response. The server is started with `uvicorn.run` on `0.0.0.0:8000` inside the `__main__` guard.

## Evaluation Criteria

Ensure you evaluate your solution against the below criteria:

1. **State Schema Definition**: LoanApplicationState TypedDict is defined with loan_type (str), applicant_info (dict), findings (Annotated[list, operator.add]), and final_decision (str) fields. The findings field uses operator.add reducer for parallel state merging. All imports (TypedDict, Annotated, operator) are correctly included.

2. **Triage Agent Implementation**: triage_agent function has correct signature accepting state parameter. get_llm() helper function retrieves Azure OpenAI credentials from environment variables and raises ValueError if not configured. Function extracts loan_purpose from applicant_info, invokes LLM with classification prompt, validates response is one of ["home", "personal", "auto"], defaults to "personal" if invalid, updates state["loan_type"], and returns updated state. Function does not return None or empty dict.

3. **Routing Function Implementation**: route_loan_type function has correct signature accepting state parameter and returns str. Function gets loan_type from state and converts to lowercase. Returns "home_loan_reviewer" if "home" in loan_type, "personal_loan_reviewer" if "personal" in loan_type, "auto_loan_reviewer" if "auto" in loan_type, and "final_aggregator" as default fallback. Return values match keys in conditional edges mapping.

4. **Final Aggregator Implementation**: final_aggregator function has correct signature accepting state parameter. Function gets findings list from state, optionally deduplicates findings, creates formatted decision report with loan type, total findings count, and numbered list of findings, updates state["final_decision"] with formatted report, and returns updated state. Function does not return None.

5. **Graph Construction Implementation**: build_graph function imports all necessary modules (StateGraph, END, state, nodes, routing). Creates StateGraph with LoanApplicationState schema. Registers all seven nodes using add_node. Sets entry point to "triage_agent" using set_entry_point. Adds conditional edges from "triage_agent" using add_conditional_edges with route_loan_type function and proper mapping. For home loans: adds separate edges from "home_loan_reviewer" to "credit_score_reviewer" and "property_assessor" (fan-out using separate add_edge calls, not list syntax for end_key). Adds edge from ["credit_score_reviewer", "property_assessor"] to "final_aggregator" (fan-in using list syntax for start_key). Adds edges from "personal_loan_reviewer" and "auto_loan_reviewer" directly to "final_aggregator". Adds edge from "final_aggregator" to END. Returns compiled graph using builder.compile(). Function does not return None.

6. **FastAPI Application Implementation**: FastAPI app is created with title, description, and version. Graph is built using build_graph() at module level. LoanApplicationRequest Pydantic model is defined with all required fields (loan_purpose, credit_score, monthly_income, property_value, property_address, vehicle_make, vehicle_model, vehicle_value) with correct types and default values.

7. **POST /assess-loan Endpoint Implementation**: POST /assess-loan endpoint is decorated with @app.post("/assess-loan") and accepts LoanApplicationRequest parameter. Endpoint initializes state dict with loan_type (""), applicant_info (dict with all request fields), findings ([]), and final_decision (""). Invokes graph with initial state using graph.invoke(initial_state). Deduplicates findings in response using key-based deduplication. Returns dict with loan_type, findings (deduplicated), and final_decision. Endpoint handles exceptions gracefully.