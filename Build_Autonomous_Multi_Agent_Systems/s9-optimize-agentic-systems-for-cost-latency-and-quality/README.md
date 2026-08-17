# Customer Support Ticket Optimization System

A FastAPI-based service that uses an intelligent **Gateway Router Pattern** to optimize support ticket resolution by routing queries to different model tiers (local Ollama vs. Azure OpenAI) based on complexity.

## Project Context

You are building a Customer Support Ticket Optimization System, an AI-powered application designed to balance cost, latency, and reasoning capabilities. The system uses a **Gateway Router** architecture where a heuristic-based router assesses the complexity of an incoming ticket description. 

If the ticket is classified as "Simple" (e.g., billing, account FAQs), it is routed to a local **Ollama (Llama 3.2)** model to save costs. If the ticket is classified as "Complex" (e.g., technical errors, bug reports), it is routed to a high-performance **Azure OpenAI (GPT-4o-mini)** model. All routing is abstracted through a **LiteLLM Gateway**.

This practice focuses on implementing logic for model tier selection, integrating with LiteLLM using the OpenAI client, and building a standardized FastAPI interface for support operations.

## Problem Statement

Build a support ticket resolution pipeline that accepts a problem description, determines the required reasoning power via heuristics, and fulfills the request using the most efficient model tier. You need to implement the heuristic routing logic, the FastAPI endpoint, and the LiteLLM client configuration.

You will complete multiple implementation tasks to build this Support Optimization System:

## Task 1 — Implement Heuristic Router

### Goal

Build the logic to assess ticket complexity without using an LLM, ensuring zero-latency categorization.

### Requirements

1. Implement the `assess_complexity` function in `router.py`.
2. Define keyword lists for **Complex** triggers (e.g., `500`, `error`, `bug`, `crash`, `deployment`, `api`).
3. Define keyword lists for **Simple** triggers (e.g., `billing`, `invoice`, `address`, `account`, `status`).
4. Implement a length-based heuristic where descriptions longer than 50 words are automatically routed to the **Complex** tier.
5. Ensure the function returns either `"complex"` or `"simple"`.

**File:** `router.py`

## Task 2 — Implement FastAPI Gateway

### Goal

Build the REST API and the gateway orchestration logic using LiteLLM.

### Requirements

1. Initialize the `OpenAI` client pointing to the LiteLLM Gateway URL (`http://localhost:4000/v1`).
2. Define the `TicketRequest` Pydantic model with a single `description` field.
3. Implement the `POST /resolve` endpoint.
4. Inside the endpoint:
    - Call the `assess_complexity` function.
    - Set the `model` parameter based on the assessment (`complex-agent` vs `simple-agent`).
    - Call the LiteLLM gateway using the client.
    - Return a JSON response containing the `complexity_assessment`, `routed_model_tier`, and the `resolution`.

**File:** `main.py`

## Task 3 - Configure LiteLLM Gateway

### Goal

Configure the proxy to route to the correct local and cloud backends.

### Requirements

1. Define a `simple-agent` entry in `litellm_config.yaml` using `ollama/llama3.2`.
2. Define a `complex-agent` entry in `litellm_config.yaml` using `azure/gpt-4o-mini`.
3. Use environment variables for all sensitive Azure credentials.

**File:** `litellm_config.yaml`

## Evaluation Criteria

Ensure you evaluate your solution against the below criteria:

1. **Heuristic Accuracy**: `router.py` correctly distinguishes between technical/complex logs and simple billing/account queries.
2. **Gateway Logic**: `main.py` successfully uses the OpenAI client to communicate with LiteLLM and routes to the correct model tier based on the router's output.
3. **API Integrity**: The `POST /resolve` endpoint validates input correctly and returns a structured response that matches the expected format in the documentation.
4. **Performance Optimization**: Simple requests are successfully fulfilled by the local model tier (verifiable via LiteLLM logs), while complex requests leverage cloud reasoning.

---

## Implementation Details

### Environment & Prerequisites

This project requires two backends running concurrently alongside the FastAPI application. Ollama runs as a background service and is started automatically by the Windows Ollama application — no manual start needed if it is already installed. The local model used is `phi3:mini` (a pre-existing model in the environment), which was substituted for `llama3.2` as specified in the original requirements. The LiteLLM proxy is started via a dedicated PowerShell script described below.

Azure OpenAI credentials are sourced from the root `.env` file located two levels above this project folder (at `Building_Agentic_AI_Systems/.env`). The required variables are `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_VERSION`, and `AZURE_OPENAI_LLM_DEPLOYMENT`. No project-level `.env` file is needed for this assignment.

Before starting the project, ensure the following dependency is installed, which enables the LiteLLM proxy server:

```
pip install "litellm[proxy]" --break-system-packages
```

### Task 1 — Heuristic Router (`router.py`)

The `assess_complexity` function applies three rules in strict priority order. First, the description is lowercased for case-insensitive matching. Rule 1 checks for complex keywords such as `500`, `error`, `bug`, `crash`, `api`, `deployment`, `failed`, `critical`, `exception`, `timeout`, and others — any match immediately returns `"complex"`. Rule 2 checks for simple keywords such as `billing`, `invoice`, `account`, `reset`, `password`, `refund`, `subscription`, and others — any match returns `"simple"`. Rule 3 checks if the word count of the description exceeds 50 words and returns `"complex"` if so. If none of the rules match, the function defaults to `"simple"`.

### Task 2 — FastAPI Gateway (`main.py`)

Environment loading uses a `_load_env()` function that resolves the root `.env` path dynamically using `Path(__file__).resolve().parents[4]`, with a fallback to bare `load_dotenv()` if the path does not exist. The `OpenAI` client is initialized pointing to `http://localhost:4000/v1` (the LiteLLM gateway) with a placeholder API key since LiteLLM handles authentication internally. The `TicketRequest` Pydantic model accepts a single `description` string field. The `POST /resolve` endpoint calls `assess_complexity`, selects `complex-agent` or `simple-agent` as the model name, calls the LiteLLM gateway with a professional customer support system prompt, and returns a JSON response containing `complexity_assessment`, `routed_model_tier`, and `resolution`.

### Task 3 — LiteLLM Gateway Configuration (`litellm_config.yaml`)

The `simple-agent` model entry uses `ollama/phi3:mini` with `api_base` pointing to `http://localhost:11434` (the default Ollama port). The `complex-agent` model entry uses `azure/gpt-4o-mini` with all sensitive fields — `api_base`, `api_key`, `api_version`, and `deployment_id` — sourced from environment variables using LiteLLM's `os.environ/VARIABLE_NAME` syntax.

### LiteLLM Startup Script (`start_litellm.ps1`)

A PowerShell startup script is provided to solve a specific environment conflict: the root `.env` contains a `DATABASE_URL` variable (used by other assignments) which causes LiteLLM to attempt a Prisma database connection and crash on startup. The script resolves the root `.env` path dynamically using `$PSScriptRoot` and navigating two parent levels up — equivalent to the `parents[2]` pattern used in Python files. It selectively loads only the four required Azure variables into the current process environment, then explicitly unsets `DATABASE_URL` for that process only (this does not affect any other terminal or system-level environment variables), and finally starts the LiteLLM gateway.

### How to Start the Project

Open two separate terminal windows, both navigated to the s9 project folder.

In Terminal 1, start the LiteLLM gateway using the provided script:

```
.\start_litellm.ps1
```

Wait until the LiteLLM banner appears and the message confirms both `simple-agent` and `complex-agent` are initialized and the server is running on port 4000.

In Terminal 2, start the FastAPI application:

```
python main.py
```

The FastAPI server will start on port 8000.

### How to Test

Open the Swagger UI at `http://localhost:8000/docs` and use the `POST /resolve` endpoint with the Try it out button.

To test the simple routing tier, submit a description containing billing or account-related language such as "I need help resetting my account password and updating my billing information." The response should show `complexity_assessment` as `simple` and `routed_model_tier` as `simple-agent`, with the resolution generated by the local Ollama phi3:mini model.

To test the complex routing tier, submit a description containing technical error language such as "Our deployment is failing with a 500 error and the API is throwing a critical exception in production." The response should show `complexity_assessment` as `complex` and `routed_model_tier` as `complex-agent`, with the resolution generated by Azure OpenAI GPT-4o-mini. The LiteLLM terminal will also log which backend handled each request, providing additional verification of the routing behavior.