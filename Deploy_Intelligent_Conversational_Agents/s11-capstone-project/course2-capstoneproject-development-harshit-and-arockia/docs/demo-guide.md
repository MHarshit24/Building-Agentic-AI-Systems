# Job Placement Agent — Demo Guide

**Project:** Course 2 Capstone — Intelligent Conversational Agent  
**Stack:** FastAPI · LangChain · Google Gemini · Auth0 · gRPC · Langfuse  
**Base URL (local):** `http://localhost:8000`  
**gRPC Server:** `localhost:50051`

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Technical Definitions](#technical-definitions)
3. [Demo Flow (REST API)](#demo-flow-rest-api)
   - [1. Health Check](#1-health-check)
   - [2. Authentication — Get Token](#2-authentication--get-token)
   - [3. Conversational Chat (Public)](#3-conversational-chat-public)
   - [4. Conversational Chat (Authenticated)](#4-conversational-chat-authenticated)
   - [5. Job Search](#5-job-search)
   - [6. Resume Analysis + Skill Gap](#6-resume-analysis--skill-gap)
   - [7. Cover Letter Generation](#7-cover-letter-generation)
   - [8. Session Management](#8-session-management)
   - [9. Streaming Chat (SSE)](#9-streaming-chat-sse)
4. [Demo Flow (gRPC)](#demo-flow-grpc)
5. [Error Scenarios](#error-scenarios)
6. [API Response Envelope](#api-response-envelope)

---

## Architecture Overview

```
CLIENTS
├── REST (curl / Postman / Swagger UI at /docs)
├── gRPC (grpcurl / Streamlit app)
└── gRPC-Web (Browser — index.html)

                     ┌─────────────────────────────────┐
                     │         FastAPI  :8000           │
                     │  Auth0 JWT → LangChain Agent     │
                     │  ┌────────────────────────────┐  │
                     │  │  Tool-Calling Agent        │  │
                     │  │  ├─ search_jobs (SerpAPI)  │  │
                     │  │  ├─ analyze_resume (LLM)   │  │
                     │  │  └─ generate_cover_letter  │  │
                     │  └────────────────────────────┘  │
                     └──────────┬──────────────────┬────┘
                          gRPC :50051        gRPC-Web :8080
                          (Streamlit)        (Browser)

EXTERNAL SERVICES
  Google Gemini API  ←  LLM inference
  SerpAPI            ←  Real-time Google Jobs
  Auth0              ←  RS256 JWT tokens
  Langfuse           ←  LLM call tracing & monitoring
```

---

## Technical Definitions

### LangChain Agent
A **tool-calling agent** built with `create_tool_calling_agent` + `AgentExecutor`. On each user message it:
1. Sends the message + conversation history to Gemini
2. Gemini decides which tool (if any) to invoke
3. The agent executes the tool and feeds the result back to Gemini
4. Gemini composes the final answer

**Max iterations:** 6 per request to prevent infinite loops.

### LCEL (LangChain Expression Language)
Declarative pipe syntax for composing chains:
```python
chain = ChatPromptTemplate | LLM | StrOutputParser()
result = chain.invoke({"input": "..."})
```
Used for resume analysis, cover letter generation, and the intent router.

### RunnableWithMessageHistory (Session Memory)
Wraps the agent to inject per-session `ChatMessageHistory` into every invocation. Sessions are identified by `session_id` and stored in-memory. Enables multi-turn conversations where the agent remembers earlier context.

### RunnableBranch (Intent Router)
An LCEL component that classifies the user's intent (`job_search | resume | cover_letter | general`) and routes to the appropriate specialist chain. Classification uses a lightweight Gemini call before the main agent executes.

### Auth0 RS256 JWT
**Authentication flow:**
1. Client `POST /api/auth/token` → receives `access_token`
2. All protected endpoints require `Authorization: Bearer <token>`
3. Backend fetches Auth0's JWKS (cached), verifies RS256 signature, checks audience/issuer/expiry
4. Invalid/missing token → `401 Unauthorized`

### Langfuse Observability
Every agent invocation emits a **trace** containing:
- LLM calls (prompt, completion, token counts, latency)
- Tool invocations (name, input, output)
- Session grouping for conversation-level analytics

Disabled gracefully when `LANGFUSE_SECRET_KEY` is empty.

### gRPC Transport
Binary protocol with Protocol Buffers. All 10 RPCs mirror the REST endpoints. Protected RPCs require `authorization: Bearer <token>` in gRPC call **metadata** (not HTTP headers).

### SerpAPI Google Jobs
Real-time job listings fetched via SerpAPI's `google_jobs` engine. Returns title, company, location, description, and apply link for each listing.

### Pydantic v2 Validation
All request bodies are validated before reaching business logic:
- `message`: 1–4,000 chars, non-blank
- `resume_text`: 50–50,000 chars
- `session_id`: 1–128 alphanumeric/hyphen/underscore chars
- `username`: must be valid email format

### ApiResponse Envelope
Every REST response is wrapped in a consistent envelope:
```json
{
  "success": true,
  "data": { "...": "..." },
  "error": null,
  "meta": {
    "request_id": "uuid-v4",
    "api_version": "1.0.0"
  }
}
```

---

## Demo Flow (REST API)

### 1. Health Check

**Purpose:** Verify the service is running. No authentication required.

**Request**
```http
GET /api/health HTTP/1.1
Host: localhost:8000
```

```bash
curl http://localhost:8000/api/health
```

**Response** `200 OK`
```json
{
  "success": true,
  "data": {
    "status": "healthy",
    "version": "1.0.0",
    "message": "Job Placement Agent API is running"
  },
  "error": null,
  "meta": {
    "request_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "api_version": "1.0.0"
  }
}
```

---

### 2. Authentication — Get Token

**Purpose:** Obtain a JWT access token from Auth0 to use with protected endpoints.

**Request**
```http
POST /api/auth/token HTTP/1.1
Content-Type: application/json

{
  "username": "demo@example.com",
  "password": "DemoPassword123!"
}
```

```bash
curl -X POST http://localhost:8000/api/auth/token \
  -H "Content-Type: application/json" \
  -d '{"username": "demo@example.com", "password": "DemoPassword123!"}'
```

**Response** `200 OK`
```json
{
  "success": true,
  "data": {
    "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhdXRoMHwxMjM0NTY3ODkwIiwiYXVkIjoiaHR0cHM6Ly9qb2ItYWdlbnQtYXBpIiwiaXNzIjoiaHR0cHM6Ly9kZXYteHh4eHh4LmF1dGgwLmNvbS8iLCJleHAiOjE3MTQwMDAwMDB9.SIGNATURE",
    "token_type": "Bearer",
    "expires_in": 86400
  },
  "error": null,
  "meta": {
    "request_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "api_version": "1.0.0"
  }
}
```

**Key fields:**
| Field | Value | Description |
|-------|-------|-------------|
| `access_token` | JWT string | Include in `Authorization` header |
| `token_type` | `"Bearer"` | Header prefix |
| `expires_in` | `86400` | Token valid for 24 hours (seconds) |

---

### 3. Conversational Chat (Public)

**Purpose:** Chat with the agent without authentication (demo / unauthenticated mode).

**Request**
```http
POST /api/chat/public HTTP/1.1
Content-Type: application/json

{
  "message": "I'm looking for a software engineer job in Bangalore. Can you help?",
  "session_id": "demo-session-001"
}
```

```bash
curl -X POST http://localhost:8000/api/chat/public \
  -H "Content-Type: application/json" \
  -d '{
    "message": "I am looking for a software engineer job in Bangalore. Can you help?",
    "session_id": "demo-session-001"
  }'
```

**Response** `200 OK`
```json
{
  "success": true,
  "data": {
    "response": "I'd be happy to help you find software engineer positions in Bangalore! Let me search for the latest openings.\n\nHere are some current Software Engineer opportunities in Bangalore:\n\n1. **Senior Software Engineer** — Infosys\n   Location: Bangalore, Karnataka\n   Skills: Java, Spring Boot, Microservices\n   Apply: https://infosys.com/careers/...\n\n2. **Software Engineer II** — Amazon\n   Location: Bangalore (Hybrid)\n   Skills: Python, AWS, Distributed Systems\n   Apply: https://amazon.jobs/...\n\n3. **Full Stack Developer** — Wipro\n   Location: Bangalore, Karnataka\n   Skills: React, Node.js, MongoDB\n   Apply: https://wipro.com/careers/...\n\nWould you like me to analyze your resume against any of these roles, or generate a cover letter for a specific position?",
    "session_id": "demo-session-001"
  },
  "error": null,
  "meta": {
    "request_id": "f7e8d9c0-b1a2-3456-cdef-789012345678",
    "api_version": "1.0.0"
  }
}
```

---

### 4. Conversational Chat (Authenticated)

**Purpose:** Full-featured chat with Auth0 JWT. Maintains multi-turn conversation memory per `session_id`.

**Request**
```http
POST /api/chat HTTP/1.1
Authorization: Bearer eyJhbGciOiJSUzI1NiIs...
Content-Type: application/json

{
  "message": "What Python skills should I add to my resume to get a data engineer role?",
  "session_id": "user-abc-session-1"
}
```

```bash
TOKEN="eyJhbGciOiJSUzI1NiIs..."

curl -X POST http://localhost:8000/api/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What Python skills should I add to my resume to get a data engineer role?",
    "session_id": "user-abc-session-1"
  }'
```

**Response** `200 OK`
```json
{
  "success": true,
  "data": {
    "response": "For a **Data Engineer** role, here are the key Python skills to add to your resume:\n\n**Core Libraries:**\n- `pandas` — data manipulation and transformation\n- `PySpark` — distributed data processing\n- `SQLAlchemy` — ORM and database connectivity\n\n**Pipeline & Orchestration:**\n- `Apache Airflow` — workflow scheduling (often Python DAGs)\n- `dbt` — data transformation pipelines\n\n**Cloud & Storage:**\n- `boto3` (AWS S3/Glue), `google-cloud-storage`, Azure SDK\n- Snowflake Connector for Python\n\n**Streaming:**\n- `kafka-python` or `confluent-kafka` for real-time pipelines\n\nWould you like me to analyze your current resume to identify specific gaps for a data engineer role?",
    "session_id": "user-abc-session-1"
  },
  "error": null,
  "meta": {
    "request_id": "1a2b3c4d-5e6f-7890-abcd-ef0123456789",
    "api_version": "1.0.0"
  }
}
```

**Multi-turn follow-up (same session_id preserves context):**
```json
{
  "message": "Great! Now search for data engineer jobs in Hyderabad.",
  "session_id": "user-abc-session-1"
}
```
> The agent remembers the earlier conversation about Python skills and continues the context.

---

### 5. Job Search

**Purpose:** Directly trigger the SerpAPI Google Jobs search tool.

**Request**
```http
POST /api/jobs/search HTTP/1.1
Authorization: Bearer eyJhbGciOiJSUzI1NiIs...
Content-Type: application/json

{
  "query": "Machine Learning Engineer",
  "location": "Remote",
  "session_id": "job-search-session"
}
```

```bash
curl -X POST http://localhost:8000/api/jobs/search \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Machine Learning Engineer",
    "location": "Remote",
    "session_id": "job-search-session"
  }'
```

**Response** `200 OK`
```json
{
  "success": true,
  "data": {
    "results": "Here are the latest Machine Learning Engineer positions (Remote):\n\n1. **Machine Learning Engineer** — Google\n   Location: Remote (US)\n   Description: Work on large-scale ML systems for Search and Ads. Requires TensorFlow, PyTorch, and distributed training experience.\n   Apply: https://careers.google.com/jobs/...\n\n2. **Senior ML Engineer** — Anthropic\n   Location: Remote\n   Description: Build and optimize foundation model training pipelines. Python, JAX, and CUDA expertise required.\n   Apply: https://anthropic.com/careers/...\n\n3. **ML Engineer — Recommendations** — Netflix\n   Location: Remote (Americas)\n   Description: Develop personalization algorithms for 230M+ users. Skills: PyTorch, Spark, A/B testing.\n   Apply: https://jobs.netflix.com/...\n\n4. **Machine Learning Engineer** — Swiggy\n   Location: Remote / Bangalore\n   Description: Build ML models for demand forecasting and logistics optimization. Python, scikit-learn, XGBoost.\n   Apply: https://careers.swiggy.com/...\n\n5. **Junior ML Engineer** — Zepto\n   Location: Remote-first\n   Description: Entry-level ML role focused on computer vision for quick commerce. OpenCV, PyTorch, cloud deployment.\n   Apply: https://zepto.com/careers/...",
    "session_id": "job-search-session"
  },
  "error": null,
  "meta": {
    "request_id": "d4e5f6a7-b8c9-0123-def4-567890abcdef",
    "api_version": "1.0.0"
  }
}
```

---

### 6. Resume Analysis + Skill Gap

**Purpose:** LLM-powered analysis of a resume. When `job_description` is provided, performs skill gap detection with a match percentage.

**Request — Resume Analysis with Skill Gap**
```http
POST /api/resume/analyze HTTP/1.1
Authorization: Bearer eyJhbGciOiJSUzI1NiIs...
Content-Type: application/json

{
  "resume_text": "John Doe\nSoftware Engineer | 3 years experience\n\nSKILLS\nPython, Django, PostgreSQL, Git, REST APIs, Docker\n\nEXPERIENCE\nBackend Developer — TechCorp (2021–2024)\n- Built REST APIs with Django and PostgreSQL\n- Deployed apps using Docker and Linux servers\n- Wrote unit tests with pytest\n\nEDUCATION\nB.E. Computer Science — Anna University (2021)",

  "job_description": "We are hiring a Senior Data Engineer. Requirements: Python, Apache Spark, PySpark, Kafka, Airflow, AWS (S3/Glue/Redshift), dbt, SQL, distributed systems, 4+ years experience.",

  "session_id": "resume-demo-session"
}
```

**Response** `200 OK`
```json
{
  "success": true,
  "data": {
    "analysis": "## Resume Analysis Report\n\n### Extracted Skills\n**Technical Skills:** Python, Django, PostgreSQL, Git, REST APIs, Docker\n**Soft Skills:** Implied team collaboration, problem-solving\n**Experience Level:** Mid-level (3 years)\n\n### Resume Quality Score: 6.5 / 10\n**Strengths:**\n- Strong backend foundation with Python\n- Practical deployment experience with Docker\n- Testing discipline with pytest\n\n**Areas for Improvement:**\n- Add quantifiable achievements (e.g., \"Reduced API latency by 40%\")\n- Missing education GPA or academic achievements\n- No mention of cloud platforms\n\n---\n\n### Skill Gap Analysis vs. Senior Data Engineer Role\n**Match Score: 28%**\n\n✅ **Matched Skills:** Python, SQL (via PostgreSQL), Docker\n\n❌ **Missing Skills (High Priority):**\n| Skill | Importance | Learning Path |\n|-------|-----------|---------------|\n| Apache Spark / PySpark | Critical | Coursera — Big Data with Spark |\n| Apache Kafka | Critical | Kafka documentation + Udemy |\n| Apache Airflow | High | Astronomer.io tutorials |\n| AWS (S3, Glue, Redshift) | High | AWS Free Tier + Cloud Practitioner |\n| dbt (data build tool) | Medium | dbt Learn — free online course |\n\n**Experience Gap:** Role requires 4+ years; your profile shows 3 years.\n\n### Recommendations\n1. Complete an AWS Cloud Practitioner certification\n2. Build a personal project using PySpark + Airflow + S3\n3. Contribute to open-source data engineering tools\n4. Rewrite resume bullet points with metrics and impact",
    "session_id": "resume-demo-session"
  },
  "error": null,
  "meta": {
    "request_id": "c3b2a1f0-e9d8-7654-3210-fedcba987654",
    "api_version": "1.0.0"
  }
}
```

---

### 7. Cover Letter Generation

**Purpose:** Generate a personalized cover letter tailored to a specific job and company.

**Request**
```http
POST /api/cover-letter/gen HTTP/1.1
Authorization: Bearer eyJhbGciOiJSUzI1NiIs...
Content-Type: application/json

{
  "resume_text": "John Doe\nSoftware Engineer | 3 years experience\nSkills: Python, Django, PostgreSQL, Docker, REST APIs\nExperience: Backend Developer at TechCorp (2021–2024)\n- Built REST APIs serving 500K daily requests\n- Reduced deployment time by 60% using Docker\n- Mentored 2 junior developers",

  "job_title": "Senior Backend Engineer",
  "company_name": "Zepto",

  "job_description": "Zepto is looking for a Senior Backend Engineer to build high-performance APIs for our quick-commerce platform. You will work on real-time inventory, order management, and delivery systems. Required: Python, FastAPI/Django, PostgreSQL, Redis, microservices, AWS.",

  "user_name": "John Doe",
  "session_id": "cover-letter-session"
}
```

**Response** `200 OK`
```json
{
  "success": true,
  "data": {
    "cover_letter": "John Doe\njohn.doe@email.com | LinkedIn: linkedin.com/in/johndoe\n\nApril 19, 2026\n\nHiring Manager\nZepto Engineering Team\n\nDear Hiring Manager,\n\nI am writing to express my enthusiastic interest in the Senior Backend Engineer position at Zepto. As a software engineer with 3 years of experience building high-performance REST APIs and scalable backend systems, I am drawn to Zepto's mission of redefining quick-commerce through technology.\n\nIn my current role at TechCorp, I designed and maintained REST APIs that handle over 500,000 daily requests — a scale that closely mirrors the performance demands of Zepto's real-time inventory and order management systems. I reduced deployment time by 60% by containerizing services with Docker, and I have hands-on experience with PostgreSQL for transactional data and Python/Django for rapid API development.\n\nWhat excites me most about this role is the real-time nature of Zepto's platform — managing live inventory, coordinating delivery logistics, and ensuring sub-second response times. I am eager to deepen my expertise in Redis caching and AWS infrastructure to meet these demands, building on the microservices patterns I have already applied in production.\n\nBeyond technical skills, I value mentorship and collaboration. Having guided two junior engineers at TechCorp, I understand that strong engineering teams require both technical excellence and shared knowledge.\n\nI would welcome the opportunity to discuss how my background aligns with Zepto's engineering goals. Thank you for your time and consideration.\n\nWarm regards,\nJohn Doe",
    "session_id": "cover-letter-session"
  },
  "error": null,
  "meta": {
    "request_id": "9e8d7c6b-5a4f-3e2d-1c0b-a9b8c7d6e5f4",
    "api_version": "1.0.0"
  }
}
```

---

### 8. Session Management

#### Create a New Session
```bash
curl -X POST http://localhost:8000/api/session
```
**Response**
```json
{
  "success": true,
  "data": {
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "message": "Session created successfully."
  },
  "error": null,
  "meta": { "request_id": "...", "api_version": "1.0.0" }
}
```

#### List Active Sessions
```bash
curl -X GET http://localhost:8000/api/sessions \
  -H "Authorization: Bearer $TOKEN"
```
**Response**
```json
{
  "success": true,
  "data": {
    "sessions": [
      "demo-session-001",
      "user-abc-session-1",
      "resume-demo-session",
      "550e8400-e29b-41d4-a716-446655440000"
    ]
  },
  "error": null,
  "meta": { "request_id": "...", "api_version": "1.0.0" }
}
```

#### Clear a Session
```bash
curl -X DELETE http://localhost:8000/api/chat/demo-session-001 \
  -H "Authorization: Bearer $TOKEN"
```
**Response**
```json
{
  "success": true,
  "data": {
    "message": "Session cleared successfully.",
    "session_id": "demo-session-001"
  },
  "error": null,
  "meta": { "request_id": "...", "api_version": "1.0.0" }
}
```

---

### 9. Streaming Chat (SSE)

**Purpose:** Receive the agent's response as a stream of tokens via Server-Sent Events.

**Request**
```bash
curl -X POST http://localhost:8000/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "Find me Python developer jobs in Chennai", "session_id": "stream-demo"}'
```

**Response** — SSE stream (each line is a token chunk):
```
data: Here

data:  are

data:  some

data:  Python

data:  Developer

data:  positions

data:  in

data:  Chennai

data:  ...

data: [DONE]
```

---

## Demo Flow (gRPC)

### Using `grpcurl`

```bash
# Health Check
grpcurl -plaintext localhost:50051 job_agent.JobAgentService/HealthCheck

# Get Token
grpcurl -plaintext -d '{
  "username": "demo@example.com",
  "password": "DemoPassword123!"
}' localhost:50051 job_agent.JobAgentService/GetToken

# Public Chat (no auth)
grpcurl -plaintext -d '{
  "message": "Find software engineer jobs in Mumbai",
  "session_id": "grpc-demo"
}' localhost:50051 job_agent.JobAgentService/ChatPublic

# Authenticated Chat (protected RPC)
grpcurl -plaintext \
  -H "authorization: Bearer eyJhbGciOiJSUzI1NiIs..." \
  -d '{
    "message": "Analyze my resume for a Python backend role",
    "session_id": "grpc-auth-demo"
  }' localhost:50051 job_agent.JobAgentService/Chat

# Job Search
grpcurl -plaintext \
  -H "authorization: Bearer $TOKEN" \
  -d '{
    "query": "Data Scientist",
    "location": "Bangalore",
    "session_id": "grpc-demo"
  }' localhost:50051 job_agent.JobAgentService/SearchJobs
```

### gRPC Response — HealthCheck
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "message": "Job Placement Agent API is running"
}
```

### gRPC Response — GetToken
```json
{
  "access_token": "eyJhbGciOiJSUzI1NiIs...",
  "token_type": "Bearer",
  "expires_in": 86400
}
```

### gRPC Response — SearchJobs
```json
{
  "results": "Here are Data Scientist positions in Bangalore:\n\n1. Data Scientist — Flipkart\n   Location: Bangalore\n   Skills: Python, SQL, scikit-learn, MLflow\n   ...",
  "session_id": "grpc-demo"
}
```

---

## Error Scenarios

### 401 — Invalid / Missing Token
```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "AUTH0_CREDENTIALS_ERROR",
    "message": "Invalid credentials. Please check your username and password."
  },
  "meta": { "request_id": "...", "api_version": "1.0.0" }
}
```

### 422 — Validation Error (blank message)
```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "message: message must not be blank."
  },
  "meta": { "request_id": "...", "api_version": "1.0.0" }
}
```

### 429 — Rate Limit (Gemini / SerpAPI)
```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "GEMINI_RATE_LIMIT",
    "message": "LLM rate limit reached. Please retry after a short delay."
  },
  "meta": { "request_id": "...", "api_version": "1.0.0" }
}
```

### 500 — Missing API Key
```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "GEMINI_CONFIG_ERROR",
    "message": "GEMINI_API_KEY is not configured on the server."
  },
  "meta": { "request_id": "...", "api_version": "1.0.0" }
}
```

### 502 — Agent Failure
```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "AGENT_ERROR",
    "message": "The AI agent encountered an unexpected error. Please try again."
  },
  "meta": { "request_id": "...", "api_version": "1.0.0" }
}
```

---

## API Response Envelope

All REST responses follow this structure:

```json
{
  "success": true | false,
  "data": { /* endpoint-specific payload, null on error */ },
  "error": null | {
    "code": "ERROR_CODE_STRING",
    "message": "Human-readable description"
  },
  "meta": {
    "request_id": "uuid-v4 — unique per request for debugging",
    "api_version": "1.0.0"
  }
}
```

**HTTP Status → Error Code Mapping:**

| HTTP Status | Scenario | Error Code |
|-------------|----------|------------|
| `400` | LLM blocked or malformed content | `GEMINI_INVALID_REQUEST` |
| `401` | Missing/invalid/expired JWT | `AUTH0_CREDENTIALS_ERROR` |
| `422` | Pydantic field validation failed | `VALIDATION_ERROR` |
| `429` | LLM or SerpAPI rate limit hit | `GEMINI_RATE_LIMIT` / `SERPAPI_RATE_LIMIT` |
| `500` | Missing server-side API key | `GEMINI_CONFIG_ERROR` / `SERPAPI_CONFIG_ERROR` |
| `502` | LangChain agent execution failed | `AGENT_ERROR` |
| `503` | External service unreachable | `*_NETWORK_ERROR` |

---

*Swagger UI available at `http://localhost:8000/docs` when the server is running.*

---

## Troubleshooting

### 422 — "JSON decode error: Invalid \escape"

**Error:**
```json
{
  "detail": [
    {
      "type": "json_invalid",
      "loc": ["body", 61],
      "msg": "JSON decode error",
      "ctx": { "error": "Invalid \\escape" }
    }
  ]
}
```

**Cause:** The request body contains a backslash `\` followed by a character that is not a valid JSON escape sequence.

Valid JSON escapes: `\"`, `\\`, `\/`, `\b`, `\f`, `\n`, `\r`, `\t`, `\uXXXX`

Invalid (will cause 422): `\e`, `\s`, `\w`, `\U`, `\p`, `\A` — anything else.

**Common sources in resume/cover-letter fields:**
| Bad input | Why it breaks | Fix |
|-----------|--------------|-----|
| `C:\Users\john` | `\U` is not a valid escape | `C:\\Users\\john` |
| `\nExperience:` if typed literally | depends on context | Use `\\n` or just a space |
| Pasted text from Word/PDF | may embed hidden `\` chars | Strip backslashes before pasting |

**Safest fix — avoid backslashes entirely in demo input.** Use spaces instead of `\n` for line breaks when typing in Swagger UI, or use the pre-formatted curl commands in this guide which use valid `\n` JSON escapes.

**To verify your JSON before sending:**
Paste it at [jsonlint.com](https://jsonlint.com) — it will highlight the exact invalid character position.

---

### Auth0: "Grant type 'password' not allowed for the client"

**Error:**
```json
{
  "error": {
    "code": "AUTH0_INVALID_CREDENTIALS",
    "message": "Grant type 'password' not allowed for the client."
  }
}
```

**Cause:** The Auth0 app does not have the **Resource Owner Password Grant** enabled. This grant type is disabled by default.

**Fix — Two steps required in the Auth0 Dashboard:**

**Step 1 — Enable Password grant on the Application:**
1. Go to **Auth0 Dashboard → Applications → [Your App] → Settings**
2. Scroll down → click **Advanced Settings**
3. Click the **Grant Types** tab
4. Check **Password**
5. Click **Save Changes**

**Step 2 — Set the Default Directory on the Tenant:**
1. Go to **Auth0 Dashboard → Settings** (top-left tenant settings)
2. Scroll to **API Authorization Settings**
3. Set **Default Directory** to your database connection name
   (usually `Username-Password-Authentication`)
4. Click **Save**

Without Step 2, the password grant will still fail even after Step 1.

---

### Auth0: "unauthorized_client" or 403 on token endpoint

Ensure your Auth0 API (not Application) also allows the `password` grant:
- Go to **Auth0 Dashboard → APIs → [Your API] → Settings**
- Scroll to **Access Settings**
- Enable **Allow Offline Access** if refresh tokens are needed
