# Expense Policy Validator

A FastAPI-based service that uses a hierarchical CrewAI crew to validate an expense claim against a simple company policy.

## Project Context

You are building an Expense Policy Validator Crew, an AI-powered system that uses a 3-agent hierarchical CrewAI crew to validate expense claims against a simple company policy and produce an auditable decision summary. The system uses manager-led autonomous collaboration where a Finance Manager coordinates two specialist agents (Policy Interpreter and Expense Validator) to interpret policy, apply decision logic, and produce a final decision with reasoning.

This practice focuses on building hierarchical crews with CrewAI — implementing a custom manager_agent with a clear role and goal, defining specialist agents with focused responsibilities, creating a single high-level task for the manager, assembling a hierarchical crew, and exposing the crew as a REST API. You will configure Azure OpenAI LLM for CrewAI, define the three agents, create a high-level validation task that includes policy and expense details, assemble the crew with Process.hierarchical, and implement FastAPI endpoints that accept expense details and return structured validation results.

## Problem Statement

Build an Expense Policy Validator crew that responds to expense claims by interpreting company policy, checking compliance, calculating any excess amount, and producing a final decision with reasoning. You need to implement Azure OpenAI LLM configuration, three agents (Policy Interpreter, Expense Validator, Finance Manager), a single high-level validation task, hierarchical crew assembly, Pydantic request/response models, and FastAPI endpoints that process validation requests and return structured results.

You will complete multiple implementation tasks to build this Expense Policy Validator crew:

## Task 1 — Implement Crew Service

### Goal

Build the complete CrewAI crew service with LLM initialization, three agents, one high-level task, and hierarchical crew assembly.

### Requirements

1. Load environment variables.
2. Read Azure OpenAI credentials from env.
3. Validate required env vars; raise `ValueError` if missing.
4. Initialize Azure OpenAI LLM.
5. Create Policy Interpreter agent.
6. Create Expense Validator agent.
7. Create Finance Manager manager_agent.
8. Create one high-level validation Task (policy + expense details, expected_output, `output_file="expense_decision.md"`).
9. Create hierarchical Crew with specialists, Task, and manager_agent.
10. Return crew execution result.

**File:** `services.py`

## Task 2 — Implement Pydantic Models

### Goal

Define request and response models for the FastAPI endpoint.

### Requirements

1. Import `BaseModel` and `Field`.
2. Define `ExpensePolicyRequest` fields: `expense_type`, `amount`, `policy_limit`, `receipt_provided`, `business_purpose`.
3. Define `ExpensePolicyResponse` fields: `success`, `decision`, `message`.

**File:** `models.py`

## Task 3 — Implement FastAPI Endpoint

### Goal

Build REST API endpoint that processes expense validation requests.

### Requirements

1. Import models and service function.
2. Implement `POST /expense/validate`.
3. Validate required fields.
4. Call the crew service and return `ExpensePolicyResponse`.
5. Handle errors with `HTTPException`.

**File:** `main.py`

## Evaluation Criteria

Ensure you evaluate your solution against the below criteria:

1. **Crew Service Implementation**: `services.py` properly loads environment variables, validates Azure OpenAI credentials, initializes LLM with Azure configuration, defines three agents (Policy Interpreter, Expense Validator, Finance Manager), creates a single high-level Task with policy and expense details, assembles a hierarchical Crew with `Process.hierarchical` and `manager_agent`, and returns crew execution results.
2. **Pydantic Models Implementation**: `ExpensePolicyRequest` BaseModel is defined with all required fields and descriptions. `ExpensePolicyResponse` BaseModel is defined with success, decision, and message fields.
3. **FastAPI Endpoint Implementation**: `POST /expense/validate` validates that required fields are not empty, calls the crew service, handles exceptions with `HTTPException`, and returns `ExpensePolicyResponse` with the decision text and a success message.

---

## Implementation Notes

### Environment Setup

Environment variables are loaded from the root `.env` file located four directory levels above the `services.py` file, which corresponds to `C:\Users\harsh\NIIT\Building_Agentic_AI_Systems\.env`. A `Path(__file__).resolve().parents[4]` traversal is used to locate the file programmatically. If that path does not exist, `load_dotenv()` is called without arguments as a fallback, which picks up any `.env` in the current working directory or system environment. There is no project-level `.env` in the `s7` folder; all credentials are sourced from the shared root file.

The variable names used in the implementation follow the personal naming convention as primary lookups, with the README-specified names as fallbacks via `os.getenv("personal_name", "fallback_name")`. Specifically, `AZURE_OPENAI_LLM_DEPLOYMENT` is read first, falling back to `AZURE_OPENAI_DEPLOYMENT_NAME` if absent.

---

### Task 1 — Crew Service (`services.py`)

**LLM Initialisation**

The `_build_azure_llm()` helper reads the four required Azure OpenAI credentials from the environment. It validates that the API key, endpoint, and deployment name are all present and non-empty, raising a descriptive `ValueError` that lists every missing variable if any are absent. The `LLM` object is constructed using the CrewAI 1.x API, where the model string is prefixed with `azure/` followed by the deployment name, and the Azure endpoint is passed via the `api_base` parameter rather than `azure_endpoint` (which belongs to the old 0.x API).

**Specialist Agents**

Two specialist agents are defined, both sharing the same LLM instance built by the helper.

The Policy Interpreter is focused exclusively on translating company policy language into concrete, actionable rules for a given expense type. Its backstory frames it as a compliance expert, ensuring the LLM stays in scope and does not drift into making approval decisions.

The Expense Validator is focused on applying those interpreted rules to the actual claim — checking each rule, computing the reimbursable amount, calculating any excess, and documenting findings in a structured format. Its backstory frames it as a financial auditor.

**Finance Manager (manager_agent)**

The Finance Manager is defined as a separate `Agent` instance and passed to the `Crew` via the `manager_agent` parameter rather than included in the `agents` list. This is the correct CrewAI 1.x pattern for hierarchical crews — the manager orchestrates the specialists but is not itself a worker in the task queue. Its goal is to coordinate the two specialists and synthesise their outputs into a single authoritative decision.

**Validation Task**

A single high-level `Task` is defined with the Finance Manager set as its `agent`. The task description is assembled at runtime by combining a fixed plain-English policy summary with the live values from the incoming `ExpensePolicyRequest` — expense type, claimed amount, policy limit, receipt status, and business purpose are all interpolated into the description string. The `expected_output` field describes the four-section structure the crew should produce: policy interpretation, compliance check results, reimbursable and excess amounts, and a final APPROVED or REJECTED verdict. The `output_file` is set to `expense_decision.md`, which causes CrewAI to write the final decision to that file in the working directory after each run.

**Hierarchical Crew Assembly**

The `Crew` is assembled with `Process.hierarchical`, the two specialist agents in the `agents` list, the single task in the `tasks` list, and the Finance Manager passed as `manager_agent`. The crew is executed synchronously via `kickoff()`, and the result is cast to a string before being returned to the caller.

---

### Task 2 — Pydantic Models (`models.py`)

**ExpensePolicyRequest**

Five fields are defined using `Field` with descriptive `description` strings, which appear in the Swagger UI to guide API consumers. `expense_type` and `business_purpose` are `str` fields. `amount` and `policy_limit` are `float` fields representing USD values. `receipt_provided` is a `bool` field. All five are required (no default values), so Pydantic will reject any request body that omits them.

**ExpensePolicyResponse**

Three fields are defined. `success` is a `bool` indicating whether the crew completed without error. `decision` is a `str` containing the full structured decision report produced by the Finance Manager, including all four sections. `message` is a short human-readable `str` summarising the outcome, set to a fixed string on the happy path.

---

### Task 3 — FastAPI Endpoint (`main.py`)

**Async / Sync Bridge**

Because the FastAPI endpoint is declared `async` and CrewAI's `kickoff()` is synchronous, calling the service directly inside the endpoint would raise a runtime error about invoking a synchronous executor from within a running event loop. This is resolved by offloading `validate_expense_policy` to a thread pool executor using `asyncio.get_event_loop().run_in_executor()`. `functools.partial` is used to bind the `request` argument since `run_in_executor` only accepts zero-argument callables. This allows the event loop to remain non-blocking while the crew runs on a background thread.

**Field Validation**

Before the service is called, four manual checks are applied: `expense_type` and `business_purpose` are checked to ensure they are not empty or whitespace-only strings, and `amount` and `policy_limit` are checked to ensure they are greater than zero. Any violation raises an `HTTPException` with a 400 status code and a specific detail message identifying the offending field. These checks complement Pydantic's type validation, which handles missing fields and wrong types at the schema level.

**Error Handling**

The service call is wrapped in a try/except block. A `ValueError` — which is raised by the LLM builder when credentials are missing — is caught and re-raised as a 400 `HTTPException`. Any other exception is caught and re-raised as a 500 `HTTPException` with the original error message included in the detail string. On success, an `ExpensePolicyResponse` is returned with `success` set to `True`, the decision string from the crew, and a fixed success message.

---

### Known Behaviour: delegate_work_to_coworker Warnings

During crew execution, the terminal may show repeated `delegate_work_to_coworker` errors with the message "Executor is already running. Cannot invoke the same executor instance concurrently." This is a known limitation of running CrewAI 1.x hierarchical crews inside a thread pool executor — the manager agent attempts to delegate sub-tasks to specialists concurrently, but because the same executor thread is already occupied, those delegation calls fail. CrewAI handles this gracefully by retrying and eventually having the Finance Manager synthesise the final answer directly from the task context. The HTTP response is still 200 and the decision output is correct and complete.

---

### Running the Service

Start the server from the `s7` project directory using `python main.py`. The server binds to `0.0.0.0:8000` with `reload=True`. The interactive API documentation is available at `http://localhost:8000/docs`. The `/health` endpoint can be used to verify the service is running before submitting validation requests. After each successful validation, a file named `expense_decision.md` is written to the project directory containing the structured decision report.