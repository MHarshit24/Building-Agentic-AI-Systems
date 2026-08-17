# Product Manual RAG System - Human Handoff

## Project Context

You're building a **Product Manual RAG System**, an AI-powered system that helps users get answers to questions about product features, installation, configuration, troubleshooting, and usage instructions.

This practice focuses on **human handoff** — implementing automated escalation mechanisms that detect when the RAG system cannot provide reliable answers and seamlessly transfer conversations to human support agents. You'll learn how to evaluate answer quality, detect user frustration, and trigger handoff workflows with comprehensive context.

## Problem Statement

Build a RAG system with human handoff capabilities. The system must support document indexing, query processing, and automatic escalation when answer quality falls below thresholds or users explicitly request human assistance. You need to implement handoff detection logic, confidence scoring, and email notification workflows that provide support agents with full context.

You will complete multiple implementation tasks to build this handoff-enabled RAG system:

---

### **Task 1 — Implement Handoff Service Functions**

#### Goal

Build the core handoff service functions that evaluate answer quality, detect handoff triggers, and send notification emails.

#### Requirements

1. Implement `generate_handoff_reference_id()` to generate unique handoff reference IDs in format "HO-{YYYYMMDD-HHMMSS}-{6-char-hex-uppercase}"

2. Implement `evaluate_score()` to determine if handoff should be triggered based on faithfulness, relevance, and retrieval status

3. Implement `evaluate_confidence_score()` to evaluate LLM confidence score for generated answers using LLM-as-a-judge

4. Implement `evaluate_explicit_user_request()` to classify explicit user requests for human help using LLM-based classification

5. Implement `send_handoff_email()` to send handoff notification emails via SMTP with full context

**File**: `main/handoff/handoff_service.py`

---

### **Task 2 — Implement Query Endpoint with Handoff Logic**

#### Goal

Integrate handoff detection and escalation into the API query endpoint with comprehensive evaluation and context building.

#### Requirements

1. Generate session ID and initialize conversation flow

2. Execute RAG query and extract answer with full retrieved chunks

3. Create Langfuse span for tracing and get trace ID

4. Run evaluation scores (faithfulness, relevance, confidence) and explicit user request detection

5. Implement handoff decision logic with priority levels (high/normal)

6. Build handoff context payload with all relevant information

7. Send handoff email via background tasks when triggered

8. Return appropriate response (handoff message or normal answer with source nodes)

**File**: `main/routes/routes.py` - `query_rag()`

---

## Evaluation Criteria

Ensure you evaluate your solution against the below criteria:

1. **generate_handoff_reference_id**: Function generates unique handoff reference IDs following the format "HO-{YYYYMMDD-HHMMSS}-{6-char-hex-uppercase}". Uses UTC timezone and handles optional datetime parameter correctly. Hex portion is uppercase and exactly 6 characters.

2. **evaluate_score**: Function correctly evaluates all handoff trigger conditions in the proper order: no_chunks check, missing evaluation scores, faithfulness threshold, relevance threshold, and keyword detection. Returns appropriate trigger status and reason strings for each condition.

3. **evaluate_confidence_score**: Function uses LLM-as-a-judge to evaluate confidence scores. Properly initializes LLM from Settings, creates structured prompt, extracts numeric score from response (defaults to 50 if parsing fails), and returns trigger status based on CONFIDENCE_THRESHOLD. Handles LLM initialization errors.

4. **evaluate_explicit_user_request**: Function uses LLM-based classification with structured prompt to detect explicit user requests. Returns YES/NO classification correctly, checks response for "YES" case-insensitively, and returns appropriate trigger status with reason when detected.

5. **send_handoff_email**: Function checks for all required SMTP configuration variables and handles missing configuration gracefully with warnings. Creates properly formatted email with subject and body containing all context fields (reference_id, trace_id, timestamp, priority, trigger_reason, user metadata, query history, generated answer, evaluation scores, retrieved chunks, conversation flow). Uses MIMEText, SMTP with STARTTLS, and handles email sending errors.

6. **Query Endpoint Handoff Integration**: Query endpoint implements complete handoff workflow. Session and trace IDs are generated. RAG query executes and chunks are extracted. All evaluators run asynchronously. Handoff decision logic follows priority rules (explicit request → confidence with risk → score-based). Handoff context includes all required fields. Email notifications are sent via background tasks. Normal responses format source nodes correctly.

---

## Implementation Details

### Project Structure

```
s10-add-human-handoff-with-context-transfer/
├── document/
│   └── CloudSync_Pro_User_Manual.txt   # Knowledge base document
├── main/
│   ├── evaluation/
│   │   ├── dataset.py                  # Langfuse dataset creation
│   │   └── dataset_evaluation.py       # LLM-as-a-judge evaluation pipeline
│   ├── handoff/
│   │   └── handoff_service.py          # Handoff detection and email logic
│   ├── routes/
│   │   └── routes.py                   # FastAPI route handlers
│   ├── service/
│   │   ├── indexing.py                 # Document loading and vector indexing
│   │   ├── query_engine.py             # Query engine creation
│   │   └── rag_service.py              # Shared RAG service initialization
│   └── app.py                          # FastAPI app setup
└── main.py                             # Application entry point
```

### Environment Configuration

The system uses a dual `.env` loading pattern to keep secrets isolated from project-level configuration. The root `.env` at `Building_Agentic_AI_Systems/` is loaded first and holds all sensitive credentials. The project `.env` is loaded second with `override=True` for deployment names and database config. After the second load, all secrets from the root are explicitly restored so the project `.env` can never overwrite them.

The root `.env` holds: `DB_PASSWORD`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_HOST`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `APPLICATION_EMAIL`, `SUPPORT_EMAIL`.

The project `.env` holds: `DB_USER`, `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_TABLE_NAME`, `AZURE_OPENAI_EMBEDDING_DEPLOYMENT`, `AZURE_OPENAI_LLM_DEPLOYMENT`, `AZURE_OPENAI_API_VERSION`, and API server settings.

This dual loading pattern is applied consistently in `main.py`, `rag_service.py`, and `handoff_service.py` so that every entry point into the system loads credentials correctly regardless of how the process is started.

### Database Setup

The system uses PostgreSQL with PGVector for vector storage. A dedicated table `handoff_vectors` is used for this assignment, keeping it fully isolated from any other assignment's data even when sharing the same database. The `DB_PASSWORD` is always passed through `urllib.parse.quote_plus` when constructing the SQLAlchemy connection URL to safely handle special characters.

### Task 1 — Handoff Service Implementation

**`generate_handoff_reference_id()`** generates a unique reference ID by combining the current UTC timestamp formatted as `YYYYMMDD-HHMMSS` with a 3-byte cryptographically random token converted to uppercase hex, producing IDs in the format `HO-20260609-163026-29F9B7`. An optional `now` parameter allows injecting a specific datetime for deterministic testing.

**`evaluate_score()`** checks handoff trigger conditions in strict priority order. It first checks whether retrieval returned no chunks at all, then whether either evaluation score is missing (None), then whether faithfulness falls below 0.6, then whether relevance falls below 0.5, and finally whether the user's question contains keywords such as "human", "agent", "support", or "escalate". Each condition returns a distinct reason string so the support agent knows exactly why escalation was triggered. If none of the conditions match, it returns `{"trigger": False}`.

**`evaluate_confidence_score()`** uses the LLM configured in `Settings.llm` as a judge to rate how confident an answer appears on a scale of 0 to 100. The prompt instructs the LLM to return only a single integer. The response is parsed using regex digit extraction, defaulting to 50 if parsing fails, and clamped to the valid range. A score below the `CONFIDENCE_THRESHOLD` of 40 triggers handoff with reason "low confidence score".

**`evaluate_explicit_user_request()`** uses the LLM as a binary classifier. The prompt asks the LLM to respond with only "YES" or "NO" based on whether the user is explicitly requesting a human agent or expressing strong frustration. The response text is uppercased before checking for "YES" to handle any casing variation the LLM might produce.

**`send_handoff_email()`** first validates that all five required SMTP configuration variables are present, logging a warning and returning early if any are missing so the system degrades gracefully without crashing. It then builds a structured plain-text email body containing the reference ID, trace ID, timestamp, priority level, trigger reason, user metadata, query history, the generated answer, all three evaluation scores, the full retrieved chunks, and the conversation flow steps. The email is sent via `smtplib.SMTP` with `starttls()` for encrypted transport. All sending errors are caught and logged without re-raising so a failed email never breaks the API response.

### Task 2 — Query Endpoint Implementation

The `query_rag()` endpoint in `routes.py` orchestrates the full handoff workflow across eight steps.

A unique `session_id` is generated using `secrets.token_hex(8)` at the start of each request, and a `conversation_flow` list is maintained throughout to record every significant step. This list is included in the handoff email so support agents have a complete audit trail of what happened during the session.

The RAG query is executed using the shared query engine from `rag_service.py`. Retrieved source nodes are collected into a `full_chunks` list immediately after the query, and `no_chunks` is set to True if retrieval returned nothing, which feeds directly into `evaluate_score()`.

Langfuse tracing uses the v4 API pattern: `create_trace_id()` generates the trace ID first, then `start_observation()` opens a span linked to that trace via `trace_context={"trace_id": trace_id}`. This produces a trace in the Langfuse dashboard with faithfulness and relevance scores attached as named scores.

All four evaluators — faithfulness, relevance, confidence, and explicit user request detection — are launched concurrently using `asyncio.gather()` so they run in parallel rather than sequentially, keeping latency low.

The handoff decision follows a strict three-level priority system. An explicit user request for human help always triggers high-priority handoff regardless of evaluation scores. If the confidence evaluator fires and the score evaluator also independently flags a problem, that combination also triggers high-priority handoff. A score-based trigger alone (no chunks, missing scores, low faithfulness, or low relevance) triggers normal-priority handoff. If none of these conditions are met, a normal response is returned with source nodes truncated to 200 characters each.

When handoff is triggered, the email is dispatched via FastAPI's `BackgroundTasks` so it does not block the API response. The user immediately receives a fallback message containing their email address and the reference ID, while the support team receives the full context email asynchronously.

### API Endpoints

**`POST /upload`** accepts `.txt`, `.pdf`, and `.md` files up to 10MB. The file is written to a temporary location, loaded via `SimpleDirectoryReader`, inserted into the PGVector index, and the temporary file is cleaned up in the `finally` block.

**`POST /query`** accepts a JSON body with `question` (string, max 2000 characters) and `user_email` (valid email address). It returns either a normal answer with source nodes or a handoff message with a reference ID.

**`GET /health`** returns service status for monitoring.

### SMTP Configuration

Email notifications are sent via SMTP with STARTTLS on port 587. The implementation uses Mailtrap sandbox for development and testing, which captures all outgoing emails in a safe inbox without delivering them to real recipients. The `APPLICATION_EMAIL` and `SUPPORT_EMAIL` variables define the sender and recipient addresses respectively and can be set to any value when using Mailtrap since delivery is simulated.

### Observability

Every query creates a Langfuse trace with faithfulness and answer relevance scores attached. The trace ID is included in the handoff context so support agents can look up the exact Langfuse trace for any escalated conversation. Scores are written to Langfuse using `langfuse.create_score()` with named score types (`faithfulness`, `answer_relevance`) enabling dashboard-level aggregation and trend analysis.