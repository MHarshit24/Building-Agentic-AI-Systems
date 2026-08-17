# Product Review Sentiment Analysis with MCP Integration

## Project Context

You're building a **Product Review Sentiment Analysis API**, an AI-powered system that analyzes customer product reviews to determine sentiment (POSITIVE, NEGATIVE, NEUTRAL, MIXED), extract key aspects (price, quality, delivery, etc.), and provide confidence scores. The system uses **Model Context Protocol (MCP)** to dynamically discover and use Hugging Face sentiment analysis models at runtime, without hardcoding any specific models.

This practice focuses on **MCP integration** — connecting to remote MCP servers, loading tools dynamically, creating autonomous agents that can discover and use ML models, and building a production-ready REST API with comprehensive error handling.

## Problem Statement

Build a production-ready sentiment analysis API that can analyze product reviews using dynamically discovered ML models via MCP. The key challenges are:

1. **MCP Integration**: Connecting to remote Hugging Face MCP servers and loading tools programmatically
2. **Dynamic Model Discovery**: Using MCP tools to discover sentiment analysis models at runtime without hardcoding
3. **Agent Orchestration**: Creating autonomous agents that can reason, search for models, and execute inference
4. **Response Parsing**: Extracting structured information (sentiment, confidence, aspects) from agent responses
5. **Error Handling**: Gracefully handling connection failures, model errors, and parsing issues

You will complete the following implementation tasks to build the sentiment analysis system with MCP integration:

---

### **Task 1 — Initialize MCP Service**

#### Goal

Set up the HuggingFaceMCPService by loading configuration credentials and setting up authentication headers.

#### Requirements

1. Load MCP server URL from environment variable with default fallback
2. Load Hugging Face authentication token from environment variable
3. Validate token presence and raise ValueError with descriptive error message if missing
4. Construct authorization headers dictionary with Bearer token authentication

**File**: `main/services/mcp_client.py` → `__init__()`

#### Implementation Notes

The URL is read from `HF_MCP_URL` with `https://huggingface.co/mcp` as the default. The token is read from `HF_TOKEN` and a `ValueError` is raised immediately if it is absent, so the service never starts in a broken state. The authorization header uses the standard Bearer scheme. An important production detail: the HuggingFace MCP streamable HTTP transport requires the token to be appended as a query parameter on the URL in addition to the header — without this the connection times out at the session initialization handshake. This is handled by appending `?token=<value>` to the URL only when no query string is already present.

---

### **Task 2 — Load MCP Tools**

#### Goal

Connect to the remote MCP server and load available tools as LlamaIndex FunctionTools.

#### Requirements

1. Instantiate BasicMCPClient with server URL and authentication headers
2. Create McpToolSpec wrapper from MCP client instance
3. Retrieve all available tools asynchronously from the tool specification
4. Apply optional tool filtering based on allowed_tools parameter
5. Return filtered or complete tool list as BaseTool instances

**File**: `main/services/mcp_client.py` → `load_tools()`

#### Implementation Notes

Before attempting the MCP connection, the token is validated against the HuggingFace `whoami-v2` API endpoint using `httpx`. This surfaces an invalid or expired token immediately with a clear error message rather than a cryptic timeout 30 seconds later. The `BasicMCPClient` is initialised with both the URL (including token query param) and the authorization headers. `McpToolSpec` wraps the client and `to_tool_list_async()` fetches all available tools over the streamable HTTP session. If `allowed_tools` is provided, tools are filtered by comparing `t.metadata.name` against the list. The discovered tool names are logged at INFO level on startup so they are visible for debugging and for constructing accurate agent prompts. Any exception is caught and re-raised as a `ConnectionError` with a human-readable message.

---

### **Task 3 — Create ReAct Agent**

#### Goal

Create a ReActAgent instance configured with tools and LLM for autonomous model discovery and inference.

#### Requirements

1. Initialize LLM instance via create_llm() factory function
2. Instantiate ReActAgent with provided tools and configured LLM
3. Return configured ReActAgent instance ready for execution

**File**: `main/services/agent_factory.py` → `create_agent()`

#### Implementation Notes

`create_llm()` constructs an `AzureOpenAI` instance from the four required environment variables (`AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_LLM_DEPLOYMENT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_API_VERSION`) and raises a `ValueError` if any are missing. The LLM is configured with `temperature=0` to keep agent reasoning deterministic. `ReActAgent` is instantiated with the combined tool list (MCP tools plus the custom inference tool) and the LLM. The agent uses the workflow-based ReAct loop from `llama_index.core.agent.workflow`.

---

### **Task 4 — Implement HF Inference API Function**

#### Goal

Create the main inference function that routes to appropriate implementation based on library availability.

#### Requirements

1. Determine library availability via HF_HUB_AVAILABLE flag
2. Route to hub client implementation if available, otherwise use requests fallback
3. Return JSON-formatted inference result or error message

**File**: `main/tools/custom_tools.py` → `hf_inference_api()`

#### Implementation Notes

The `HF_HUB_AVAILABLE` flag is set at module import time by attempting to import `InferenceClient` from `huggingface_hub`. If the import succeeds the hub client path is taken; otherwise the pure-`requests` fallback is used. Both paths return a JSON string in the same format so the agent sees a consistent interface regardless of which library is available.

---

### **Task 5 — Implement Hub Client Inference**

#### Goal

Implement inference using the HuggingFace Hub client library for text classification.

#### Requirements

1. Load and validate Hugging Face authentication token from environment
2. Return structured JSON error response if token is missing
3. Initialize InferenceClient with authentication token
4. Execute text classification inference
5. Transform classification results into JSON format with label and score fields
6. Return structured error response with model information and recovery suggestions on failure

**File**: `main/tools/custom_tools.py` → `_call_with_hub_client()`

#### Implementation Notes

`HF_TOKEN` is read from the environment rather than passed as a parameter so the tool remains stateless and safe to call from the agent loop. If the token is absent a structured JSON error is returned immediately rather than raising an exception, because the agent needs to read the error message and decide what to do next. `InferenceClient` is initialised with the token and `text_classification()` is called with the model ID. The results — a list of label/score objects — are normalised into plain dictionaries before serialisation. On any exception the error response includes the model ID and a suggestion to use model search to find an alternative, which the agent can act on directly.

---

### **Task 6 — Implement Requests-Based Inference**

#### Goal

Implement fallback inference method using requests library directly for HuggingFace Inference API.

#### Requirements

1. Load and validate Hugging Face token from environment
2. Construct HuggingFace Inference API endpoint URL
3. Configure HTTP request headers with Bearer authentication and content type
4. Prepare request payload with input text
5. Execute POST request with timeout configuration
6. Handle response status codes with retry logic for loading models
7. Return structured error responses on failure

**File**: `main/tools/custom_tools.py` → `_call_with_requests()`

#### Implementation Notes

The HuggingFace Inference API endpoint is constructed as `https://api-inference.huggingface.co/models/{model_id}`. A 503 response means the model is still loading on HuggingFace's infrastructure; the implementation waits 5 seconds with `time.sleep()` and retries once before giving up, which handles the common cold-start delay for less popular models. Any non-200/503 status is returned as a structured error with the status code so the agent has enough context to decide whether to retry or search for a different model. Network exceptions are caught at the outermost level and also returned as structured JSON rather than being raised, keeping the agent loop stable.

---

### **Task 7 — Create LlamaIndex Tool**

#### Goal

Create a FunctionTool from the hf_inference_api function for use by the agent.

#### Requirements

1. Create FunctionTool instance using FunctionTool.from_defaults() factory method
2. Configure tool with hf_inference_api function reference
3. Set tool identifier as "hf_inference"
4. Define comprehensive tool description including usage constraints, optimization details, error handling instructions, parameter specifications, and return value format
5. Assign tool instance to custom_inference_tool module variable

**File**: `main/tools/custom_tools.py` → `custom_inference_tool`

#### Implementation Notes

`FunctionTool.from_defaults()` wraps `hf_inference_api` and registers it under the name `hf_inference`. The description is the primary mechanism by which the ReAct agent understands when and how to use the tool, so it explicitly states that a model ID from `model_search` is required before calling it, what to do on failure, the expected parameter types, and the return format. A well-written description here directly reduces the number of agent reasoning steps needed, which improves response time.

---

### **Task 8 — Initialize Agent Service**

#### Goal

Set up the agent service by connecting to MCP, loading tools, and creating the agent.

#### Requirements

1. Implement idempotent initialization check with early return
2. Instantiate HuggingFaceMCPService for MCP connectivity
3. Load MCP tools asynchronously and store in instance variable
4. Integrate custom inference tool into tool collection
5. Create ReActAgent instance with configured tools
6. Set service state flags for initialization and MCP connectivity

**File**: `main/services/agent_service.py` → `initialize()`

#### Implementation Notes

The idempotency check at the top means repeated calls during testing or hot-reload scenarios do not re-establish the MCP connection unnecessarily. The MCP tool names discovered at runtime are stored in `_mcp_tool_names` and logged at INFO level — this is critical for debugging because the agent prompt references these names, and if the name changes on HuggingFace's side the logs will make the mismatch immediately visible. The custom inference tool is appended after MCP tool loading so the agent always has both discovery and inference capability. Both `_initialized` and `_mcp_connected` flags are set only after all steps succeed, so `is_initialized()` is a reliable readiness check. Any exception is logged with full traceback and re-raised so the FastAPI lifespan handler can log it and continue running (degraded) rather than crashing the process.

---

### **Task 9 — Implement Review Sentiment Analysis**

#### Goal

Orchestrate the complete sentiment analysis pipeline: prompt creation → agent execution → response parsing.

#### Requirements

1. Validate agent initialization state prior to processing
2. Build product context string from optional product_name and product_id parameters
3. Construct multi-line prompt with review text, model search instructions, inference tool usage, aspect extraction requirements, and response format specifications
4. Create Context object and execute agent with prompt
5. Parse agent response using \_parse_response helper method
6. Return structured result dictionary with success flag or error response

**File**: `main/services/agent_service.py` → `analyze_review_sentiment()`

#### Implementation Notes

The product context string is built incrementally — only the fields that are actually provided are appended — so the prompt stays concise when optional fields are absent. The prompt lists the actual MCP tool names loaded at runtime (from `_mcp_tool_names`) rather than hardcoding `model_search`, which prevents the agent from looping endlessly trying to call a tool that doesn't exist under that exact name. `max_iterations=50` gives the agent enough budget for model search, inference, and occasional retries. `early_stopping_method="generate"` ensures that if the budget is still exhausted, the agent produces a best-effort final answer rather than raising an exception. The response text is always logged at INFO level before parsing so failures can be diagnosed directly from the server logs without needing to reproduce the request.

---

### **Task 10 — Parse Agent Response**

#### Goal

Extract structured information (sentiment, confidence, model, aspects) from the agent's text response using regex.

#### Requirements

1. Extract sentiment, confidence, model, and aspects patterns from response string using regex
2. Map extracted sentiment string to SentimentLabel enum with variation handling
3. Parse confidence score as float with default value
4. Extract model identifier with default fallback
5. Parse aspects list from comma-separated string with validation
6. Return structured dictionary with all extracted fields or None if parsing fails

**File**: `main/services/agent_service.py` → `_parse_response()`

#### Implementation Notes

Before regex matching, all asterisk characters are stripped from the response. This handles the common case where the LLM wraps field names in markdown bold (`**Sentiment:**`) instead of plain text, which would otherwise cause every match to fail silently. The four regex patterns all use `re.IGNORECASE` and allow arbitrary whitespace after the colon. Sentiment mapping first attempts an exact `SentimentLabel` enum lookup and falls back to substring matching for abbreviated or alternate forms. If the structured format is not found at all — for example when the agent produces a narrative answer instead — a keyword fallback scans the raw response for POSITIVE/NEGATIVE/MIXED and returns a best-guess result with a confidence of 0.5, ensuring the API always returns a usable response rather than a 500 error.

---

### **Task 11 — Implement Review Analysis API Endpoint**

#### Goal

Create a FastAPI endpoint that accepts product review requests and returns structured sentiment analysis responses.

#### Requirements

1. Validate agent service initialization state prior to processing requests
2. Invoke agent_service.analyze_review_sentiment() with request parameters
3. Validate result success status and handle failure cases appropriately
4. Transform service response dictionary into SentimentResponse Pydantic model
5. Implement exception handling for proper error propagation

**File**: `main/routes/routes.py` → `analyze_review()`

#### Implementation Notes

The initialization check uses `is_initialized()` rather than checking the flag directly, keeping the route layer decoupled from internal state details. A 503 is returned rather than 500 when the service is not ready, which correctly signals to clients that the condition is temporary and worth retrying. `HTTPException` instances are re-raised unchanged so FastAPI preserves the original status code and detail message. All other exceptions are caught and wrapped as 500 with the error string included in the detail, which aids debugging without exposing internal stack traces to the client. The `SentimentAnalysisResult` is constructed by explicitly mapping each key from the result dictionary, which makes the field mapping visible and prevents silent mismatches if the dictionary schema changes.

---

## Evaluation Criteria

Ensure you evaluate your solution against the below criteria:

1. **MCP Service Initialization**: The HuggingFaceMCPService successfully initializes with URL and token from environment variables, validates token presence, and sets up authorization headers correctly.

2. **MCP Tools Loading**: The load_tools method successfully connects to the MCP server, creates BasicMCPClient and McpToolSpec instances, retrieves tools asynchronously, and handles filtering when allowed_tools is provided.

3. **Agent Creation**: The create_agent function successfully creates a ReActAgent instance with the provided tools and LLM from create_llm().

4. **Inference Functions**: The hf_inference_api function correctly routes to hub client or requests-based implementation, both implementations handle token validation, API calls, and error responses appropriately.

5. **Tool Creation**: The custom_inference_tool is successfully created using FunctionTool.from_defaults() with proper function, name, and description.

6. **Agent Service Initialization**: The initialize method successfully connects to MCP, loads tools, adds custom inference tool, creates agent, and sets initialization flags with proper error handling.

7. **Sentiment Analysis Pipeline**: The analyze_review_sentiment method correctly validates initialization, builds prompts, executes agent, parses responses, and returns structured results with success/error handling.

8. **End-to-End Flow**: The complete system processes review queries through initialization → MCP connection → tool loading → agent creation → query execution → response parsing → API response, returning structured sentiment analysis with all required fields.

---

## Environment Setup

### Required Environment Variables

Two `.env` files are used. Secrets live in the root `.env` and are preserved across loads so the project `.env` cannot overwrite them.

**Root `.env`** (contains secrets, never overwritten):
- `AZURE_OPENAI_API_KEY` — Azure OpenAI API key
- `AZURE_OPENAI_ENDPOINT` — Azure OpenAI endpoint URL
- `HF_TOKEN` — HuggingFace access token (READ permission required), obtain from https://huggingface.co/settings/tokens
- `HF_MCP_URL` — HuggingFace MCP server URL (set to `https://huggingface.co/mcp`)

**Project `.env`** (non-secret deployment config):
- `AZURE_OPENAI_LLM_DEPLOYMENT` — deployment name, e.g. `gpt-4o-mini`
- `AZURE_OPENAI_API_VERSION` — API version, e.g. `2024-02-01`

### Required Package

`llama-index-tools-mcp` is not included in the base dependencies and must be installed separately:

```
pip install llama-index-tools-mcp
```

---

## Implementation Results

All 11 tasks were completed and verified against the 8 evaluation criteria. The system was tested end-to-end with the following confirmed behaviours:

- A positive review for "Wireless Headphones" returned `POSITIVE` sentiment with confidence 0.95, model `cardiffnlp/twitter-roberta-base-sentiment`, and aspects `["price", "quality", "delivery"]`.
- A negative review with no product context returned `NEGATIVE` sentiment with confidence 0.95 and aspects `["quality", "customer service", "value for money"]`.
- An empty review string correctly returned HTTP 422 with Pydantic validation details.
- The health check endpoint returned the correct service metadata.

The HuggingFace MCP connection requires the token as both a Bearer header and a URL query parameter for the streamable HTTP transport to complete its session handshake. The agent prompt uses the actual tool names discovered at runtime rather than hardcoded names, and the response parser strips markdown formatting before regex matching to handle LLM output variation. Response time per request is several minutes due to the agent performing live model search and inference over the network, which is expected for a ReAct agent with external tool calls.