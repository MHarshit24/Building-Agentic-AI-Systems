# Technical Documentation Generation

## Project Context

You're building a Technical Documentation Generator, an AI-powered system that generates comprehensive documentation for Python code and iteratively improves it through self-reflection until quality standards are met. The system uses a Reflection pattern to generate initial documentation, critically evaluate it for completeness and clarity, and refine it until quality criteria are satisfied.

This practice focuses on building Self-Correcting agents with LangGraph — implementing generation nodes that create initial documentation, reflection nodes that critique documentation quality, refinement nodes that improve documentation based on feedback, and conditional routing based on quality scores. You'll learn how to create state schemas with reflection tracking fields, build generation prompts that create structured documentation, implement reflection logic that evaluates on multiple criteria, design refinement mechanisms that address specific issues, and implement quality gates that determine when to approve or continue refining.

## Problem Statement

Build a Reflection-based technical documentation generator that responds to code snippets by creating initial documentation, evaluating it on completeness, clarity, and examples, refining it based on critique, and approving when quality threshold is met. You need to implement state schemas with draft output and reflection feedback tracking, generation prompts that create README.md format documentation, graph nodes for generation, reflection, and refinement, conditional routing based on quality scores, and FastAPI endpoints that process documentation requests and return structured results.

You will complete multiple implementation tasks to build this Self-Correcting documentation agent:

## Task 1 — Implement State Schema

### Goal

Define the state schema that tracks documentation generation, reflection feedback, iterations, and quality scores.

### Requirements

1. Open `state.py`
2. Define `DocumentationReflectionState` TypedDict with the following fields:
   - `messages`: Annotated[list, operator.add]
   - `task_description`: str
   - `draft_output`: str
   - `reflection_feedback`: Annotated[List[str], operator.add]
   - `iteration_count`: int
   - `quality_score`: float
   - `quality_threshold`: float
   - `max_iterations`: int
   - `output_approved`: bool

**File:** `state.py`

### Implementation

`DocumentationReflectionState` is defined as a `TypedDict` with nine fields. Two of the fields — `messages` and `reflection_feedback` — are declared using `Annotated[..., operator.add]`, which instructs LangGraph to automatically accumulate new items appended by each node rather than overwriting the previous value. This is essential for the reflection loop: every iteration appends a new feedback string to `reflection_feedback` without losing prior critique history.

The remaining fields use plain types. `draft_output` holds the current working version of the documentation and is overwritten on each refinement. `iteration_count` is an integer that increments only when the reflector decides a refinement is needed, so it accurately reflects how many improvement passes actually ran. `quality_score` is updated after every reflection call. `quality_threshold` and `max_iterations` are passed in from the API request and stored in state so every node and the routing function can read them without needing external configuration. `output_approved` is a boolean flag set by either the reflection node or the routing function to signal the final approval decision.

## Task 2 — Implement LLM Initialization

### Goal

Set up Azure OpenAI LLM instance for generation, reflection, and refinement operations.

### Requirements

1. Open `llm.py`
2. Load environment variables using `load_dotenv()`
3. Initialize `AzureChatOpenAI` (or `ChatOpenAI`) with:
   - Parameters from environment variables (API key, endpoint, version)
   - `temperature=0` (deterministic)
4. Export the instance as `llm`

**File:** `llm.py`

### Implementation

Environment variables are loaded from the root `.env` file located at `Building_Agentic_AI_Systems/`. The path is resolved dynamically using `Path(__file__).resolve().parents[2]`, which walks two levels up from `llm.py`'s location to reach the project root. If that path does not exist on disk — for example in a different environment layout — the code falls back to a bare `load_dotenv()` call so it can still pick up variables from the working directory or shell.

The deployment name is resolved with an `or` chain across three variable names in priority order: `AZURE_OPENAI_LLM_DEPLOYMENT` (the personal naming convention used in this project), then `AZURE_OPENAI_DEPLOYMENT_NAME` (the name used in the assignment scaffolding), then `MODEL_NAME` (a generic fallback). This ensures the correct deployment is picked up regardless of which naming convention was used to set up the environment.

`AzureChatOpenAI` is initialised with `temperature=0` for fully deterministic output — important here because both the generation and reflection prompts need consistent, reproducible responses across runs. `max_retries=3` handles transient Azure API errors silently, and `timeout=60` prevents the FastAPI worker from hanging indefinitely if the upstream service is slow. The resulting instance is exported as the module-level `llm` variable and imported directly by both node files.

## Task 3 — Implement Generation Node

### Goal

Build a generation node that creates initial technical documentation in README.md format.

### Requirements

1. Open `nodes/generation.py`
2. Implement `generation_node` function:
   - **Input**: `state`
   - **Action**: Use LLM to generate a README.md based on `task_description`
   - **Output**: Update `draft_output`, reset `iteration_count` to 0, set `output_approved` to False

**File:** `nodes/generation.py`

### Implementation

The generation node reads `task_description` from state and constructs a two-message prompt: a system message that establishes the LLM as an expert technical writer with a mandate to produce beginner-friendly Markdown, and a human message that specifies the exact four sections required — Overview, Installation, Usage, and API Documentation — along with an instruction to output only Markdown content with no surrounding explanation.

After the LLM responds, the raw content is cleaned of any Markdown code fences the model may have wrapped around the output. The cleaning handles both the ` ```markdown ` variant and a bare ` ``` ` fence, stripping them from both the start and end of the string. This is a defensive step because many LLMs wrap their output in fences even when explicitly told not to, and passing fenced content downstream would corrupt the reflection evaluation.

The node returns only a partial state dictionary — `draft_output`, `iteration_count` reset to zero, and `output_approved` set to `False` — rather than the full state object. LangGraph merges partial returns with the existing state automatically, so only the fields that actually changed need to be returned. `iteration_count` is reset to zero here because this node always represents the start of a fresh generation cycle.

## Task 4 — Implement Reflection Node

### Goal

Build a reflection node that critically evaluates documentation on completeness, clarity, and examples.

### Requirements

1. Open `nodes/reflection.py`
2. Implement `reflection_node` function:
   - **Input**: `state`
   - **Action**: Use LLM to Critique **AND** Refine the documentation
     - Evaluate Completeness, Clarity, Examples (0-10)
     - If score < threshold, generate **refined content** in the same call
   - **Output**: Update `quality_score`, append to `reflection_feedback`
     - If refined, update `draft_output` and increment `iteration_count`

**File:** `nodes/reflection.py`

### Implementation

The reflection node performs two responsibilities in a single LLM call: it critiques the current draft and, if the quality is below the threshold, it also produces a refined version of the documentation in the same response. Combining critique and refinement into one call avoids an extra round-trip to the API and ensures the refined content is directly informed by the critique that produced it.

The system message instructs the LLM to act as a strict technical reviewer and to respond exclusively in valid JSON. The human message presents both the original task description and the current `draft_output`, then asks for scores on three criteria — Completeness, Clarity, and Examples — each on a 0–10 scale, along with an `overall_score`, a list of issues, a list of suggestions, a one-sentence summary, and a `refined_content` field containing an improved README if the score falls below the threshold.

After the LLM responds, the raw text is stripped of any ` ```json ` or bare ` ``` ` fences before being passed to `json.loads()`. If parsing fails — for example if the model returns prose instead of JSON — a `JSONDecodeError` is caught and the score falls back to `5.0`, which keeps the graph running rather than crashing. A human-readable feedback string is constructed from the iteration number and the summary, and is returned as a single-element list so LangGraph's `operator.add` accumulator appends it to the existing `reflection_feedback` list rather than replacing it.

The node then checks whether refinement is needed: if `overall_score` is below `quality_threshold` and the current `iteration_count` is still within `max_iterations`, and the LLM provided non-empty `refined_content`, it updates `draft_output` with the refined version, increments `iteration_count`, and sets `output_approved` to `False`. Otherwise it sets `output_approved` to `True`. Like the generation node, only the fields that changed are returned in the partial dictionary.

## Task 5 — Implement Quality Gate Routing

### Goal

Build routing logic that determines whether to approve documentation or continue refining.

### Requirements

1. Open `routing.py`
2. Implement `should_continue` function:
   - **Input**: `state`
   - **Logic**:
     - Return "approve" if `iteration_count` >= max or `quality_score` >= threshold
     - Return "refine" otherwise

**File:** `routing.py`

### Implementation

`should_continue` reads four values from state — `quality_score`, `iteration_count`, `max_iterations`, and `quality_threshold` — and applies three checks in a fixed priority order. The iteration ceiling is checked first so the graph always terminates even if the LLM consistently scores below the threshold. The exact threshold check comes second, covering the normal approval path. A borderline check at `7.0` comes third and handles the case where the score is close enough to an acceptable level even if it hasn't cleared the exact threshold — this prevents unnecessary extra iterations when the documentation is already of reasonable quality.

In all three approval cases, `output_approved` is set to `True` directly on the state before returning. This is a deliberate redundancy alongside the flag being set in the reflection node: the routing function is the definitive decision point for approval by iteration limit, so it ensures the flag is accurate regardless of what the reflection node set. If none of the three conditions are met, the function returns `"refine"`, which the graph maps back to the `"reflector"` node for another pass.

## Task 6 — Build Reflection Graph

### Goal

Construct the complete LangGraph workflow with generation, reflection, and refinement nodes.

### Requirements

1. Open `graph.py`
2. Implement `build_graph()`:
   - Create `StateGraph` with `DocumentationReflectionState`
   - Add nodes: `"generator"`, `"reflector"`
   - Add Edge: `"generator"` -> `"reflector"`
   - Add Conditional Edge from `"reflector"` using `should_continue`:
     - "refine" -> `"reflector"` (Loop)
     - "approve" -> `END`

**File:** `graph.py`

### Implementation

`build_graph` constructs a `StateGraph` parameterised with `DocumentationReflectionState` so LangGraph knows the exact shape of the state object and can handle field-level merging correctly. Two nodes are registered: `"generator"` mapped to `generation_node` and `"reflector"` mapped to `reflection_node`.

The entry point is set to `"generator"`, and a direct edge connects `"generator"` to `"reflector"` so every run always starts with a fresh generation followed immediately by a reflection. The conditional edge is attached to `"reflector"` using `should_continue` as the routing function, with a mapping dictionary that sends `"refine"` back to `"reflector"` (creating the self-correction loop) and `"approve"` to `END` (terminating the graph). This means the reflector node can run multiple times in sequence — each time LangGraph calls `should_continue` after the node returns and decides whether to loop or exit.

The compiled graph is returned from `build_graph` and stored as the module-level `doc_graph` in `main.py` at startup. Compiling once at startup rather than per request avoids repeated graph construction overhead on every API call.

## Task 7 — Implement FastAPI Endpoint

### Goal

Build REST API endpoint that processes documentation requests and returns structured results.

### Requirements

1. Open `main.py`
2. Define Pydantic models:
   - `DocumentationRequest`: task_description (str), quality_threshold (float), max_iterations (int)
   - `DocumentationResponse`: status, generated_docs, history, metrics
3. Implement `POST /generate`:
   - Initialize state
   - Run graph: `await asyncio.to_thread(doc_graph.invoke, ...)`
   - Return response


**File:** `main.py`

### Implementation

The FastAPI application is initialised once at module load time. `build_graph()` is called immediately after import and the compiled graph is stored as `doc_graph` — a module-level variable that persists across all incoming requests for the lifetime of the server process.

`DocumentationRequest` accepts three fields: `task_description` as a required string, `quality_threshold` defaulting to `8.0`, and `max_iterations` defaulting to `3`. `DocumentationResponse` captures the full output of a graph run: the final documentation string, the accumulated reflection history as a list of strings, the number of refinement iterations that actually ran, the final quality score, the approval flag, and the total wall-clock execution time in seconds.

The `POST /generate` endpoint builds an initial state dictionary with all nine fields that `DocumentationReflectionState` expects, supplying empty defaults for fields the graph will populate. The graph is invoked using `await asyncio.to_thread(doc_graph.invoke, initial_state)`, which runs the synchronous LangGraph call in a separate thread pool thread so the FastAPI event loop is not blocked during the LLM calls. Execution time is measured by recording a timestamp immediately before the `asyncio.to_thread` call and computing the difference after it returns. Any exception during graph execution is caught and re-raised as an HTTP 500 with the error detail included, so callers get a meaningful error message rather than a generic server failure. The final state returned by the graph is unpacked into a `DocumentationResponse` and returned with HTTP 200.

The `GET /health` endpoint requires no graph interaction and returns a static status object, serving as a lightweight liveness check.

## Evaluation Criteria
 
Ensure you evaluate your solution against the below criteria:
 
1. **State Schema Implementation**: DocumentationReflectionState class extends TypedDict correctly, includes all required fields with correct types (messages with Annotated[list, operator.add], task_description as str, draft_output as str, reflection_feedback with Annotated[List[str], operator.add], iteration_count as int, quality_score as float, quality_threshold as float, max_iterations as int, output_approved as bool), and all fields are properly typed.
 
2. **LLM Initialization Implementation**: llm.py loads environment variables with load_dotenv(), retrieves all required Azure OpenAI credentials from environment, creates AzureChatOpenAI instance with correct parameters (api_key, azure_endpoint, model, api_version, temperature=0, max_retries=3, timeout=60), and exports llm variable correctly.
 
3. **Generation Node Implementation**: generation_node function has correct signature accepting DocumentationReflectionState parameter. Function extracts task_description from state, builds comprehensive generation prompt requesting README.md format with overview, installation, usage examples, and API docs, uses beginner-friendly language instruction, invokes llm.invoke() with SystemMessage and HumanMessage, extracts documentation from response.content, cleans markdown code fences (handles ```markdown and ``` cases), stores documentation in draft_output, initializes iteration_count to 0, sets output_approved to False, and returns updated state.
 
4. **Reflection Node Implementation**: reflection_node function has correct signature accepting DocumentationReflectionState parameter. Function extracts task_description and draft_output from state, builds critique prompt evaluating on three criteria (Completeness, Clarity, Examples) with 0-10 scoring, requests JSON format with scores, issues, suggestions, and overall_score, invokes llm.invoke() with SystemMessage and HumanMessage, parses JSON from response.content (removes markdown fences, handles JSONDecodeError), extracts overall_score from critique, creates feedback string with iteration number and summary, appends feedback to reflection_feedback, updates quality_score with overall_score, handles JSONDecodeError with fallback score 5.0, and returns updated state.
 
5. **Quality Gate Routing Implementation**: should_continue function has correct signature accepting DocumentationReflectionState parameter and returns str. Function extracts quality_score, iteration_count, max_iterations, and quality_threshold from state, checks iteration_count >= max_iterations (sets output_approved to True, returns "approve"), checks quality_score >= quality_threshold (sets output_approved to True, returns "approve"), checks borderline case 7.0 <= quality_score < quality_threshold (sets output_approved to True, returns "approve"), otherwise returns "refine", and handles all edge cases correctly.
 
6. **Graph Construction Implementation**: build_graph function creates StateGraph with DocumentationReflectionState schema. All nodes are registered correctly (generator, reflector). Entry point is set to "generator". Edge is added from "generator" to "reflector". Conditional edges are added from "reflector" using should_continue function with proper mapping (refine->reflector, approve->END). Graph is compiled correctly and returned.