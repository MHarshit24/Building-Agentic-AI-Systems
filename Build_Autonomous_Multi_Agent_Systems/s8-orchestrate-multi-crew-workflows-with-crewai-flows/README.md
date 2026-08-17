# Resume Screening & Candidate Routing

A FastAPI-based service that uses a multi-crew orchestration system using CrewAI Flows to screen resumes, route them to specialized crews, and generate AI-driven hiring recommendations.

## Project Context

You are building a Resume Screening and Candidate Routing system, an AI-powered application that uses CrewAI Flows to orchestrate specialized evaluation crews based on resume content. The system uses a flow-based architecture where a main flow classifies a resume, routes it to the appropriate domain-specific crew (Data Analyst, HR, Sales, or General), and aggregates the evaluation results.

This practice focuses on building orchestrations with CrewAI Flows - implementing a `Flow` class with state management, using decorators like `@start`, `@router`, and `@listen` to define the workflow, creating specialized agents for different domains, and exposing the entire process as a REST API. You will configure Azure OpenAI LLM, define the flow state, implement the routing logic, and create a FastAPI application to serve the model.

## Problem Statement

Build a Resume Screening pipeline that accepts a candidate's name and resume text, classifies the role, routes it to the correct evaluator, and produces a structured assessment. You need to implement Azure OpenAI LLM configuration, the flow orchestration logic, Pydantic models for state and API communication, and a FastAPI endpoint.

You will complete multiple implementation tasks to build this Resume Screening Flow:

## Task 1 — Implement Crew Service

### Goal

Build the complete CrewAI Flow service with LLM initialization, classification logic, routing, and specialized evaluator execution.

### Requirements

1. Load environment variables.
2. Read Azure OpenAI credentials from env.
3. Validate required env vars.
4. Initialize Azure OpenAI LLM.
5. Define `ResumeScreeningFlow` class inheriting from `Flow`.
6. Implement `classify_resume` method decorated with `@start` to determine the role.
7. Implement `route_application` method decorated with `@router` to direct the flow.
8. Implement `_run_evaluator` helper to create and run specialized agents.
9. Implement listeners (e.g., `run_data_analyst_crew`) for each track.
10. Implement `process_resume` async wrapper to run the flow.

**File:** `services.py`

### Implementation Details

**Environment Loading — Dual `.env` Pattern**

The service uses a two-stage environment loading strategy to prevent credential conflicts across assignments. The root `.env` file (located two directory levels above the project) is loaded first without override, so all shared Azure credentials are picked up. The values for `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_VERSION`, and `AZURE_OPENAI_LLM_DEPLOYMENT` are immediately captured into local variables. If a project-level `.env` exists, it is then loaded with `override=True`. After that, the preserved root credentials are restored back into the environment, ensuring that no project-level file can accidentally overwrite the shared Azure configuration.

**LLM Initialization — `_build_azure_llm`**

This helper reads the four Azure OpenAI configuration values from the environment. The deployment name lookup uses `AZURE_OPENAI_LLM_DEPLOYMENT` as the primary key, with `AZURE_OPENAI_DEPLOYMENT_NAME` as a fallback, so both personal and README-specified variable names are honoured. Before constructing the LLM, it validates that none of the required values are missing and raises a descriptive `ValueError` listing any absent variables. The CrewAI `LLM` is constructed with the model string formatted as `azure/<deployment_name>`, which is the path required by CrewAI's Azure OpenAI provider (not the litellm path).

**Flow State Initialisation — `ResumeScreeningFlow.__init__`**

The constructor calls `super().__init__()` to let the CrewAI `Flow` base class set up its state machinery, then immediately builds and stores the LLM instance on `self.llm`. This ensures the same LLM object is reused across all four evaluator crews within a single flow execution, avoiding redundant initialisation.

**Resume Classification — `classify_resume` (`@start`)**

This is the entry point of the flow. It converts the resume text to lowercase and scores it against three independent keyword lists — one each for data analyst, HR, and sales domains. The score for each domain is simply the count of matching keywords found in the resume. The domain with the highest non-zero score determines the route. In the case of a tie between domains, data analyst takes precedence over HR, which takes precedence over sales. If no keywords match any list at all, the resume falls through to the general track. The classified role label (e.g., `"Data Analyst"`) and the routing track string (e.g., `"data_analyst_track"`) are both set, and the track string is returned for the router to consume.

**Routing — `route_application` (`@router`)**

The router receives the track string returned by `classify_resume` and validates it against the four known track names. If the string is unrecognised for any reason, it safely falls back to `"general_track"` rather than raising an error. The returned string is what CrewAI uses to determine which `@listen` method to invoke next.

**Evaluator Helper — `_run_evaluator`**

This private method contains all the CrewAI boilerplate for creating and running a single-agent crew, keeping the four listener methods thin. It creates an `Agent` with the provided role name, goal, and a backstory that frames the agent as an experienced domain expert. The `Task` description passes the full candidate name, applying-for context, and resume text inline, and explicitly instructs the agent to write in prose rather than JSON. After `crew.kickoff()` completes, `result.raw` (the plain text output) is stored in `self.state.justification`, and the agent's role name is stored in `self.state.evaluator_role` so the API response can surface who performed the evaluation.

**Track Listeners**

Each of the four `@listen` methods — `run_data_analyst_crew`, `run_hr_crew`, `run_sales_crew`, and `run_general_crew` — does nothing except call `_run_evaluator` with domain-appropriate arguments. The evaluator roles are Lead Data Scientist, HR Director, VP of Sales, and General Recruiter respectively. The evaluation criteria passed to each are tailored to the domain: technical skills and tooling for data analyst, compliance and people skills for HR, quota attainment and CRM proficiency for sales, and transferable employability skills for general.

**Async Wrapper — `process_resume`**

Because CrewAI's `flow.kickoff()` is synchronous and blocking, running it directly inside a FastAPI `async` route would block the entire event loop. The wrapper solves this by obtaining the current event loop and offloading the synchronous `kickoff` call to a thread pool executor using `loop.run_in_executor(None, flow.kickoff)`. The initial state fields — `candidate_name`, `resume_text`, and `applying_for` — are set on the flow instance before the executor call so they are available when `classify_resume` fires. The function returns both the flow instance (so the caller can read the final state) and the raw kickoff result.

---

## Task 2 — Implement Pydantic Models

### Goal

Define the Flow State and request/response models for the FastAPI endpoint.

### Requirements

1. Import `BaseModel` and `Field`.
2. Define `ResumeFlowState` with fields like `candidate_name`, `resume_text`, `classified_role`, `justification`, etc.
3. Define `ResumeRequest` fields: `candidate_name`, `resume_text`, `applying_for`.
4. Define `ResumeResponse` fields: `success`, `candidate_name`, `classified_role`, `evaluator`, `feedback`.

**File:** `models.py`

### Implementation Details

**`ResumeFlowState`**

This model represents the internal state that the CrewAI Flow carries and mutates across its methods. All six fields default to an empty string so that CrewAI's Flow base class can instantiate the state object before any values are injected. The fields `candidate_name`, `resume_text`, and `applying_for` are populated by the `process_resume` wrapper before kickoff. The fields `classified_role`, `evaluator_role`, and `justification` are written during flow execution — by `classify_resume` and `_run_evaluator` respectively — and are read back at the end to build the API response.

**`ResumeRequest`**

This is the JSON payload model for the `POST /screen` endpoint. All three fields — `candidate_name`, `resume_text`, and `applying_for` — are required (no defaults), which means FastAPI will automatically return a `422 Unprocessable Entity` response if any of them are absent or of the wrong type. Each field carries a human-readable description that is surfaced in the Swagger UI.

**`ResumeResponse`**

This is the structured JSON response returned to the caller after the flow completes. The `success` boolean signals whether the pipeline completed without error. The `classified_role` field reflects what domain the keyword classifier assigned the resume to. The `evaluator` field names the agent role that assessed the candidate (e.g., Lead Data Scientist), providing transparency about which specialised crew was used. The `feedback` field contains the full prose evaluation produced by the LLM.

---

## Task 3 — Implement FastAPI Endpoint

### Goal

Build REST API endpoint that processes resume screening requests.

### Requirements

1. Import models and service function.
2. Implement `POST /screen`.
3. Validate required fields.
4. Call `process_resume` and return `ResumeResponse`.
5. Handle errors with `HTTPException`.

**File:** `main.py`

### Implementation Details

**Blank-String Validation**

Pydantic enforces that all three request fields are present and are strings, but it cannot catch fields that are present yet empty. Before calling the service, the endpoint explicitly strips each field and raises an `HTTPException` with status `422` if any of them resolve to an empty string. This guards against payloads like `{"candidate_name": "  ", ...}` that would otherwise pass Pydantic validation but produce meaningless flow output.

**Calling the Service**

The endpoint `await`s `process_resume`, passing the three request fields directly. The function returns a tuple of the flow instance and the raw kickoff result. Only the flow instance is used — its `.state` attributes hold all the information needed to construct the response.

**Building the Response**

After the flow completes, `flow.state.candidate_name`, `flow.state.classified_role`, `flow.state.evaluator_role`, and `flow.state.justification` are mapped directly into a `ResumeResponse` object with `success` set to `True`. FastAPI serialises this into the structured JSON body that the caller receives.

**Error Handling**

Two exception types are caught separately. A `ValueError` indicates a configuration problem (typically a missing environment variable surfaced by `_build_azure_llm`) and is returned as a `500` with a message prefixed `Configuration error:`. Any other `Exception` is also returned as a `500`, prefixed `Resume screening failed:`, so the caller always receives a meaningful error message rather than an unhandled traceback.

---

## How to Run

Start the server from the project directory using:

```
python main.py
```

The API will be available at `http://localhost:8000`. The interactive Swagger UI can be accessed at `http://localhost:8000/docs` and can be used to test all endpoints without any additional tooling.

To suppress the interactive CrewAI trace prompt that appears between requests, add `CREWAI_TRACING_ENABLED=false` to the project `.env` file.

---

## Architecture Overview

The system follows a linear flow-based architecture with a single decision point:

1. The FastAPI `POST /screen` endpoint receives the candidate payload and delegates to the `process_resume` async wrapper.
2. The wrapper initialises a `ResumeScreeningFlow` instance, sets the initial state, and offloads the synchronous `kickoff` to a thread pool executor so FastAPI's event loop is not blocked.
3. Inside the flow, `classify_resume` (decorated with `@start`) performs keyword scoring to assign the resume to one of four domain tracks and returns the track name.
4. `route_application` (decorated with `@router`) validates and forwards the track name, which CrewAI uses to select the correct `@listen` method.
5. The selected listener — one of `run_data_analyst_crew`, `run_hr_crew`, `run_sales_crew`, or `run_general_crew` — calls the shared `_run_evaluator` helper with domain-specific agent configuration.
6. `_run_evaluator` constructs a single-agent `Crew`, runs it, and writes the text output back into the flow state.
7. Control returns to `process_resume`, which hands the flow instance back to the FastAPI route.
8. The route reads the final state and returns a structured `ResumeResponse` to the caller.

---

## Evaluation Criteria

Ensure you evaluate your solution against the below criteria:

1. **Crew Service Implementation**: `services.py` properly loads environment variables, initializes LLM, implements the `ResumeScreeningFlow` with correct `@start`, `@router`, and `@listen` decorators, and successfully routes resumes to different crews based on content.
2. **Pydantic Models Implementation**: `ResumeFlowState` correctly manages the flow's internal state. `ResumeRequest` and `ResumeResponse` are defined with appropriate fields and types.
3. **FastAPI Endpoint Implementation**: `POST /screen` acts as the entry point, accepting JSON requests, triggering the flow, and returning a structured JSON response with the AI's feedback.