# Job Placement Agent — Technical Document

**Version:** 1.0.0  
**Course:** NIIT — Build and Deploy Intelligent Conversational Agents  
**Sprint:** 11 (Capstone)  
**Branch:** development-arockia

---

## Table of Contents

1. [Purpose](#1-purpose)
2. [System Overview](#2-system-overview)
3. [Architecture](#3-architecture)
4. [Technology Stack](#4-technology-stack)
5. [Module Reference](#5-module-reference)
6. [API Specification](#6-api-specification)
7. [gRPC Service Definition](#7-grpc-service-definition)
8. [LangChain Agent Design](#8-langchain-agent-design)
9. [LCEL Chains](#9-lcel-chains)
10. [Authentication & Authorization](#10-authentication--authorization)
11. [Observability](#11-observability)
12. [Data Models](#12-data-models)
13. [Error Handling](#13-error-handling)
14. [Testing Strategy](#14-testing-strategy)
15. [Deployment](#15-deployment)
16. [Environment Variables](#16-environment-variables)
17. [Sprint Concept Mapping](#17-sprint-concept-mapping)
18. [Technical Concepts & Glossary](#18-technical-concepts--glossary)

---

## 1. Purpose

The **Job Placement Agent** was built as the Sprint 11 capstone project for the NIIT course *Build and Deploy Intelligent Conversational Agents*. Its purpose is to demonstrate end-to-end design and deployment of a production-grade AI system by solving a concrete, real-world problem: helping job seekers navigate the modern hiring process through an intelligent conversational interface.

### Goals

- **For job seekers** — Provide a single conversational assistant that can search live job postings, critically evaluate a resume against a target role, identify skill gaps with an actionable match score, and generate a personalised cover letter — all within one session.
- **For the course** — Consolidate every sprint's learning objective (LLM integration, tool calling, LCEL chains, agent memory, streaming, observability, authentication, and gRPC transport) into one coherent, testable, and deployable codebase.

### Scope

| In Scope | Out of Scope |
|----------|-------------|
| Conversational AI agent with multi-turn memory | Persistent user accounts / database storage |
| Real-time job search via SerpAPI Google Jobs | Direct job application submission |
| Resume analysis and skill-gap scoring | Document parsing (PDF/DOCX) — plain text input only |
| Personalised cover letter generation | Interview preparation or salary negotiation guidance |
| Auth0 JWT authentication | OAuth social login flows |
| Langfuse LLM observability | Business analytics or dashboards |
| REST + gRPC + gRPC-Web transports | Mobile-native clients |
| Serverless deployment to Vercel | Container/Kubernetes deployment |

### Design Principles

1. **Shared business logic** — All three transports (REST, gRPC, gRPC-Web) invoke the same agent and tool layer; only the serialization boundary differs.
2. **Graceful degradation** — Observability (Langfuse) and authentication (Auth0) are optional; the core agent functions without them.
3. **Typed error propagation** — Every external failure maps to a domain exception subclass, ensuring consistent HTTP/gRPC error codes and human-readable messages.
4. **High test coverage** — 376 tests at 99% statement coverage validate correctness from unit to integration level without relying on live external services.

---

## 2. System Overview

The **Job Placement Agent** is a production-grade, conversational AI system that guides job seekers through four interconnected career tasks:

| Task | Mechanism |
|------|-----------|
| Job Discovery | SerpAPI Google Jobs real-time search |
| Resume Analysis | LLM-powered skill extraction via LCEL chain |
| Skill Gap Detection | Resume-vs-JD comparison with match score |
| Cover Letter Generation | LLM-powered personalized letter creation |

The system exposes three transports:

- **FastAPI REST** — primary HTTP/JSON API (Vercel serverless)
- **gRPC** — binary protobuf over TCP (Python/Streamlit clients)
- **gRPC-Web** — protobuf over HTTP/1.1 (browser clients)

All three transports share the same business logic; only the serialization layer differs.

---

## 3. Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          CLIENTS                                    │
│  Streamlit app · index.html (gRPC-Web) · REST clients / Postman    │
└──────────┬──────────────────────────┬───────────────────────────────┘
           │ HTTP/JSON                │ gRPC / gRPC-Web
           ▼                          ▼
┌──────────────────┐        ┌─────────────────────┐
│  FastAPI Backend │        │   gRPC Server        │
│  fastapi_app.py  │        │   grpc_server.py     │
│  Vercel (Mangum) │        │   grpc_web_server.py │
└────────┬─────────┘        └──────────┬────────────┘
         │                             │
         └──────────────┬──────────────┘
                        │  shared business logic
                        ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     LANGCHAIN AGENT LAYER                           │
│  agent/job_agent.py                                                 │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  create_tool_calling_agent  +  AgentExecutor                 │  │
│  │  RunnableWithMessageHistory (per-session ChatMessageHistory)  │  │
│  │  Langfuse CallbackHandler (observability)                     │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  LCEL Intent Router (agent/router.py)                               │
│  ChatPromptTemplate | LLM | StrOutputParser  →  RunnableBranch     │
└────────────────────────┬────────────────────────────────────────────┘
                         │ tool calls
        ┌────────────────┼────────────────┐
        ▼                ▼                ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────────┐
│  search_jobs │  │analyze_resume│  │generate_cover_   │
│  (SerpAPI)   │  │(LCEL chain)  │  │letter (LCEL chain)│
└──────┬───────┘  └──────┬───────┘  └────────┬──────────┘
       │                 │                   │
       ▼                 ▼                   ▼
  SerpAPI API       Gemini LLM          Gemini LLM
  Google Jobs       (via OpenAI         (via OpenAI
  results           compat API)         compat API)

                ┌──────────────────────────────┐
                │  Auth0  (RS256 JWT / JWKS)   │
                │  Langfuse (CallbackHandler)   │
                └──────────────────────────────┘
```

### Component Responsibilities

| Component | File | Role |
|-----------|------|------|
| FastAPI app | `fastapi_app.py` | HTTP transport, route handlers, CORS |
| gRPC servicer | `grpc_server.py` | Protobuf RPC handlers |
| gRPC-Web server | `grpc_web_server.py` | HTTP/1.1 gRPC-Web proxy via sonora |
| Entry point | `main.py` | Starts gRPC + gRPC-Web in parallel threads |
| Vercel adapter | `index.py` | Mangum ASGI-to-Lambda wrapper |
| Agent | `agent/job_agent.py` | LangChain agent, session memory, async |
| LLM factory | `agent/llm.py` | ChatOpenAI cached instance, error mapping |
| Intent router | `agent/router.py` | LCEL RunnableBranch classification |
| Job search tool | `agent/tools/job_search.py` | SerpAPI Google Jobs integration |
| Resume tool | `agent/tools/resume_analyzer.py` | LCEL chain, prompt engineering |
| Cover letter tool | `agent/tools/cover_letter.py` | LCEL chain, personalization |
| Auth | `auth/auth0.py` | JWKS fetch, RS256 JWT verify |
| Observability | `observability/langfuse_config.py` | Langfuse handler factory |
| Exceptions | `exceptions.py` | Domain exception hierarchy |
| Schemas | `models/schemas.py` | Pydantic v2 request/response models |
| Responses | `models/responses.py` | ApiResponse envelope |

---

## 4. Technology Stack

| Layer | Technology | Version | Purpose |
|-------|-----------|---------|---------|
| LLM | Google Gemini | gemini-2.0-flash | Text generation via OpenAI-compat API |
| Agent Framework | LangChain | 0.2.x | Tool calling, LCEL, memory |
| LLM Client | langchain-openai / ChatOpenAI | 0.1.x | Gemini via OpenAI endpoint |
| HTTP Backend | FastAPI | ≥0.110 | REST API, dependency injection |
| ASGI Server | Uvicorn | ≥0.29 | Local development server |
| Serverless | Mangum | ≥0.17 | FastAPI → Vercel/Lambda adapter |
| RPC Transport | grpcio | latest | Binary protobuf over TCP |
| gRPC-Web | sonora | latest | gRPC-Web browser proxy |
| Job Search | SerpAPI (`google-search-results`) | ≥2.4 | Real-time Google Jobs |
| Auth | python-jose[cryptography] | ≥3.3 | RS256 JWT verification |
| Observability | langfuse | 2.x | LLM tracing and monitoring |
| Data Validation | pydantic | 2.x | Request/response schemas |
| Testing | pytest + pytest-cov + pytest-mock | latest | Unit & integration tests |
| Deployment | Vercel | — | Serverless hosting |
| Config | python-dotenv | ≥1.0 | Environment variable loading |

---

## 5. Module Reference

### 4.1 `agent/llm.py`

```python
get_llm() -> ChatOpenAI          # @lru_cache(maxsize=1) — cached singleton
invoke_llm(prompt, callbacks)    # wraps llm.invoke(); maps all OpenAI/Gemini
                                 # exceptions to typed GeminiError subclasses
_translate_llm_error(exc)        # isinstance checks (openai SDK) + string fallback
```

**Error mapping table:**

| openai SDK exception | GeminiError subclass | HTTP status |
|---------------------|---------------------|------------|
| `RateLimitError` | `GeminiRateLimitError` | 429 |
| `AuthenticationError` | `GeminiConfigError` | 500 |
| `PermissionDeniedError` | `GeminiConfigError` | 500 |
| `NotFoundError` | `GeminiConfigError` | 500 |
| `APIConnectionError` / `APITimeoutError` | `GeminiNetworkError` | 503 |
| `InternalServerError` | `GeminiNetworkError` | 503 |
| `BadRequestError` | `GeminiInvalidRequestError` | 400 |

### 4.2 `agent/job_agent.py`

```python
# Session management
get_session_history(session_id) -> ChatMessageHistory
clear_session(session_id)
list_sessions() -> list[str]

# Agent construction (lazy — called once on first request)
_build_agent_executor() -> AgentExecutor
_get_agent() -> RunnableWithMessageHistory   # singleton wrapper

# Public interface
run_agent(user_message, session_id, user_id) -> str
run_agent_async(user_message, session_id, user_id) -> str    # Sprint 2 LO3
stream_agent(user_message, session_id, user_id) -> AsyncGenerator[str, None]  # Sprint 7
```

**Agent configuration:**

```python
AgentExecutor(
    agent=create_tool_calling_agent(llm, tools, prompt),
    tools=[search_jobs, analyze_resume, generate_cover_letter],
    verbose=True,
    max_iterations=6,
    handle_parsing_errors=True,
)
```

### 4.3 `agent/router.py`

```python
INTENT_JOB_SEARCH  = "job_search"
INTENT_RESUME      = "resume_analysis"
INTENT_COVER_LETTER = "cover_letter"
INTENT_GENERAL     = "general"

_get_classify_chain() -> LCEL_chain    # @lru_cache — ChatPromptTemplate | LLM | StrOutputParser
get_router_pipeline() -> Runnable      # @lru_cache — RunnablePassthrough.assign(intent=...) | branch
route_query(query, callbacks) -> tuple[str, str]  # (intent, response)
```

**Routing logic:**

```
classify_chain.invoke({"query": query}) → intent (stripped)
branch = RunnableBranch(
    (lambda x: x["intent"] == "job_search",    job_search_chain),
    (lambda x: x["intent"] == "resume_analysis", resume_chain),
    (lambda x: x["intent"] == "cover_letter",  cover_letter_chain),
    general_chain,   # default
)
```

### 4.4 `agent/tools/resume_analyzer.py`

```python
_get_analysis_chain() -> LCEL_chain    # @lru_cache
    # = ChatPromptTemplate.from_messages([("human", "{analysis_prompt}")]) | get_llm() | StrOutputParser()

analyze_resume_core(resume_text, job_description, callbacks) -> str
    # Builds structured prompt → invokes LCEL chain → returns analysis

analyze_resume  # @tool wrapper — catches ValueError, GeminiError, Exception
```

**Prompt structure:**

```
1. Skill Extraction        — list every technical/soft skill found
2. Experience Assessment   — years, seniority level, progression
3. Resume Quality Score    — /10 with breakdown
4. Improvement Suggestions — top 3 actionable tips
5. Skill Gap Analysis      — (only when job_description ≥ 20 chars)
   • Missing skills  
   • Match percentage
   • Skills to develop
```

### 4.5 `auth/auth0.py`

```python
_get_jwks() -> dict              # @lru_cache — fetches JWKS from Auth0
fetch_token(username, password) -> dict   # returns {access_token, token_type, expires_in}
verify_token(token) -> dict      # RS256 verify → returns payload dict
get_current_user(token) -> dict  # FastAPI Depends() integration
```

### 4.6 `observability/langfuse_config.py`

```python
get_langfuse_handler(session_id, user_id) -> CallbackHandler | None
flush_langfuse()
```

Returns `None` when `LANGFUSE_SECRET_KEY` is empty — completely safe to call without Langfuse configured.

---

## 6. API Specification

All REST responses follow the `ApiResponse` envelope:

```json
{
  "success": true,
  "data":    { ... },
  "error":   null,
  "meta":    { "request_id": "uuid", "api_version": "1.0.0" }
}
```

### Public Endpoints

#### `GET /api/health`

```
Response 200
{
  "data": { "status": "healthy", "version": "1.0.0", "message": "..." }
}
```

#### `POST /api/auth/token`

```
Request  { "username": "email", "password": "pass" }
Response { "data": { "access_token": "eyJ...", "token_type": "Bearer", "expires_in": 86400 } }
Errors   401 AUTH0_INVALID_CREDENTIALS, 500 AUTH0_CONFIGURATION_ERROR, 503 AUTH0_UNAVAILABLE
```

#### `POST /api/chat/public`

```
Request  { "message": "Find jobs in NYC", "session_id": "optional-uuid" }
Response { "data": { "response": "...", "session_id": "uuid" } }
```

#### `POST /api/session`

```
Response { "data": { "session_id": "uuid", "message": "Session created." } }
```

#### `POST /api/chat/stream` (SSE)

```
Request  { "message": "...", "session_id": "optional" }
Response Content-Type: text/event-stream

data: {"token": "Here", "session_id": "uuid"}\n\n
data: {"token": " are", "session_id": "uuid"}\n\n
...
data: {"done": true, "session_id": "uuid"}\n\n
# On error:
data: {"error": "STREAM_ERROR", "message": "..."}\n\n
```

#### `POST /api/chat/route`

```
Request  { "message": "Write me a cover letter", "session_id": "optional" }
Response { "data": { "response": "[cover_letter] Dear...", "session_id": "uuid" } }
```

### Protected Endpoints (Bearer JWT required)

#### `POST /api/chat`

```
Request  { "message": "...", "session_id": "optional" }
Response { "data": { "response": "...", "session_id": "uuid" } }
Errors   401 AUTH0_INVALID_CREDENTIALS
```

#### `POST /api/chat/async`

Identical to `/api/chat` but uses `await run_agent_async()` internally.

#### `POST /api/jobs/search`

```
Request  { "query": "Python developer", "location": "Austin", "session_id": "optional" }
Response { "data": { "results": "markdown listing...", "session_id": "uuid" } }
```

#### `POST /api/resume/analyze`

```
Request  {
  "resume_text":     "Full resume (min 50 chars)",
  "job_description": "Target job description (optional)",
  "session_id":      "optional"
}
Response { "data": { "analysis": "Structured analysis...", "session_id": "uuid" } }
```

#### `POST /api/cover-letter/gen`

```
Request  {
  "resume_text":     "...",
  "job_title":       "Senior Engineer",
  "company_name":    "Acme Corp",
  "job_description": "...",
  "user_name":       "Jane Doe",
  "session_id":      "optional"
}
Response { "data": { "cover_letter": "Dear Hiring Manager...", "session_id": "uuid" } }
```

#### `DELETE /api/chat/{session_id}`

```
Response { "data": { "message": "Session cleared successfully.", "session_id": "uuid" } }
```

#### `GET /api/sessions`

```
Response { "data": { "sessions": ["uuid1", "uuid2"] } }
```

### HTTP Error Codes

| HTTP | error_code | Trigger |
|------|-----------|---------|
| 400 | `LLM_INVALID_REQUEST` | Prompt blocked / too long |
| 401 | `AUTH0_INVALID_CREDENTIALS` | Bad/expired JWT |
| 422 | Pydantic `VALIDATION_ERROR` | Invalid request schema |
| 429 | `LLM_RATE_LIMITED` / `JOB_SEARCH_RATE_LIMITED` | API rate limit |
| 500 | `LLM_CONFIGURATION_ERROR` | Missing API key |
| 502 | `AGENT_ERROR` | Unexpected agent failure |
| 503 | `LLM_UNAVAILABLE` / `AUTH0_UNAVAILABLE` | Network/service down |

---

## 7. gRPC Service Definition

```protobuf
service JobAgentService {
  // Public RPCs (no auth token required)
  rpc HealthCheck(HealthRequest)       returns (HealthResponse);
  rpc GetToken(GetTokenRequest)        returns (GetTokenResponse);
  rpc ChatPublic(ChatRequest)          returns (ChatResponse);
  rpc CreateSession(CreateSessionRequest) returns (CreateSessionResponse);

  // Protected RPCs (authorization: Bearer <token> in metadata)
  rpc Chat(ChatRequest)                returns (ChatResponse);
  rpc SearchJobs(JobSearchRequest)     returns (JobSearchResponse);
  rpc AnalyzeResume(ResumeAnalysisRequest) returns (ResumeAnalysisResponse);
  rpc GenerateCoverLetter(CoverLetterRequest) returns (CoverLetterResponse);
  rpc ClearSession(ClearSessionRequest) returns (ClearSessionResponse);
  rpc ListSessions(ListSessionsRequest) returns (ListSessionsResponse);
}
```

**Auth validation in gRPC:**

```python
def _require_auth(context) -> dict:
    metadata = dict(context.invocation_metadata())
    auth_header = metadata.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        context.abort(StatusCode.UNAUTHENTICATED, "...")
    token = auth_header[len("Bearer "):]
    try:
        return verify_token(token)
    except AppError as exc:
        code, detail = _map_app_error(exc)
        context.abort(code, detail)
    return {}  # unreachable
```

**gRPC status mapping:**

| AppError subclass | gRPC StatusCode |
|-------------------|----------------|
| `Auth0CredentialsError` | `UNAUTHENTICATED` |
| `Auth0NetworkError` | `UNAVAILABLE` |
| `Auth0ConfigError` | `INTERNAL` |
| `GeminiRateLimitError` | `RESOURCE_EXHAUSTED` |
| `GeminiQuotaExceededError` | `UNAVAILABLE` |
| `GeminiNetworkError` | `UNAVAILABLE` |
| `GeminiInvalidRequestError` | `INVALID_ARGUMENT` |
| `SerpApiRateLimitError` | `RESOURCE_EXHAUSTED` |
| `SerpApiNetworkError` | `UNAVAILABLE` |
| `SerpApiConfigError` | `INTERNAL` |
| Generic `AppError` | `INTERNAL` |

---

## 8. LangChain Agent Design

### Agent Construction

```python
# Prompt
prompt = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    MessagesPlaceholder("chat_history"),   # RunnableWithMessageHistory
    ("human", "{input}"),
    MessagesPlaceholder("agent_scratchpad"), # AgentExecutor tool steps
])

# Tool-calling agent
agent = create_tool_calling_agent(llm, tools, prompt)

# Executor
executor = AgentExecutor(
    agent=agent,
    tools=[search_jobs, analyze_resume, generate_cover_letter],
    verbose=True,
    max_iterations=6,
    handle_parsing_errors=True,
    return_intermediate_steps=False,
)

# Session memory wrapper
agent_with_history = RunnableWithMessageHistory(
    executor,
    get_session_history,         # session factory
    input_messages_key="input",
    history_messages_key="chat_history",
)
```

### Invocation Patterns

```python
# Synchronous (REST, gRPC)
result = agent_with_history.invoke(
    {"input": user_message},
    config={"configurable": {"session_id": session_id}, "callbacks": callbacks},
)

# Asynchronous (Sprint 2 LO3 — FastAPI /api/chat/async)
result = await agent_with_history.ainvoke({"input": user_message}, config=config)

# Streaming (Sprint 7 — SSE /api/chat/stream)
async for event in agent_with_history.astream_events(
    {"input": user_message}, config=config, version="v1"
):
    if event["event"] == "on_chat_model_stream":
        chunk = event["data"].get("chunk")
        if chunk and chunk.content and not getattr(chunk, "tool_call_chunks", None):
            yield chunk.content   # final-answer tokens only
```

### Langfuse Integration

```python
langfuse_handler = get_langfuse_handler(session_id=session_id, user_id=user_id)
callbacks = [langfuse_handler] if langfuse_handler else []
config = {"configurable": {"session_id": session_id}, "callbacks": callbacks}
# ... invoke ...
# finally:
if langfuse_handler:
    try:
        langfuse_handler.flush()    # essential for serverless (process killed after request)
    except Exception:
        pass    # never let flush failure mask a real error
```

---

## 9. LCEL Chains

### Resume Analysis Chain

```python
@lru_cache(maxsize=1)
def _get_analysis_chain():
    prompt_template = ChatPromptTemplate.from_messages([
        ("human", "{analysis_prompt}")
    ])
    return prompt_template | get_llm() | StrOutputParser()

# Usage
chain = _get_analysis_chain()
result = chain.invoke(
    {"analysis_prompt": built_prompt},
    config={"callbacks": callbacks} if callbacks else {}
)
```

### Cover Letter Chain

Same pattern — `ChatPromptTemplate | get_llm() | StrOutputParser()` with a different prompt template.

### Intent Router Chain

```python
# Stage 1: classify
classify_chain = ChatPromptTemplate.from_messages([
    ("system", _CLASSIFY_SYSTEM),
    ("human", "User query: {query}\n\nRespond with one label only.")
]) | get_llm() | StrOutputParser()

# Stage 2: route
branch = RunnableBranch(
    (lambda x: x["intent"] == "job_search",     job_search_chain),
    (lambda x: x["intent"] == "resume_analysis", resume_chain),
    (lambda x: x["intent"] == "cover_letter",   cover_chain),
    general_chain,    # default
)

# Stage 3: combined pipeline (not used in route_query — stages called separately)
pipeline = RunnablePassthrough.assign(intent=classify_chain) | branch
```

---

## 10. Authentication & Authorization

### Auth0 JWT Flow

```
Client                    FastAPI                     Auth0
  │                          │                           │
  │──POST /api/auth/token────▶│                           │
  │                          │──POST /oauth/token────────▶│
  │                          │◀───{access_token}──────────│
  │◀─{access_token}──────────│                           │
  │                          │                           │
  │──POST /api/chat + Bearer─▶│                           │
  │                          │──GET /.well-known/jwks────▶│
  │                          │◀───{JWKS keys}─────────────│
  │                          │  verify RS256 signature    │
  │                          │  check audience/issuer/exp │
  │◀─{response}──────────────│                           │
```

### JWT Verification Code

```python
from jose import jwt, JWTError

def verify_token(token: str) -> dict:
    header  = jwt.get_unverified_header(token)
    kid     = header.get("kid")
    jwks    = _get_jwks()          # lru_cache
    key     = _find_key(jwks, kid)
    payload = jwt.decode(
        token,
        key,
        algorithms=["RS256"],
        audience=AUTH0_AUDIENCE,
        issuer=f"https://{AUTH0_DOMAIN}/",
    )
    return payload
```

### Protected Endpoint Pattern

```python
@app.post("/api/chat")
def chat(
    body: ChatRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),  # raises 401 on invalid JWT
):
    user_id = current_user.get("sub", "unknown")
    ...
```

---

## 11. Observability

### Langfuse Trace Structure

```
Trace: job-placement-agent  (session_id=..., user_id=...)
│
├── Span: AgentExecutor.invoke
│   ├── Span: ChatModel (planning)         ← LLM decides tool to call
│   ├── Span: search_jobs                  ← tool invocation
│   ├── Span: ChatModel (final answer)     ← LLM generates response
│   └── metadata: token_count, latency_ms
│
└── Flush: on every request (flush() in finally block)
```

### Configuration

```python
def get_langfuse_handler(session_id: str, user_id: str | None) -> CallbackHandler | None:
    sk = os.getenv("LANGFUSE_SECRET_KEY", "")
    pk = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    if not sk or not pk:
        return None          # tracing disabled — no exception raised

    handler = CallbackHandler(
        secret_key=sk,
        public_key=pk,
        host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
        session_id=session_id,
        user_id=user_id,
        trace_name="job-placement-agent",
        tags=["job-placement", "langchain", "gemini"],
    )
    handler.auth_check()     # validates keys at startup
    return handler
```

---

## 12. Data Models

### Request Models (Pydantic v2)

```python
class ChatRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    message:    str            = Field(..., min_length=1, max_length=4000)
    session_id: Optional[str]  = Field(default="default")

class ResumeAnalysisRequest(BaseModel):
    resume_text:     str           = Field(..., min_length=50, max_length=50_000)
    job_description: Optional[str] = Field(default="", max_length=10_000)
    session_id:      Optional[str] = Field(default="default")

class CoverLetterRequest(BaseModel):
    resume_text:     str           = Field(..., min_length=50, max_length=50_000)
    job_title:       str           = Field(..., min_length=1,  max_length=200)
    company_name:    str           = Field(..., min_length=1,  max_length=200)
    job_description: str           = Field(..., min_length=10, max_length=10_000)
    user_name:       Optional[str] = Field(default="Applicant")
    session_id:      Optional[str] = Field(default="default")
```

### Response Envelope

```python
class ApiResponse(BaseModel, Generic[T]):
    success: bool
    data:    Optional[T]
    error:   Optional[ErrorDetail]
    meta:    RequestMeta            # {request_id, api_version}

class ErrorDetail(BaseModel):
    code:    str                    # machine-readable
    message: str                    # human-readable
    details: Optional[List[FieldError]]

class RequestMeta(BaseModel):
    request_id:  str               # echoed from X-Request-ID header or generated UUID
    api_version: str = "1.0.0"
```

---

## 13. Error Handling

### Exception Hierarchy

```
AppError (base)
├── ConfigurationError          HTTP 500  CONFIGURATION_ERROR
├── Auth0Error                  HTTP 502  AUTH0_ERROR
│   ├── Auth0ConfigError        HTTP 500  AUTH0_CONFIGURATION_ERROR
│   ├── Auth0CredentialsError   HTTP 401  AUTH0_INVALID_CREDENTIALS
│   └── Auth0NetworkError       HTTP 503  AUTH0_UNAVAILABLE
├── GeminiError                 HTTP 502  LLM_ERROR
│   ├── GeminiConfigError       HTTP 500  LLM_CONFIGURATION_ERROR
│   ├── GeminiRateLimitError    HTTP 429  LLM_RATE_LIMITED
│   ├── GeminiQuotaExceededError HTTP 503 LLM_QUOTA_EXCEEDED
│   ├── GeminiNetworkError      HTTP 503  LLM_UNAVAILABLE
│   └── GeminiInvalidRequestError HTTP 400 LLM_INVALID_REQUEST
├── LangfuseError               HTTP 502  OBSERVABILITY_ERROR
├── SerpApiError                HTTP 502  JOB_SEARCH_ERROR
│   ├── SerpApiConfigError      HTTP 500  JOB_SEARCH_CONFIGURATION_ERROR
│   ├── SerpApiRateLimitError   HTTP 429  JOB_SEARCH_RATE_LIMITED
│   └── SerpApiNetworkError     HTTP 503  JOB_SEARCH_UNAVAILABLE
└── AgentError                  HTTP 502  AGENT_ERROR
```

### Global Exception Handler (FastAPI)

```python
@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.http_status,
        content=ApiResponse.fail(
            code=exc.error_code,
            message=str(exc),
            request_id=_req_id(request),
        ).model_dump(),
    )
```

---

## 14. Testing Strategy

### Coverage Summary

```
Total: 1016 statements · 11 missed · 99% coverage
376 tests · 0 failures
```

### Test Files

| File | Tests | Focus |
|------|-------|-------|
| `test_agent.py` | 52 | Session management, run_agent, async, stream, flush swallowing |
| `test_llm.py` | 22 | LLM factory, error translation, openai isinstance branches |
| `test_router.py` | 27 | Intent classification, RunnableBranch routing, pipeline cache |
| `test_tools_job_search.py` | 16 | SerpAPI integration, result formatting, error handling |
| `test_tools_resume_analyzer.py` | 19 | LCEL chain, prompt construction, GeminiError handling |
| `test_tools_cover_letter.py` | 12 | Cover letter chain, prompt, validation |
| `test_fastapi_app.py` | 79 | TestClient, all 13 endpoints, AppError handler, SSE |
| `test_main.py` | 95 | gRPC servicer RPCs, _require_auth, _map_app_error, serve() |
| `test_auth0.py` | 38 | JWT validation, JWKS fetch, error types |
| `test_schemas.py` | 32 | Pydantic models, validators, ApiResponse |
| `test_entry_point.py` | 9 | main.py _start_grpc_thread, main(), env vars |

### Key Testing Patterns

**1. sys.modules stubbing (conftest.py)**

```python
# Makes langchain, grpcio, sonora importable without installation
sys.modules["langchain_core.runnables"] = _stub_module(
    "langchain_core.runnables",
    RunnableBranch=MagicMock,
    RunnablePassthrough=MagicMock(),
)
```

**2. LCEL chain mocking**

```python
# Mock the cached chain factory, not the LLM directly
mocker.patch("agent.tools.resume_analyzer._get_analysis_chain",
             return_value=mock_chain)
```

**3. Async generator mocking (stream_agent)**

```python
async def _mock_stream(user_message=None, session_id="default", user_id=None):
    yield "Hello"
    yield " world"
mocker.patch("fastapi_app.stream_agent", new=_mock_stream)
```

**4. FastAPI TestClient with dependency override**

```python
from fastapi_app import app
from auth.auth0 import get_current_user
app.dependency_overrides[get_current_user] = lambda: FAKE_USER
with TestClient(app) as c:
    resp = c.post("/api/chat", json={"message": "Hi"})
```

---

## 15. Deployment

### Vercel (Recommended — Serverless)

**Frontend** (`src/frontend/vercel.json`)

```json
{
  "rewrites": [{ "source": "/(.*)", "destination": "/index.html" }]
}
```

**Backend** (`src/backend/vercel.json`)

```json
{
  "builds": [{ "src": "index.py", "use": "@vercel/python" }],
  "routes": [{ "src": "/(.*)", "dest": "index.py" }]
}
```

**Entry point** (`src/backend/index.py`)

```python
from fastapi_app import app
from mangum import Mangum
handler = Mangum(app, lifespan="off")
```

**Deploy command** (via `deploy-vercel.ps1`)

```powershell
cd src/frontend; vercel deploy --prod
cd src/backend;  vercel deploy --prod
```

### Local Development

```bash
# FastAPI
cd src/backend
uvicorn fastapi_app:app --reload --port 8000

# gRPC + gRPC-Web (both servers)
cd src/backend
python main.py

# Frontend
cd src/frontend
# Open index.html in browser or use a dev server
```

---

## 16. Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GEMINI_API_KEY` | Yes | — | Google AI Studio API key |
| `GEMINI_MODEL_NAME` | No | `gemini-2.0-flash` | Model identifier |
| `GEMINI_BASE_URL` | No | Google OpenAI-compat URL | API base URL |
| `SERPAPI_API_KEY` | Yes | — | SerpAPI key for Google Jobs |
| `AUTH0_DOMAIN` | Yes* | — | Auth0 tenant (e.g. `dev-x.auth0.com`) |
| `AUTH0_AUDIENCE` | Yes* | — | API audience URL |
| `AUTH0_CLIENT_ID` | Yes* | — | Auth0 application client ID |
| `AUTH0_CLIENT_SECRET` | Yes* | — | Auth0 application client secret |
| `LANGFUSE_SECRET_KEY` | No | `""` | Disables tracing if empty |
| `LANGFUSE_PUBLIC_KEY` | No | `""` | Disables tracing if empty |
| `LANGFUSE_HOST` | No | `https://cloud.langfuse.com` | Langfuse server |
| `GRPC_PORT` | No | `50051` | gRPC server port |
| `GRPC_WEB_PORT` | No | `8080` | gRPC-Web server port |
| `GRPC_WORKERS` | No | `10` | gRPC thread pool size |

*Required only for protected endpoints; public endpoints work without Auth0.

---

## 17. Sprint Concept Mapping

| Sprint | Learning Objective | Implementation |
|--------|-------------------|----------------|
| Sprint 2 | LLM Integration | `agent/llm.py` — `get_llm()` via ChatOpenAI + Gemini compat API |
| Sprint 2 LO3 | Async LLM Calls | `run_agent_async()` using `.ainvoke()` |
| Sprint 3 | LangChain Tools | `@tool` decorator on `search_jobs`, `analyze_resume`, `generate_cover_letter` |
| Sprint 4 | Agent + Memory | `create_tool_calling_agent`, `AgentExecutor`, `RunnableWithMessageHistory` |
| Sprint 5/6 | LCEL Pipe Syntax | `prompt | llm | StrOutputParser()` in all tool chains |
| Sprint 5/6 | Router Chains | `agent/router.py` — `RunnableBranch` intent classification |
| Sprint 7 | SSE Streaming | `stream_agent()` + `POST /api/chat/stream` `StreamingResponse` |
| Sprint 8 | Observability | Langfuse `CallbackHandler` on every agent invocation |
| Sprint 8 | Authentication | Auth0 RS256 JWT — `get_current_user` FastAPI dependency |
| Sprint 9 | gRPC Transport | `grpc_server.py` servicer + protobuf + `grpc_web_server.py` |

---

## 18. Technical Concepts & Glossary

This glossary defines every significant technology, pattern, and term used throughout this document. The concepts span five layers of the system — each layer depending on the one below it:

- **LLM & AI layer** — the intelligence core: the large language model itself, the agent loop that drives it, the tool-calling protocol that connects it to external systems, and the LCEL pipe syntax used to assemble reusable chains. Concepts here include `LLM`, `Tool Calling`, `AgentExecutor`, `create_tool_calling_agent`, `LCEL`, `RunnableBranch`, `RunnableWithMessageHistory`, `ChatOpenAI`, `ChatPromptTemplate`, `MessagesPlaceholder`, `StrOutputParser`, `CallbackHandler`, and the `@tool` and `@lru_cache` decorators.

- **External service integrations** — third-party APIs the agent calls at runtime: `SerpAPI` for live job search results, `Gemini` as the underlying LLM, `Auth0` as the identity provider, and `Langfuse` for observability and tracing.

- **Transport & serialisation layer** — how clients communicate with the backend: `FastAPI` over HTTP/JSON (REST), `gRPC` over binary Protocol Buffers, and `gRPC-Web` for browser clients. `SSE` (Server-Sent Events) handles streaming responses within the REST transport. `ASGI` is the common server interface all HTTP transports share.

- **Security layer** — the mechanisms that protect the API: `JWT` for stateless bearer authentication, `JWKS` for public-key distribution, `RS256` as the signing algorithm, and `python-jose` as the verification library.

- **Infrastructure & runtime layer** — how the application is packaged and run: `Uvicorn` as the local ASGI server, `Mangum` as the Vercel/Lambda adapter, `Vercel` as the serverless host, and `Pydantic` for request/response schema validation.

All entries are listed alphabetically below. Cross-references to source files and sections are included where relevant.

---

### `@lru_cache` (Least Recently Used Cache)

A Python standard-library decorator (`functools.lru_cache`) that memoises the return value of a function after its first call. Subsequent calls with the same arguments return the cached value without re-executing the function body. Used here with `maxsize=1` to create lazily-initialised singletons (LLM instance, LCEL chains, JWKS keys) — the object is built once on first request and reused for the lifetime of the process.

---

### `@tool` Decorator (LangChain)

A LangChain decorator that converts a plain Python function into a `Tool` object the agent can invoke. It extracts the function name, docstring, and type-annotated parameters to build the tool schema that is passed to the LLM. The LLM uses this schema to decide when and how to call the tool.

---

### AgentExecutor (LangChain)

The runtime loop that drives a LangChain agent. It repeatedly calls the agent (LLM) to get either a tool invocation or a final answer. On a tool invocation it calls the tool, appends the result to the scratchpad, and asks the agent again. The loop terminates when the agent produces a final answer or `max_iterations` is reached. Key configuration used here: `max_iterations=6`, `handle_parsing_errors=True`.

---

### ASGI (Asynchronous Server Gateway Interface)

A Python standard that defines how an async web server communicates with a Python web application. FastAPI is an ASGI application; Uvicorn is the ASGI server that runs it locally. Mangum is an ASGI adapter that translates AWS Lambda / Vercel serverless invocations into ASGI calls so FastAPI can run in a serverless environment without modification.

---

### Auth0

A cloud-based Identity-as-a-Service (IDaaS) platform. In this project it acts as the authorisation server: it issues signed JWT access tokens when a user provides valid credentials (`POST /oauth/token`), and it hosts the public JWKS endpoint that the backend uses to verify those tokens offline without calling Auth0 on every request.

---

### Bearer Token

An HTTP authentication scheme (`Authorization: Bearer <token>`) where possession of the token is sufficient proof of identity. The server does not maintain a session; instead it validates the token's cryptographic signature on every request. Used here with Auth0-issued JWTs.

---

### CallbackHandler (LangChain / Langfuse)

A LangChain interface for intercepting lifecycle events during agent or chain execution (e.g., `on_llm_start`, `on_tool_end`, `on_chain_error`). Langfuse ships a `CallbackHandler` that translates these events into structured traces and sends them to the Langfuse backend. Passing the handler in the `callbacks` list of a `config` dict wires it into every step of the execution.

---

### ChatMessageHistory (LangChain)

An in-memory store for a sequence of `HumanMessage` / `AIMessage` objects representing one conversation session. `RunnableWithMessageHistory` uses a factory function (`get_session_history`) to retrieve or create the appropriate history object for each `session_id`, making multi-turn context available to the agent.

---

### ChatOpenAI (LangChain)

LangChain's wrapper around the OpenAI Chat Completions API (`/chat/completions`). Because Google Gemini exposes an OpenAI-compatible endpoint, `ChatOpenAI` can target Gemini by pointing `openai_api_base` at the Gemini URL and supplying a Gemini API key — no Gemini-specific SDK required.

---

### ChatPromptTemplate (LangChain)

A template that constructs a list of `BaseMessage` objects (system, human, AI, placeholder) from a mix of static strings and runtime variables. In LCEL chains it is the first stage: `ChatPromptTemplate | LLM | OutputParser`. The `from_messages` class method accepts a list of `(role, template_string)` tuples.

---

### `create_tool_calling_agent` (LangChain)

A factory function that wires together a prompt, an LLM that supports native tool/function calling, and a list of tools into a single `Runnable`. The resulting runnable takes `{input, chat_history, agent_scratchpad}` and returns either a tool call or a final answer. It is not an executor — `AgentExecutor` wraps it to run the loop.

---

### Dependency Injection (FastAPI `Depends`)

FastAPI's mechanism for declaring shared logic (authentication, database connections, config) as reusable callables. When a route handler declares a parameter typed as `Depends(some_callable)`, FastAPI calls `some_callable` before the handler and passes its return value in. Used here so `get_current_user` is called automatically for every protected endpoint, raising `HTTP 401` if the token is invalid.

---

### FastAPI

A modern Python web framework built on Starlette (ASGI) and Pydantic. It generates OpenAPI documentation automatically from type annotations, supports both sync and async route handlers, and uses a dependency injection system for cross-cutting concerns. It is the primary HTTP transport in this project.

---

### Gemini (Google)

Google's family of large language models. This project uses `gemini-2.0-flash` via Google's OpenAI-compatible endpoint, allowing the standard `openai` Python SDK (and therefore `ChatOpenAI`) to call Gemini without a separate Google AI SDK.

---

### gRPC (Google Remote Procedure Call)

A high-performance, language-neutral RPC framework from Google. It uses Protocol Buffers (`.proto` files) to define services and message schemas, generates client/server stub code in multiple languages, and transmits binary-encoded messages over HTTP/2. Advantages over REST: smaller payload size, strict schema, built-in streaming, and strongly-typed generated clients.

---

### gRPC-Web

A variant of gRPC that runs over HTTP/1.1 instead of HTTP/2, making it usable from browsers (which cannot initiate raw HTTP/2 frames). The `sonora` library acts as a server-side gRPC-Web proxy: it accepts HTTP/1.1 gRPC-Web requests, translates them to standard gRPC calls, and forwards responses back. Browser clients use the generated JavaScript stubs or the `grpc-web` npm package.

---

### JWT (JSON Web Token)

A compact, URL-safe token format defined by RFC 7519. A JWT consists of three Base64URL-encoded parts separated by dots: a **header** (algorithm, key ID), a **payload** (claims such as `sub`, `aud`, `exp`), and a **signature**. The signature lets the recipient verify the token without contacting the issuer, as long as it has the public key. This project uses RS256-signed JWTs issued by Auth0.

---

### JWKS (JSON Web Key Set)

A JSON document (RFC 7517) that contains a set of public cryptographic keys. Auth0 publishes its JWKS at `https://<domain>/.well-known/jwks.json`. The backend downloads this document (cached via `lru_cache`), finds the key matching the JWT's `kid` header, and uses it to verify the RS256 signature without ever seeing the private key.

---

### Langfuse

An open-source LLM observability platform. It captures traces of LangChain executions — every LLM call, tool invocation, latency, token count, and error — and displays them in a web dashboard. Integration is entirely through LangChain's `CallbackHandler` interface; the application code does not call Langfuse APIs directly.

---

### LCEL (LangChain Expression Language)

A declarative composition syntax built into LangChain. Runnables (prompts, LLMs, parsers, branches) are composed with the `|` pipe operator to form chains: `prompt | llm | parser`. Every LCEL chain implements the `Runnable` interface (`invoke`, `ainvoke`, `stream`, `astream`) so chains can be nested, cached, and instrumented uniformly.

---

### LLM (Large Language Model)

A neural network trained on large text corpora to predict and generate natural language. In this project, the LLM (Gemini 2.0 Flash) serves three roles: (1) agent brain — decides which tool to call and synthesises the final answer; (2) LCEL chain worker — executes resume analysis and cover letter generation prompts; (3) intent classifier — categorises the user's query in the router chain.

---

### Mangum

A Python adapter library that wraps any ASGI application (FastAPI, Starlette) in an AWS Lambda / Vercel handler interface. Vercel's Python runtime invokes `handler(event, context)` — Mangum translates that invocation into an ASGI lifecycle, runs the FastAPI app, and serialises the response back into the Lambda response format.

---

### `MessagesPlaceholder` (LangChain)

A special slot inside a `ChatPromptTemplate` that is filled at runtime with a list of messages. Used in two places in the agent prompt: `MessagesPlaceholder("chat_history")` is filled by `RunnableWithMessageHistory` with the session's prior messages; `MessagesPlaceholder("agent_scratchpad")` is filled by `AgentExecutor` with intermediate tool-call steps.

---

### Pydantic (v2)

A Python data validation library that uses class definitions with type annotations to declare schemas. At runtime Pydantic parses and validates incoming data, raising detailed errors for constraint violations. FastAPI uses Pydantic models for request bodies and response serialisation. The `Field(...)` API adds constraints (`min_length`, `max_length`) and default values.

---

### Protocol Buffers (Protobuf)

Google's language-neutral binary serialisation format. A `.proto` file defines message types and service methods; the `protoc` compiler generates language-specific classes (Python, JavaScript, Go, etc.) that serialise/deserialise those messages. Binary encoding is 3–10× smaller and faster to parse than equivalent JSON.

---

### RS256

An asymmetric JWT signing algorithm: **R**SA **S**ignature with **SHA-256**. The issuer (Auth0) signs the JWT with its **private** RSA key; the recipient (this backend) verifies the signature with the corresponding **public** key fetched from JWKS. Because the private key never leaves Auth0, the signature cannot be forged even if the JWKS endpoint is public.

---

### `RunnableBranch` (LangChain LCEL)

An LCEL construct that routes execution to one of several sub-chains based on a condition evaluated at runtime. It takes a list of `(predicate, runnable)` pairs and a default runnable. The first predicate that returns `True` determines which runnable processes the input. Used in the intent router to dispatch to the appropriate tool chain.

---

### `RunnableWithMessageHistory` (LangChain)

A wrapper that adds persistent session memory to any `Runnable` (typically an `AgentExecutor`). Before each invocation it loads the session's history from the store, injects it into the input under `history_messages_key`, runs the inner runnable, and appends the new human/AI message pair back to the store. Session identity is passed via `config["configurable"]["session_id"]`.

---

### SerpAPI

A commercial API service that programmatically scrapes Google Search result pages and returns structured JSON. The `google-search-results` Python package wraps the HTTP calls. This project uses the Google Jobs engine (`engine=google_jobs`) to retrieve real-time job listings without needing a direct Google Jobs API key.

---

### SSE (Server-Sent Events)

An HTTP/1.1 protocol where the server keeps a connection open and pushes newline-delimited `data: ...\n\n` frames to the client. Unlike WebSockets, SSE is unidirectional (server → client only) and uses plain HTTP — no upgrade handshake. FastAPI's `StreamingResponse` with `media_type="text/event-stream"` implements SSE. Used for streaming LLM token output to the browser.

---

### `StrOutputParser` (LangChain)

An LCEL output parser that extracts the plain string content from an LLM's `AIMessage` response object. It is the final stage of most LCEL chains: `ChatPromptTemplate | ChatOpenAI | StrOutputParser()` returns a `str` rather than an `AIMessage`.

---

### Tool Calling (Function Calling)

A capability of modern LLMs where the model can output a structured JSON object describing a function it wants to call (name + arguments) instead of producing free text. The framework (LangChain's `AgentExecutor`) intercepts this output, executes the real function, appends the result to the conversation, and asks the LLM to continue. This allows the LLM to interact with external systems (APIs, databases) in a controlled way.

---

### Uvicorn

A production-grade ASGI server written in Python, built on `uvloop` (fast event loop) and `httptools` (fast HTTP parser). It is the recommended server for running FastAPI locally (`uvicorn fastapi_app:app --reload`). In production (Vercel) it is replaced by Mangum's Lambda shim.

---

### Vercel

A serverless hosting platform optimised for frontend frameworks and Python/Node.js serverless functions. Each `vercel.json` build entry compiles a source file into a Lambda-compatible function. The `@vercel/python` builder packages the Python environment. Cold starts are mitigated by Vercel's edge caching; the `lru_cache` singletons warm up on the first request to each function instance.

---

### `python-jose`

A Python library for creating and verifying JSON Web Tokens and JSON Web Keys. Used in `auth/auth0.py` to decode and RS256-verify Auth0 JWTs. The `[cryptography]` extra installs the `cryptography` backend required for RSA key operations (`jwt.decode` with `algorithms=["RS256"]`).
