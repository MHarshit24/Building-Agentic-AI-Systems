# Job Placement Agent — AI-Powered Career Assistant

> Sprint 11 Capstone · NIIT — Build and Deploy Intelligent Conversational Agents

An intelligent, conversational job placement agent that helps users discover relevant job
opportunities, analyze their resumes, identify skill gaps, and generate personalized cover
letters — all through a natural chat interface.

[![Tests](https://img.shields.io/badge/tests-376%20passed-brightgreen)](#testing)
[![Coverage](https://img.shields.io/badge/coverage-99%25-brightgreen)](#testing)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](#tech-stack)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688)](#tech-stack)
[![LangChain](https://img.shields.io/badge/LangChain-0.2.x-orange)](#tech-stack)

---

## Table of Contents

- [Architecture](#architecture)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Quick Start](#quick-start)
- [API Endpoints](#api-endpoints)
- [Sprint Coverage](#sprint-coverage)
- [Testing](#testing)
- [Deployment](#deployment)
- [Authentication](#authentication)
- [Observability](#observability)
- [Environment Variables](#environment-variables)
- [Documentation](#documentation)

---

## Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│                        USER INTERFACES                             │
│     index.html (gRPC-Web)    ·    REST clients / Postman           │
└──────────────┬───────────────────────────────┬─────────────────────┘
               │ HTTP REST / SSE               │ gRPC / gRPC-Web
               ▼                               ▼
┌──────────────────────────┐      ┌────────────────────────────────┐
│   FastAPI  (fastapi_app) │      │  gRPC Server  (grpc_server)    │
│   Vercel Serverless      │      │  gRPC-Web     (grpc_web_server)│
│   Mangum ASGI adapter    │      │  main.py  (threaded launcher)  │
└─────────────┬────────────┘      └──────────────┬─────────────────┘
              │                                  │
              └──────────────┬───────────────────┘
                             │ shared business logic
                             ▼
┌────────────────────────────────────────────────────────────────────┐
│                  LANGCHAIN AGENT  (agent/job_agent.py)             │
│                                                                    │
│  create_tool_calling_agent  +  AgentExecutor (max 6 iterations)   │
│  RunnableWithMessageHistory  →  per-session ChatMessageHistory     │
│  run_agent() · run_agent_async() · stream_agent()                 │
│                                                                    │
│  LCEL Intent Router  (agent/router.py)                             │
│  ChatPromptTemplate | LLM | StrOutputParser  →  RunnableBranch    │
└──────────────────────────┬─────────────────────────────────────────┘
                           │ tool calls
         ┌─────────────────┼─────────────────┐
         ▼                 ▼                 ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────────┐
│ search_jobs  │   │analyze_resume│   │generate_cover_   │
│ SerpAPI      │   │LCEL chain    │   │letter LCEL chain │
│ Google Jobs  │   │StrOutputParser│   │StrOutputParser   │
└──────┬───────┘   └──────┬───────┘   └────────┬──────────┘
       │                  │                    │
       ▼                  ▼                    ▼
  SerpAPI API        Gemini LLM           Gemini LLM
  (real-time)   (OpenAI-compat API)  (OpenAI-compat API)

            ┌──────────────────────────────────────┐
            │  Auth0  RS256 JWT  ·  Langfuse traces │
            └──────────────────────────────────────┘
```

---

## Features

| Feature | Description |
|---------|-------------|
| **Real-Time Job Search** | SerpAPI Google Jobs — live listings by role + city |
| **Resume Analysis** | LLM skill extraction, experience scoring, quality rating |
| **Skill Gap Detection** | Resume-vs-JD comparison with match percentage |
| **Cover Letter Generator** | Tailored, role-specific letters in seconds |
| **Session Memory** | `RunnableWithMessageHistory` — context preserved across turns |
| **SSE Token Streaming** | Token-by-token via FastAPI `StreamingResponse` |
| **LCEL Intent Router** | `RunnableBranch` classifies intent → routes to specialist chain |
| **Async Agent** | `.ainvoke()` keeps the FastAPI event loop free |
| **Dual Transport** | FastAPI REST + gRPC + gRPC-Web on a single shared servicer |
| **Auth0 JWT Auth** | RS256 signature validation via JWKS on all protected endpoints |
| **Langfuse Observability** | Full trace: LLM calls, tools, latency, errors, session grouping |
| **99% Test Coverage** | 376 tests — unit, integration, FastAPI TestClient, gRPC servicer |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| LLM | Google Gemini via OpenAI-compatible API |
| Agent Framework | LangChain 0.2.x (`create_tool_calling_agent` + `AgentExecutor`) |
| LCEL / Memory | `RunnableWithMessageHistory`, `RunnableBranch`, `StrOutputParser` |
| Job Search | SerpAPI Google Jobs |
| HTTP Backend | FastAPI + Uvicorn |
| Serverless | Mangum (ASGI → Vercel/Lambda) |
| RPC Transport | grpcio + protobuf |
| gRPC-Web | sonora WSGI adapter |
| Authentication | Auth0 RS256 JWT via `python-jose[cryptography]` |
| Observability | Langfuse `CallbackHandler` |
| Data Validation | Pydantic v2 |
| Testing | pytest + pytest-cov + pytest-mock |
| Deployment | Vercel (frontend + backend) |

---

## Project Structure

```
course2-capstoneproject/
│
├── README.md
├── pytest.ini
├── deploy-vercel.ps1
│
├── docs/
│   ├── technical-document.md       ← System design, API spec, module reference
│   ├── user-manual.md              ← End-user guide with walkthroughs
│   ├── generate_ppt.py             ← Generates demo presentation (python-pptx)
│   └── Job_Placement_Agent_Demo.pptx  ← Generated demo PPT (12 slides)
│
├── src/
│   ├── backend/
│   │   ├── fastapi_app.py          ← FastAPI app — 13 endpoints
│   │   ├── grpc_server.py          ← gRPC servicer (all RPCs)
│   │   ├── grpc_web_server.py      ← gRPC-Web HTTP server (sonora)
│   │   ├── main.py                 ← Starts gRPC + gRPC-Web in threads
│   │   ├── index.py                ← Vercel entry point (Mangum)
│   │   ├── exceptions.py           ← Domain exception hierarchy
│   │   ├── requirements.txt
│   │   │
│   │   ├── agent/
│   │   │   ├── job_agent.py        ← LangChain agent + session memory + async
│   │   │   ├── llm.py              ← Gemini LLM factory (cached) + error mapping
│   │   │   ├── prompts.py          ← System prompt
│   │   │   ├── router.py           ← LCEL intent router (RunnableBranch)
│   │   │   └── tools/
│   │   │       ├── job_search.py   ← SerpAPI Google Jobs tool
│   │   │       ├── resume_analyzer.py  ← LCEL chain, skill extraction
│   │   │       └── cover_letter.py     ← LCEL chain, personalization
│   │   │
│   │   ├── auth/
│   │   │   └── auth0.py            ← RS256 JWT validation via JWKS
│   │   │
│   │   ├── models/
│   │   │   ├── schemas.py          ← Pydantic v2 request/response models
│   │   │   └── responses.py        ← ApiResponse envelope
│   │   │
│   │   ├── observability/
│   │   │   └── langfuse_config.py  ← Langfuse handler factory + flush
│   │   │
│   │   └── proto/                  ← Generated protobuf stubs
│   │
│   └── frontend/
│       ├── index.html              ← Chat UI
│       ├── build.js                ← Vite bundle script
│       └── vercel.json
│
└── tests/
    ├── conftest.py                 ← sys.modules stubs, fixtures, cache resets
    ├── test_agent.py               ← 52 tests
    ├── test_llm.py                 ← 22 tests
    ├── test_router.py              ← 27 tests
    ├── test_tools_job_search.py    ← 16 tests
    ├── test_tools_resume_analyzer.py  ← 19 tests
    ├── test_tools_cover_letter.py  ← 12 tests
    ├── test_fastapi_app.py         ← 79 tests
    ├── test_main.py                ← 95 tests (gRPC servicer)
    ├── test_auth0.py               ← 38 tests
    ├── test_schemas.py             ← 32 tests
    └── test_entry_point.py         ← 9 tests (main.py)
```

---

## Quick Start

### Prerequisites

- Python 3.11+
- [Gemini API key](https://aistudio.google.com/app/apikey)
- [SerpAPI key](https://serpapi.com/) (free tier available)
- [Auth0 account](https://auth0.com/) (free tier — for protected endpoints)
- [Langfuse account](https://cloud.langfuse.com/) (optional — for observability)

### 1. Clone and configure

```bash
git clone <repo-url>
cd course2-capstoneproject

# Copy and fill in your API keys
cp .env.example src/backend/.env
```

### 2. Install dependencies

```bash
cd src/backend
pip install -r requirements.txt
```

### 3. Start the API server

```bash
# FastAPI (REST + SSE)
uvicorn fastapi_app:app --reload --host 0.0.0.0 --port 8000

# Or — gRPC + gRPC-Web (both servers)
python main.py
```

### 4. Open the interactive docs

```
http://localhost:8000/docs
```

### 5. Generate the demo presentation

```bash
python docs/generate_ppt.py
# Output: docs/Job_Placement_Agent_Demo.pptx  (12 slides)
```

---

## API Endpoints

### Public (no auth required)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/health` | Health check |
| `POST` | `/api/auth/token` | Get Auth0 access token |
| `POST` | `/api/chat/public` | Chat with the agent (demo) |
| `POST` | `/api/session` | Create a new session |
| `POST` | `/api/chat/stream` | SSE token streaming |
| `POST` | `/api/chat/route` | LCEL intent router |

### Protected (Auth0 Bearer JWT required)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/chat` | Chat (synchronous) |
| `POST` | `/api/chat/async` | Chat via `.ainvoke()` |
| `POST` | `/api/jobs/search` | Direct SerpAPI job search |
| `POST` | `/api/resume/analyze` | Resume skill analysis |
| `POST` | `/api/cover-letter/gen` | Cover letter generation |
| `DELETE` | `/api/chat/{session_id}` | Clear session memory |
| `GET` | `/api/sessions` | List active sessions |

**All responses follow the `ApiResponse` envelope:**

```json
{
  "success": true,
  "data":    { "...": "..." },
  "error":   null,
  "meta":    { "request_id": "uuid", "api_version": "1.0.0" }
}
```

---

## Sprint Coverage

| Sprint | Concept | Implementation |
|--------|---------|---------------|
| 2 | LLM Integration | `ChatOpenAI` via Gemini OpenAI-compat API · `@lru_cache` |
| 2 LO3 | Async LLM Calls | `run_agent_async()` using `.ainvoke()` |
| 3 | LangChain Tools | `@tool` on `search_jobs`, `analyze_resume`, `generate_cover_letter` |
| 4 | Agent + Memory | `create_tool_calling_agent` · `AgentExecutor` · `RunnableWithMessageHistory` |
| 5/6 | LCEL Pipe Syntax | `prompt \| llm \| StrOutputParser()` in all tool chains |
| 5/6 | Router Chains | `agent/router.py` — `RunnableBranch` intent dispatch |
| 7 | SSE Streaming | `stream_agent()` · `POST /api/chat/stream` · `StreamingResponse` |
| 8 | Observability | Langfuse `CallbackHandler` — traces every LLM call |
| 8 | Authentication | Auth0 RS256 JWT · JWKS validation · `get_current_user` dependency |
| 9 | gRPC Transport | `grpc_server.py` servicer · protobuf · `grpc_web_server.py` |

---

## Testing

```bash
# Run all tests with coverage report
cd course2-capstoneproject
python -m pytest tests/ --tb=short -q
```

### Results

```
376 passed · 0 failed · 2 warnings
Total coverage: 99%  (1016 statements · 11 missed)
```

### Coverage by module

| Module | Coverage |
|--------|---------|
| `agent/job_agent.py` | 100% |
| `agent/llm.py` | 100% |
| `agent/router.py` | 100% |
| `agent/tools/*.py` | 100% |
| `auth/auth0.py` | 100% |
| `fastapi_app.py` | 100% |
| `grpc_server.py` | 100% |
| `main.py` | 100% |
| `observability/langfuse_config.py` | 100% |
| `exceptions.py` | 100% |
| `models/responses.py` | 100% |
| `models/schemas.py` | 96% |

### Key testing patterns

- **`conftest.py`** — `sys.modules` stubs for langchain, grpcio, sonora (no real installs needed)
- **LCEL chain mocking** — patches `_get_analysis_chain` factory, not the LLM directly
- **Async generator testing** — real `async def` generators, not `AsyncMock`
- **FastAPI `TestClient`** — with `app.dependency_overrides[get_current_user]`
- **gRPC `MockContext`** — `abort()` raises `GrpcAbortError` for clean assertion

---

## Deployment

### Vercel (Recommended)

```bash
# Frontend
cd src/frontend
vercel deploy --prod

# Backend
cd src/backend
vercel deploy --prod
```

Or use the provided script:

```powershell
.\deploy-vercel.ps1
```

**Backend entry point** (`src/backend/index.py`):

```python
from fastapi_app import app
from mangum import Mangum
handler = Mangum(app, lifespan="off")
```

Set all environment variables in the Vercel project dashboard.

### Local gRPC (development)

```bash
# Both gRPC :50051 and gRPC-Web :8080 in one command
cd src/backend
python main.py
```

---

## Authentication

The backend validates **RS256 JWTs** issued by Auth0 on all protected endpoints.

**Setup:**

1. Create an Auth0 API → note domain, client ID, client secret, audience
2. Add to `.env`:
   ```
   AUTH0_DOMAIN=your-tenant.auth0.com
   AUTH0_AUDIENCE=https://your-api-audience
   AUTH0_CLIENT_ID=your-client-id
   AUTH0_CLIENT_SECRET=your-client-secret
   ```

**How it works:**

```
Client → POST /api/auth/token → Auth0 → returns JWT
Client → any protected endpoint + "Authorization: Bearer <JWT>"
FastAPI → fetches JWKS from Auth0 → verifies RS256 signature, audience, issuer, expiry
        → extracts sub claim → passes to route handler as current_user
```

---

## Observability

Every agent run is traced in Langfuse:

- LLM prompts, completions, token counts
- Tool invocations with arguments and outputs
- End-to-end and per-step latency
- Errors with full context
- Session grouping by `session_id`

**Setup:**

```
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_HOST=https://cloud.langfuse.com
```

Leave keys empty to disable tracing (agent works identically without Langfuse).

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GEMINI_API_KEY` | Yes | — | Google AI Studio key |
| `GEMINI_MODEL_NAME` | No | `gemini-2.0-flash` | Model identifier |
| `GEMINI_BASE_URL` | No | Google OpenAI-compat URL | API base URL |
| `SERPAPI_API_KEY` | Yes | — | SerpAPI key for Google Jobs |
| `AUTH0_DOMAIN` | Yes* | — | Auth0 tenant domain |
| `AUTH0_AUDIENCE` | Yes* | — | Auth0 API audience |
| `AUTH0_CLIENT_ID` | Yes* | — | Auth0 client ID |
| `AUTH0_CLIENT_SECRET` | Yes* | — | Auth0 client secret |
| `LANGFUSE_SECRET_KEY` | No | `""` | Disables tracing if empty |
| `LANGFUSE_PUBLIC_KEY` | No | `""` | Disables tracing if empty |
| `LANGFUSE_HOST` | No | `https://cloud.langfuse.com` | Langfuse server |
| `GRPC_PORT` | No | `50051` | gRPC server port |
| `GRPC_WEB_PORT` | No | `8080` | gRPC-Web port |
| `GRPC_WORKERS` | No | `10` | gRPC thread pool size |

*Required only for protected endpoints.

---

## Documentation

| Document | Location | Description |
|----------|----------|-------------|
| Technical Document | [`docs/technical-document.md`](docs/technical-document.md) | Architecture, API spec, module reference, LCEL chains, gRPC service, testing strategy |
| User Manual | [`docs/user-manual.md`](docs/user-manual.md) | End-user guide with feature walkthroughs, API examples, troubleshooting |
| Demo Presentation | [`docs/Job_Placement_Agent_Demo.pptx`](docs/Job_Placement_Agent_Demo.pptx) | 12-slide project overview (generate via `python docs/generate_ppt.py`) |
| Interactive API Docs | `/docs` (Swagger UI) | Live API explorer when backend is running |
