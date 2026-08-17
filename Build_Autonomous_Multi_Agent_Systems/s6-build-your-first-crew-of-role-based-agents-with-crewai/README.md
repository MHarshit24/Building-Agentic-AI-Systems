# Product Review Analysis

## Project Context

You're building a Product Review Analysis Crew, an AI-powered system that uses a 3-agent CrewAI crew to analyze product reviews, extract insights, and generate actionable business reports. The system uses role-based autonomous collaboration where specialized agents work together sequentially to research reviews, analyze sentiment, and produce executive summaries.

This practice focuses on building multi-agent crews with CrewAI — implementing agents with distinct roles, goals, and backstories, creating sequential tasks with context dependencies, integrating web search tools for review research, and exposing the crew as a REST API. You'll learn how to configure Azure OpenAI LLM for CrewAI, define specialized agents with tools, create tasks with automatic context passing, build crews with sequential processes, and implement FastAPI endpoints that process product review analysis requests.

## Problem Statement

Build a Product Review Analysis crew that responds to product names by searching for reviews, analyzing sentiment and themes, and generating actionable insights reports. You need to implement Azure OpenAI LLM configuration, web search tool integration, three specialized agents (Review Researcher, Sentiment Analyzer, Insights Reporter), three sequential tasks with context dependencies, crew assembly with sequential process, Pydantic request/response models, and FastAPI endpoints that process analysis requests and return structured results.

You will complete multiple implementation tasks to build this Product Review Analysis crew:

## Task 1 — Implement Crew Service

### Goal

Build the complete CrewAI crew service with LLM initialization, web search tool, three agents, three tasks, and crew assembly.

### Requirements

1. Load environment variables using `load_dotenv()`
2. Retrieve Azure OpenAI credentials from environment (AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_DEPLOYMENT_NAME, AZURE_OPENAI_API_VERSION)
3. Validate all required environment variables are present, raise ValueError if missing
4. Initialize LLM with Azure OpenAI configuration (model, provider="azure_openai", azure_endpoint, api_key, api_version, temperature=0.3)
5. Initialize SerperDevTool for web search
6. Create Review Researcher Agent with role="Product Review Analyst", goal="Find and compile recent product reviews from multiple sources", appropriate backstory, tools=[search_tool], llm, verbose=True, allow_delegation=False
7. Create Sentiment Analyzer Agent with role="Customer Sentiment Specialist", goal="Analyze review sentiment and extract key themes", appropriate backstory, llm, verbose=True, allow_delegation=False
8. Create Insights Reporter Agent with role="Business Insights Writer", goal="Transform analysis into actionable business recommendations", appropriate backstory, llm, verbose=True, allow_delegation=False
9. Create Research Task with description to search for reviews of {product}, find 3-5 detailed reviews covering different aspects, expected_output describing compilation of 3-5 reviews with source references, agent=review_researcher, tools=[search_tool]
10. Create Analyze Task with description to analyze sentiment, praised features, complaints, and recurring themes, expected_output describing structured analysis with sentiment scores and categorized themes, agent=sentiment_analyzer, context=[research_task]
11. Create Report Task with description to create executive summary with sentiment overview, key strengths, weaknesses, and recommendations, expected_output describing professional report (300-400 words) with actionable recommendations, agent=insights_reporter, context=[analyze_task], output_file="product_insights.md"
12. Create Crew with list of all three agents, list of all three tasks, process=Process.sequential, verbose=True, tracing=True
13. Return crew.kickoff(inputs={"product": product})

**File:** `services.py`

## Task 2 — Implement Pydantic Models

### Goal

Define request and response models for the FastAPI endpoint.

### Requirements

1. Import BaseModel and Field from pydantic
2. Create ProductReviewRequest with product field (str, required)
3. Create ProductReviewResponse with insights (str, required), status (str, default="success"), message (str, default="Review analysis completed successfully")

**File:** `models.py`

## Task 3 — Implement FastAPI Endpoint

### Goal

Build REST API endpoint that processes product review analysis requests.

### Requirements

1. Import ProductReviewRequest and ProductReviewResponse from models
2. Import create_review_analysis_crew from services
3. Validate product name is not empty in POST /analyze endpoint
4. Call create_review_analysis_crew with product name
5. Return ProductReviewResponse with insights from result.raw

**File:** `main.py`

## Evaluation Criteria

Ensure you evaluate your solution against the below criteria:

1. **Crew Service Implementation**: services.py properly loads environment variables, validates Azure OpenAI credentials, initializes LLM with Azure configuration, creates SerperDevTool, implements three specialized agents (Review Researcher, Sentiment Analyzer, Insights Reporter) with appropriate roles, goals, and backstories, creates three sequential tasks with proper context dependencies, assembles Crew with sequential process, and returns crew execution results.

2. **Pydantic Models Implementation**: ProductReviewRequest BaseModel is defined with product field (str, required, description). ProductReviewResponse BaseModel is defined with insights (str, required), status (str, default="success"), message (str, default="Review analysis completed successfully").

3. **FastAPI Endpoint Implementation**: POST /analyze endpoint validates product name is not empty, calls create_review_analysis_crew with product name, handles exceptions with HTTPException, returns ProductReviewResponse with insights from result.raw, status="success", and appropriate message.

## Implementation Notes

### Environment Setup

This project loads environment variables exclusively from the root `.env` file located at `Building_Agentic_AI_Systems/`. There is no project-level `.env` in the s6 folder. The path is resolved dynamically using `Path(__file__).resolve().parents[2]`, with a fallback to `load_dotenv()` in case the root `.env` is not found. The primary variable names follow the convention used across all assignments (`AZURE_OPENAI_LLM_DEPLOYMENT`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_API_VERSION`), with the README's `AZURE_OPENAI_DEPLOYMENT_NAME` wired in as a fallback via `os.getenv()`.

In addition to the Azure OpenAI variables, `SERPER_API_KEY` must also be present in the root `.env`. This is read automatically by `SerperDevTool` at runtime and is required for the Review Researcher agent to perform web searches.

### Package Installation

This project requires `crewai==1.14.7` and `crewai-tools==1.14.7`, installed with the `--ignore-requires-python` flag to bypass the `<3.14` version gate in the package metadata. Although the package pins certain dependencies (pydantic, opentelemetry, mcp) to older versions, those pins are metadata-only and do not cause runtime breakage when the newer versions already installed across other assignments are used instead. The one additional package that must be explicitly installed is `azure-ai-inference`, which crewai 1.x uses as its native Azure OpenAI SDK. It is a pure Python wheel with no version restrictions.

### LLM Initialization

CrewAI 1.x introduced a native Azure provider that routes through the `azure-ai-inference` SDK rather than through litellm. The `LLM` class in crewai 1.x is a factory — when the model name or `provider` argument maps to a recognized native provider, it instantiates the corresponding native completion class. For Azure, this means `provider="azure_openai"` routes to `AzureCompletion`, which in turn requires `azure-ai-inference` to be installed. The `LLM` is initialized with `provider="azure_openai"`, `api_key`, `api_base` (the correct parameter name in crewai 1.x, as opposed to `azure_endpoint` referenced in older documentation), `api_version`, and `temperature=0.3`.

### Agent Design

Three agents are defined, each with a distinct role and backstory that shapes how the LLM approaches its assigned task. The Review Researcher is the only agent equipped with `SerperDevTool`, since web search is only needed in the first task. The Sentiment Analyzer and Insights Reporter work purely from the context passed down by preceding tasks and do not require tool access. All three agents have `allow_delegation=False` and `verbose=True`.

### Task Chaining and Context Dependencies

The three tasks form a strict sequential pipeline. The Research Task has no context dependency and runs first, with `SerperDevTool` attached directly to it. The Analyze Task receives `context=[research_task]`, meaning CrewAI automatically injects the Research Task's output into the Sentiment Analyzer's working context before it begins. The Report Task receives `context=[analyze_task]` in the same fashion. This context chaining is what allows each downstream agent to work from the previous agent's output without any manual data passing. The Report Task also specifies `output_file="product_insights.md"`, which causes CrewAI to write the final report to disk in addition to returning it in the API response.

### FastAPI and Event Loop Compatibility

FastAPI runs on an async event loop, and CrewAI's `crew.kickoff()` is a synchronous blocking call that internally spawns its own event loop. Calling a synchronous function that creates a new event loop from within an already-running async context raises a `RuntimeError`. The fix is to run `crew.kickoff()` inside a `ThreadPoolExecutor` using `concurrent.futures`, which executes it in a separate thread with its own event loop context, completely isolated from FastAPI's event loop.

### API Endpoints

The server exposes three endpoints. `GET /` returns metadata about the API. `GET /health` returns a simple health check response and can be used to confirm the server is running before attempting a crew execution. `POST /analyze` accepts a JSON body with a `product` field, validates that it is not empty or whitespace, runs the full three-agent crew, and returns a structured `ProductReviewResponse` containing the executive report under the `insights` key along with `status` and `message` fields. The endpoint is tested via Swagger UI at `http://127.0.0.1:8000/docs`.

### Running the Server

Navigate to the s6 project folder and start the server with `uvicorn main:app --reload`. The `--reload` flag is suitable for development but requires a full process restart (Ctrl+C followed by re-running the command) whenever `services.py` is modified, since environment variable loading happens at module import time and reload does not always re-execute module-level code reliably.