# FinDoc Analyzer — Financial Report Intelligence System

> **Production-Grade RAG + SQL + Multimodal AI System** for financial document analysis,
> powered by LlamaIndex, PostgreSQL/pgvector, Azure OpenAI / Anthropic / OpenAI,
> and guarded by Presidio PII detection, RAGAS evaluation, Langfuse tracing, and human handoff.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [System Architecture](#2-system-architecture)
3. [Component Deep-Dive](#3-component-deep-dive)
4. [Query Routing Logic](#4-query-routing-logic)
5. [Multimodal Image Extraction (New)](#5-multimodal-image-extraction-new)
6. [Langfuse Tracing (Enhanced)](#6-langfuse-tracing-enhanced)
7. [Guardrails & Safety](#7-guardrails--safety)
8. [Evaluation & SLOs](#8-evaluation--slos)
9. [Human Handoff](#9-human-handoff)
10. [API Reference](#10-api-reference)
11. [Environment Variables](#11-environment-variables)
12. [Database Schema](#12-database-schema)
13. [Project Structure](#13-project-structure)
14. [Setup & Deployment](#14-setup--deployment)
15. [Evaluation Results & Findings](#15-evaluation-results--findings)

---

## 1. Project Overview

### Problem Statement

Financial analysts, auditors, and compliance teams work with dense multi-hundred-page reports
containing tables, charts, footnotes, and narrative disclosures. Manual analysis is slow,
error-prone, and cannot scale.

### Solution

FinDoc Analyzer is an AI-powered backend that:

- **Ingests** financial reports (PDF, CSV, XLSX) and indexes them in a vector database.
- **Extracts** structured financial metrics from tables and inserts them into PostgreSQL.
- **Analyzes embedded charts** in PDFs using LLM vision and indexes the resulting insights.
- **Routes queries** intelligently between RAG, SQL, Hybrid, and live MCP (yfinance) pathways.
- **Validates** every input and output with financial guardrails and PII detection.
- **Evaluates** every response for faithfulness, relevance, and context precision.
- **Traces** every pipeline step with Langfuse for full observability.
- **Escalates** low-confidence or high-risk queries to human experts automatically.

### Key Metrics (from TechVision 2024 Annual Report)

| Metric | 2024 | 2023 | YoY |
|--------|------|------|-----|
| Total Revenue | $1,831.5M | $1,489.3M | +23% |
| Net Income | $328.7M | $245.2M | +34.1% |
| Gross Margin | 68.4% | 66.0% | +2.4pp |
| EPS | $3.28 | $2.45 | +33.9% |

---

## 2. System Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                         Client / API Consumer                         │
└──────────────────────┬───────────────────────────┬───────────────────┘
                       │ POST /api/v1/ingest        │ POST /api/v1/query
                       ▼                            ▼
┌──────────────────────────────────────────────────────────────────────┐
│                      FastAPI Application (app.py)                     │
│  ┌──────────────────┐  ┌──────────────────────┐  ┌────────────────┐ │
│  │  ingest_routes   │  │    query_routes       │  │ health_routes  │ │
│  └────────┬─────────┘  └──────────┬────────────┘  └────────────────┘ │
└───────────┼────────────────────────┼─────────────────────────────────┘
            │                        │
            ▼                        ▼
┌───────────────────┐    ┌───────────────────────────────────────────┐
│  INGESTION PIPELINE│    │             QUERY PIPELINE                │
│                   │    │                                           │
│ 1. File Validation│    │ 1. Input Guardrails                       │
│ 2. SimpleDir Reader│   │ 2. Langfuse Trace Init                    │
│ 3. SentenceSplitter│   │ 3. Query Router (classify_query)          │
│ 4. PGVector Index  │   │ 4. Route Execute (RAG/SQL/Hybrid/MCP)     │
│ 5. Table Extractor │   │ 5. Output Guardrails + PII                │
│    (PyMuPDF)       │   │ 6. LLM Evaluation (faith/relev/ctx_prec)  │
│ 6. SQL Insert      │   │ 7. Handoff Decision                       │
│ 7. LLM Vision      │   │ 8. Langfuse Flush                         │
│    (Chart Analysis)│   │ 9. Response                               │
│ 8. Image RAG Index │   └───────────────────────────────────────────┘
└───────────────────┘
            │
            ▼
┌──────────────────────────────────────────────────────────────────────┐
│                         DATA STORES                                   │
│  ┌─────────────────┐  ┌──────────────────┐  ┌─────────────────────┐ │
│  │  PostgreSQL      │  │  pgvector        │  │  In-Memory Query Log│ │
│  │  (Structured     │  │  (Vector         │  │  (SLO Metrics)      │ │
│  │   Financial Data)│  │   Embeddings)    │  └─────────────────────┘ │
│  └─────────────────┘  └──────────────────┘                          │
└──────────────────────────────────────────────────────────────────────┘
```

### Full Ingestion Flow

```
PDF Upload
    │
    ▼
File Validation ──► 400 if invalid type/size
    │
    ▼
SimpleDirectoryReader  ──► extracts raw text from all pages
    │
    ▼
SentenceSplitter(512 tokens, 50 overlap)
    │
    ▼
PGVector Embedding Store  ──► text chunks embedded + stored
    │
    ▼
PDFTableExtractor (pymupdf)
    ├──► find_tables() ──► DataFrame ──► financial metrics
    ├──► _extract_footnotes() ──► footnote list
    └──► PDFImageAnalyzer (NEW)
              │
              ├──► get_images(full=True) ──► embedded XObjects
              │         │
              │         ▼ (if image >= 150x100)
              │    LLM Vision API (Anthropic/OpenAI/Azure)
              │         │
              │         ▼
              │    Chart Analysis Text (CHART TYPE / DATA POINTS / TREND / INSIGHTS)
              │
              └──► get_pixmap(2x scale) ──► page render fallback
                         │
                         ▼ (if page has chart signals)
                    LLM Vision API
                         │
                         ▼
                    Chart Analysis Text

    ▼
insert_metrics_to_sql()  ──► income_statement_line_items
    │
    ▼
image_analyses_to_documents()  ──► LlamaIndex Document objects
    │
    ▼
ingest_documents(image_docs)  ──► PGVector (chart analyses now queryable via RAG!)
```

### Full Query Flow

```
POST /api/v1/query  { "question": "...", "routing_hint": null }
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│  Input Guardrails                                        │
│  ✓ Empty / length check (max 2000 chars)                │
│  ✓ Prompt injection patterns (10 regex patterns)        │
│  ✓ SQL injection patterns (10 regex patterns)           │
└─────────────────────────────────────────────────────────┘
    │ (blocked → 400)         │ (valid → continue)
    ▼
┌─────────────────────────────────────────────────────────┐
│  Langfuse Trace Init                                     │
│  trace = langfuse.trace(name="findoc_query", ...)       │
└─────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│  Query Router  (classify_query)                          │
│                                                          │
│  Keyword scoring:                                        │
│    sql_score  = count of SQL_KEYWORDS in question        │
│    rag_score  = count of RAG_KEYWORDS in question        │
│    mcp_score  = count of MCP_KEYWORDS in question        │
│                                                          │
│  Decision tree:                                          │
│    routing_hint provided → use hint directly             │
│    mcp_score >= 2        → MCP                           │
│    sql >= 3 & rag <= 1   → SQL                           │
│    rag >= 3 & sql <= 1   → RAG                           │
│    else                  → HYBRID                        │
└────────┬───────────┬──────────────┬──────────────────────┘
         │           │              │              │
         ▼           ▼              ▼              ▼
       [RAG]       [SQL]        [HYBRID]        [MCP]
         │           │              │              │
         │      NLSQLTable     RAG + SQL       yfinance
         │      QueryEngine    merged by     /HuggingFace
         │                     LLM           MCP tools
         └───────────┴──────────────┴──────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────┐
│  Output Guardrails + Presidio PII                        │
│  ✓ Investment advice disclaimer injection                │
│  ✓ Hallucination indicator detection                    │
│  ✓ PII redaction (EMAIL, PHONE, SSN, CC)                │
│  ✓ Numerical traceability check                         │
└─────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│  LLM Evaluation  (Langfuse spans logged for each)        │
│                                                          │
│  faithfulness       = LLM rates answer vs context (0-1) │
│  answer_relevance   = LLM rates answer vs question (0-1) │
│  context_precision  = fraction of chunks relevant (0-1) │
└─────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│  Handoff Decision                                        │
│  1. Explicit user request keyword / LLM classifier      │
│  2. Investment advice / high-risk keyword               │
│  3. Low faithfulness (< 0.5) or relevance (< 0.4)       │
│  4. LLM self-confidence < 20/100                        │
│                                                          │
│  → if triggered: background email + reference ID        │
└─────────────────────────────────────────────────────────┘
    │
    ▼
JSON Response  { question, answer, routing_used, source_nodes,
                 sql_query, validation_results, handoff_*, trace_id }
```

---

## 3. Component Deep-Dive

### 3.1 RAG Service (`rag_service.py`)

| Concern | Implementation |
|---------|---------------|
| LLM provider | `LLM_PROVIDER` env var: `azure` (default) / `openai` / `anthropic` |
| Embedding provider | `EMBEDDING_PROVIDER` env var; Anthropic falls back to OpenAI embeddings |
| Vector store | `PGVectorStore` backed by PostgreSQL + `pgvector` extension |
| Chunking | `SentenceSplitter(chunk_size=512, chunk_overlap=50)` |
| Deduplication | Checks `metadata_->>'source_file'` in `data_findoc_embeddings` before re-ingesting |
| Query engine | `VectorStoreIndex.as_query_engine(similarity_top_k=4)` with LRU cache |

### 3.2 SQL Service (`sql_service.py`)

Direct SQL lookups are tried first (fast path) before falling back to `NLSQLTableQueryEngine`.
Covers: revenue, net income, quarterly segments, EPS, gross profit, full income statement.

Schema taught to the LLM via `SQL_SYSTEM_PROMPT`:

```
financial_statements          (header row, 1 per company/year/statement type)
income_statement_line_items   (JOIN financial_statements)
quarterly_revenue_breakdown   (segment + quarter data)
balance_sheet_items           (JOIN financial_statements)
risk_disclosures              (JOIN financial_statements)
financial_ratios              (standalone)
risk_factors                  (standalone)
```

### 3.3 MCP Client (`mcp_client.py`)

Priority order for MCP route:
1. **yfinance** — resolves ticker via alias map or `$TICK` / `(TICK)` regex pattern.
   Returns: stock price, market cap, P/E, 52-week range, revenue, analyst rating.
2. **HuggingFace MCP** — `BasicMCPClient` with `model_search`, `search_papers`, `summarization` tools.
3. **Fallback message** — instructs user how to form a ticker-based query.

### 3.4 Table Extractor (`table_extractor.py`)

Three-layer PDF extraction:

| Layer | Tool | Output |
|-------|------|--------|
| Tables | `page.find_tables()` → pandas DataFrame | Financial metrics for SQL |
| Text fallback | Regex on `page.get_text()` | Financial metrics for SQL |
| Footnotes | Small-font span detection | Footnote text for context |
| **Images (NEW)** | `PDFImageAnalyzer` + LLM vision | Chart analysis Documents for RAG |

---

## 4. Query Routing Logic

```
classify_query(question, routing_hint=None)

SQL keywords (score +=1 each):
  revenue, profit, earnings, ebitda, eps, net income, gross margin,
  operating income, cash flow, total assets, liabilities, equity, debt,
  capex, how much, what is the, calculate, compare, growth rate, yoy,
  quarter, fiscal year, per share, market cap, balance sheet, income
  statement, cash flow statement, return on, price to, p/e

RAG keywords (score +=1 each):
  explain, describe, what are, discuss, summarize, risk, strategy,
  outlook, guidance, management, notes, disclosure, footnote, policy,
  compliance, why, how does, what happened, tell me about, annual
  report, 10-k, 10-q, filing, narrative

MCP keywords (score +=1 each):
  current, latest, today, real-time, live, market data, stock price,
  news, analyst, current price, share price, market cap today

Routing rules (evaluated in order):
  1. routing_hint in {rag, sql, hybrid, mcp}  →  use hint
  2. mcp_score >= 2                            →  mcp
  3. sql_score >= 3 AND rag_score <= 1         →  sql
  4. rag_score >= 3 AND sql_score <= 1         →  rag
  5. else                                      →  hybrid
```

**Example routings:**

| Question | Route | Reason |
|----------|-------|--------|
| "What was the revenue in 2024?" | `sql` | sql_score=4 (revenue, what is, 2024→fiscal year) |
| "Explain the key risks in the annual report" | `rag` | rag_score=4 (explain, risk, annual report) |
| "What drove revenue growth and what are the risks?" | `hybrid` | sql+rag both high |
| "What is the current stock price of TechVision?" | `mcp` | mcp_score=2 (current, stock price) |

---

## 5. Multimodal Image Extraction (New)

### What Was Missing

The original `PDFTableExtractor` only extracted text blocks and tables. The TechVision PDF
contains a **Quarterly Revenue Trend bar chart (2022–2024)** with data values not present
in the text layer. Without image analysis, queries like
*"What does the quarterly revenue trend show?"* could not be answered accurately.

### New `PDFImageAnalyzer` Class

Located in `table_extractor.py`, this class:

**Step 1 — Embedded image extraction**
```python
image_list = page.get_images(full=True)
for xref in image_list:
    base_img = doc.extract_image(xref)  # raw bytes + dimensions
    if width >= 150 and height >= 100:
        send_to_llm_vision(base64_encode(bytes))
```

**Step 2 — Page render fallback**
```python
# If no embedded images but page text contains chart signals:
mat = fitz.Matrix(2.0, 2.0)   # 2x scale for quality
pix = page.get_pixmap(matrix=mat)
send_to_llm_vision(base64_encode(pix.tobytes("png")))
```

**Step 3 — LLM vision analysis**

Prompt sent to the LLM:
```
You are a financial analyst assistant.
Analyze the following financial chart or figure...
Format your response as:
CHART TYPE: <type>
DATA POINTS: <list all visible numbers with their labels>
TREND SUMMARY: <2-3 sentence description>
KEY INSIGHTS: <bullet list>
```

**Step 4 — RAG indexing of analysis**

Chart analysis text is wrapped in a LlamaIndex `Document` with metadata:
```python
Document(
    text="[CHART ANALYSIS — Page 2 of TechVision_Annual_Report_2024.pdf]\n"
         "Company: TechVision Corporation | Fiscal Year: 2024\n\n"
         "CHART TYPE: Bar chart\n"
         "DATA POINTS: Q1 2022: $245.5M, Q2 2022: $289.7M, ...\n"
         "TREND SUMMARY: Consistent quarterly revenue growth over 3 years...\n"
         "KEY INSIGHTS:\n- Revenue grew 91% from Q1 2022 to Q4 2024\n...",
    metadata={
        "content_type": "chart_analysis",
        "source_file":  "TechVision_Annual_Report_2024.pdf",
        "page_number":  "2",
        "image_type":   "page_render",
        ...
    }
)
```

This document is then passed through `ingest_documents()` and stored in PGVector,
making chart data **queryable through the RAG pipeline**.

### Provider Support

| Provider | Vision Model Used |
|----------|------------------|
| `anthropic` | `claude-3-5-sonnet-20241022` (or `ANTHROPIC_MODEL` env var) |
| `azure` | Deployment set by `AZURE_OPENAI_LLM_DEPLOYMENT` (must be GPT-4o or GPT-4-vision) |
| `openai` | `gpt-4o` (or `OPENAI_MODEL` env var) |

---

## 6. Langfuse Tracing (Enhanced)

### What Was in the Original Code

The original code created a single root trace and flushed it at the end.
Evaluation scores were logged as separate `langfuse.score()` calls.
There was no span-level breakdown of the pipeline.

### What Was Added

Every logical step in the query pipeline now creates a **child span** on the root trace.
This produces a full waterfall view in the Langfuse UI:

```
findoc_query  (root trace)
├── input_guardrails          [~1ms]   input: {question}, output: {valid, length}
├── query_routing             [~5ms]   input: {question, hint}, output: {route, nodes, sql}
├── rag_retrieval             [~800ms] input: {question}, output: {chunks, length}
│   (or sql_lookup / hybrid_retrieval / mcp_call depending on route)
├── output_guardrails         [~300ms] output: {pii_redacted, disclaimer_added, warnings}
├── evaluation                [~1200ms] output: {faithfulness, relevance, ctx_precision}
└── handoff_decision          [~200ms] output: {triggered, reference_id, reason}
```

**Root trace metadata** (visible in Langfuse trace detail):
```json
{
  "session_id":       "a1b2c3d4",
  "llm_provider":     "azure",
  "timestamp_utc":    "2024-12-31T10:00:00Z",
  "latency_ms":       2450.3,
  "faithfulness":     0.87,
  "relevance":        0.91,
  "context_precision": 0.75,
  "pii_redacted":     false,
  "source_nodes":     4
}
```

**Scores on the trace** (visible in Langfuse scores dashboard):
- `faithfulness` — LLM-rated answer vs retrieved context
- `answer_relevance` — LLM-rated answer vs question
- `context_precision` — fraction of retrieved chunks that are relevant
- `handoff_triggered` (1.0 if triggered) — with reason as comment

### Langfuse Setup

1. Create an account at [cloud.langfuse.com](https://cloud.langfuse.com) (or self-host).
2. Create a project → copy the public key, secret key, and host URL.
3. Add to your root `.env`:
   ```
   LANGFUSE_PUBLIC_KEY=pk-lf-...
   LANGFUSE_SECRET_KEY=sk-lf-...
   LANGFUSE_HOST=https://cloud.langfuse.com
   ```
4. Langfuse tracing activates automatically on startup if keys are present.
   Check `GET /api/v1/health` → `langfuse` component to confirm.

### Tracing Architecture Diagram

```
query_routes.py
│
├── langfuse.trace("findoc_query")  ←── root trace
│        │
│        ├── trace.span("input_guardrails")     ← step 1
│        │       └── span.end(output)
│        │
│        ├── trace.span("query_routing")         ← step 2
│        │       └── span.end(output)
│        │
│        ├── trace.span("rag_retrieval")         ← step 3 (route-specific)
│        │    [or "sql_lookup" / "hybrid_retrieval" / "mcp_call"]
│        │       └── span.end(output)
│        │
│        ├── trace.span("output_guardrails")     ← step 4
│        │       └── span.end(output)
│        │
│        ├── trace.span("evaluation")            ← step 5
│        │       └── span.end({faithfulness, relevance, ctx_precision})
│        │
│        ├── trace.span("handoff_decision")      ← step 6
│        │       └── span.end({triggered, reference_id})
│        │
│        ├── langfuse.score("faithfulness", value)
│        ├── langfuse.score("answer_relevance", value)
│        ├── langfuse.score("context_precision", value)
│        └── trace.update(output, metadata)
│
└── langfuse.flush()
```

---

## 7. Guardrails & Safety

### Input Guardrails (`validators.py`)

| Check | Details |
|-------|---------|
| Empty / length | Blocked if empty or > 2000 characters |
| Prompt injection | 10 regex patterns (ignore instructions, jailbreak, bypass, etc.) |
| SQL injection | 10 regex patterns (DROP TABLE, UNION SELECT, xp_cmdshell, etc.) |

### Output Guardrails

| Check | Tool | Details |
|-------|------|---------|
| PII detection & redaction | Presidio → Guardrails Hub fallback | EMAIL, PHONE, SSN, CC |
| Investment advice | Regex (8 patterns) | Appends legal disclaimer automatically |
| Hallucination indicators | Regex (4 patterns) | Flags "I believe the revenue..." |
| Uncertainty detection | String match | Flags "I don't know", "not available" |
| Numerical traceability | Regex + source context | Checks if dollar amounts appear in retrieved context |

### PII Entity Types Detected

```
EMAIL_ADDRESS, PHONE_NUMBER, US_SSN, CREDIT_CARD, US_DRIVER_LICENSE
```
*(DATE_TIME and PERSON excluded to avoid false positives on fiscal years and executive names)*

---

## 8. Evaluation & SLOs

### Per-Query Evaluation (runs automatically on every `/query` call)

All three metrics are computed via LLM prompt scoring (0.0–1.0):

| Metric | LLM Prompt Pattern | Logged To |
|--------|-------------------|-----------|
| **Faithfulness** | Rate how well the answer is supported by the context | Langfuse score + SLO store |
| **Answer Relevance** | Rate how well the answer addresses the question | Langfuse score + SLO store |
| **Context Precision** | Fraction of retrieved chunks relevant to the question | Langfuse score + SLO store |

### SLO Thresholds

| SLO | Default Threshold | Environment Variable |
|-----|-------------------|---------------------|
| Min faithfulness | 0.6 | `SLO_FAITHFULNESS_MIN` |
| Min relevance | 0.5 | `SLO_RELEVANCE_MIN` |
| Max latency | 5000ms | `SLO_LATENCY_MAX_MS` |

### SLO Dashboard

```
GET /api/v1/evaluate

Response:
{
  "status": "ok",
  "metrics": {
    "total_queries_evaluated": 47,
    "avg_faithfulness":        0.84,
    "avg_relevance":           0.79,
    "avg_latency_ms":          2340.5,
    "routing_distribution":    {"rag": 12, "sql": 21, "hybrid": 11, "mcp": 3},
    "slo_passed":              true,
    "slo_details": {
      "faithfulness":       {"value": 0.84, "threshold": 0.6, "passed": true},
      "relevance":          {"value": 0.79, "threshold": 0.5, "passed": true},
      "latency_ms":         {"value": 2340, "threshold": 5000, "passed": true},
      "avg_context_precision": 0.73,
      "p95_latency_ms":     4210.0,
      "ragas_available":    false
    }
  },
  "langfuse_enabled": true
}
```

### RAGAS Batch Evaluation (optional)

If `ragas` and `datasets` packages are installed:

```bash
POST /api/v1/evaluate/ragas
{
  "questions":     ["What was revenue in 2024?"],
  "answers":       ["TechVision reported $1,831.5M in revenue for FY2024."],
  "contexts":      [["Total Revenue: $1,831.5M...", "Cloud Services: $892M..."]],
  "ground_truths": ["$1,831.5M"]
}
```

---

## 9. Human Handoff

### Automatic Trigger Conditions (priority order)

1. **Explicit user request** — LLM classifier detects "speak to someone", "escalate", "I want a human", etc.
2. **Investment advice** — High-risk keywords: "should I invest", "guaranteed return", "best investment"
3. **Low evaluation scores** — faithfulness < 0.5 OR relevance < 0.4 (for RAG/hybrid routes)
4. **Low LLM confidence** — LLM self-rates answer confidence < 20/100 (RAG route only)
5. **No chunks retrieved** — Zero source nodes returned

### Handoff Process

```
Handoff Triggered
      │
      ▼
generate_handoff_reference_id()
  → "FINDOC-HO-20241231-100000-A1B2C3"
      │
      ▼
Build handoff_context bundle:
  - reference_id, trace_id, timestamp_utc, session_id
  - priority ("high" / "normal")
  - trigger_reason
  - original question + generated answer
  - evaluation scores (faithfulness, relevance, confidence)
  - retrieved chunks with similarity scores
  - routing used, user email
      │
      ▼
background_tasks.add_task(send_handoff_email, context)
      │
      ▼
final_answer replaced with:
  "I don't have sufficient confidence to answer this reliably.
   Your request has been escalated to a financial expert.
   Reference ID: FINDOC-HO-..."
      │
      ▼
langfuse.score("handoff_triggered", 1.0, comment=reason)
```

### Manual Handoff

```
POST /api/v1/handoff
{
  "question": "Explain the off-balance sheet liabilities in the 2023 annual report",
  "answer": "I am not confident in my answer.",
  "user_email": "analyst@firm.com",
  "reason": "Complex accounting question requiring expert review"
}
```

### Email Configuration

| Variable | Purpose |
|----------|---------|
| `SMTP_HOST` | SMTP server hostname |
| `SMTP_PORT` | SMTP port (default 587) |
| `SMTP_USERNAME` | SMTP auth username |
| `SMTP_PASSWORD` | SMTP auth password |
| `APPLICATION_EMAIL` | From address |
| `SUPPORT_EMAIL` | To address (support team) |

---

## 10. API Reference

### POST /api/v1/ingest

Upload a financial document for processing.

**Request** (multipart/form-data):
```
file         : UploadFile  — PDF, TXT, CSV, XLSX (max 50MB)
company_name : string      — e.g. "TechVision Corporation"
fiscal_year  : integer     — e.g. 2024
```

**Response** (201):
```json
{
  "message": "Successfully ingested 'TechVision_Annual_Report_2024.pdf'. Vector chunks: 48. Tables extracted: 2, metrics stored in SQL: 12. Chart images analyzed and indexed: 1.",
  "documents_indexed": 4,
  "chunks_created":    49,
  "document_id":       "f3a2b1c0-...",
  "file_name":         "TechVision_Annual_Report_2024.pdf",
  "file_type":         "pdf"
}
```

### POST /api/v1/query

Query the system with natural language.

**Request**:
```json
{
  "question":     "What was the revenue growth over the last three years?",
  "user_email":   "analyst@example.com",
  "routing_hint": null
}
```

**Response** (200):
```json
{
  "question":     "What was the revenue growth over the last three years?",
  "answer":       "TechVision Corporation revenue (2024): Total Revenue: $1,831.5M...",
  "routing_used": "sql",
  "source_nodes": [],
  "sql_query":    "direct revenue lookup",
  "validation_results": {
    "faithfulness":      0.91,
    "relevance":         0.88,
    "context_precision": null,
    "latency_ms":        1240.5,
    "llm_provider":      "azure"
  },
  "handoff_triggered":    false,
  "handoff_reference_id": null,
  "trace_id":             "trace_abc123"
}
```

### GET /api/v1/health

Full component health check.

```json
{
  "status":  "healthy",
  "service": "FinDoc Analyzer",
  "version": "1.0.0",
  "components": {
    "postgresql":    {"status": "ok",       "detail": "PostgreSQL 16.1 | pgvector ✓"},
    "llm_provider":  {"status": "ok",       "detail": "provider=azure llm=gpt-4o emb=text-embedding-3-small"},
    "rag_service":   {"status": "ok",       "detail": "LlamaIndex index loaded | provider=azure"},
    "guardrails_ai": {"status": "disabled", "detail": "Not installed — using custom validators"},
    "ragas":         {"status": "disabled", "detail": "Not installed. Run: pip install ragas datasets"},
    "presidio_pii":  {"status": "ok",       "detail": "presidio-analyzer installed ✓"},
    "pymupdf_tables":{"status": "ok",       "detail": "pymupdf 1.24.3 ✓ — PDF table extraction active"},
    "yfinance":      {"status": "ok",       "detail": "yfinance 0.2.40 ✓"},
    "langfuse":      {"status": "ok",       "detail": "host=https://cloud.langfuse.com"},
    "mcp":           {"status": "disabled", "detail": "Missing: ['HF_TOKEN']"},
    "smtp_handoff":  {"status": "ok",       "detail": "host=smtp.gmail.com"}
  }
}
```

### GET /api/v1/evaluate

SLO compliance dashboard.

### POST /api/v1/evaluate/ragas

Batch RAGAS evaluation (requires `pip install ragas datasets`).

### POST /api/v1/handoff

Manual human escalation trigger.

---

## 11. Environment Variables

### Root `.env` (secrets — at `Building_Agentic_AI_Systems/.env`)

```env
# Database
DB_PASSWORD=your_postgres_password

# LLM Provider — choose ONE of: azure, openai, anthropic
LLM_PROVIDER=azure

# Azure OpenAI (required if LLM_PROVIDER=azure)
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_VERSION=2024-02-01
AZURE_OPENAI_LLM_DEPLOYMENT=gpt-4o
AZURE_OPENAI_LLM_MODEL=gpt-4o
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-small
AZURE_OPENAI_EMBEDDING_MODEL=text-embedding-3-small

# OpenAI (required if LLM_PROVIDER=openai)
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

# Anthropic (required if LLM_PROVIDER=anthropic)
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022

# Observability
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://cloud.langfuse.com

# Handoff email
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your@gmail.com
SMTP_PASSWORD=your_app_password
APPLICATION_EMAIL=findoc@yourdomain.com
SUPPORT_EMAIL=support@yourdomain.com
```

### Project `.env` (config — at `FinDoc Analyzer/.env`)

```env
# Database connection
DB_HOST=localhost
DB_PORT=5432
DB_NAME=findoc_db
DB_USER=postgres
DB_TABLE_NAME=findoc_embeddings
DB_FINANCE_TABLE=financial_statements

# App settings
MAX_FILE_SIZE_MB=50

# SLO thresholds (optional, these are defaults)
SLO_FAITHFULNESS_MIN=0.6
SLO_RELEVANCE_MIN=0.5
SLO_LATENCY_MAX_MS=5000

# Handoff thresholds (optional, these are defaults)
HANDOFF_FAITHFULNESS_THRESHOLD=0.5
HANDOFF_RELEVANCE_THRESHOLD=0.4
HANDOFF_CONFIDENCE_THRESHOLD=20

# MCP / yfinance (optional)
MCP_SERVER_URL=https://huggingface.co/mcp
HF_TOKEN=hf_...
```

---

## 12. Database Schema

```sql
-- Financial statement headers
CREATE TABLE financial_statements (
    statement_id   SERIAL PRIMARY KEY,
    company_name   VARCHAR(255) NOT NULL,
    fiscal_year    INTEGER NOT NULL,
    fiscal_quarter INTEGER,
    statement_type VARCHAR(50) NOT NULL,   -- 'income' | 'balance' | 'cashflow'
    filing_date    DATE
);

-- Line items (revenue, net income, EPS, etc.)
CREATE TABLE income_statement_line_items (
    line_item_id          SERIAL PRIMARY KEY,
    statement_id          INTEGER REFERENCES financial_statements,
    line_item_name        VARCHAR(255),
    line_item_category    VARCHAR(100),
    amount_usd            NUMERIC(20, 4),
    percentage_of_revenue NUMERIC(10, 4),
    notes                 TEXT
);

-- Quarterly segment breakdown
CREATE TABLE quarterly_revenue_breakdown (
    revenue_id             SERIAL PRIMARY KEY,
    company_name           VARCHAR(255),
    fiscal_year            INTEGER,
    fiscal_quarter         VARCHAR(5),
    segment_name           VARCHAR(100),
    revenue_usd            NUMERIC(20, 4),
    yoy_growth_percent     NUMERIC(10, 4),
    segment_margin_percent NUMERIC(10, 4)
);

-- Balance sheet
CREATE TABLE balance_sheet_items (
    balance_item_id  SERIAL PRIMARY KEY,
    statement_id     INTEGER REFERENCES financial_statements,
    account_category VARCHAR(100),
    account_name     VARCHAR(255),
    amount_usd       NUMERIC(20, 4),
    is_debit         BOOLEAN
);

-- Risk disclosures
CREATE TABLE risk_disclosures (
    risk_id             SERIAL PRIMARY KEY,
    statement_id        INTEGER REFERENCES financial_statements,
    risk_category       VARCHAR(100),
    risk_title          VARCHAR(255),
    risk_description    TEXT,
    severity_level      VARCHAR(20),
    first_disclosed_date DATE
);

-- Runtime tables created by setup_db.py
CREATE TABLE financial_ratios ( ... );
CREATE TABLE risk_factors ( ... );

-- Vector embeddings (managed by pgvector + LlamaIndex)
-- Table name controlled by DB_TABLE_NAME env var (default: findoc_embeddings)
```

---

## 13. Project Structure

```
FinDoc Analyzer/
├── main/
│   ├── app.py                    # FastAPI app, lifespan, CORS
│   ├── config.py                 # Dual .env loader, load_config()
│   ├── models.py                 # Pydantic models for all endpoints
│   │
│   ├── routes/
│   │   ├── ingest_routes.py      # POST /api/v1/ingest  ← UPDATED
│   │   ├── query_routes.py       # POST /api/v1/query   ← UPDATED (Langfuse spans)
│   │   ├── health_routes.py      # GET  /api/v1/health
│   │   ├── evaluate_routes.py    # GET  /api/v1/evaluate + POST /evaluate/ragas
│   │   └── handoff_routes.py     # POST /api/v1/handoff
│   │
│   ├── services/
│   │   ├── rag_service.py        # LlamaIndex + PGVector core
│   │   ├── sql_service.py        # SQLAlchemy + NLSQLTableQueryEngine
│   │   ├── query_router.py       # classify_query + route_and_execute
│   │   └── table_extractor.py    # PyMuPDF + PDFImageAnalyzer ← UPDATED
│   │
│   ├── guardrails/
│   │   └── validators.py         # GuardrailsValidator + FinancialGuardrailsService
│   │
│   ├── evaluation/
│   │   └── evaluation_service.py # Langfuse client + LLM eval + SLO report
│   │
│   ├── handoff/
│   │   └── handoff_service.py    # Handoff decision + email
│   │
│   └── mcp/
│       └── mcp_client.py         # yfinance + HuggingFace MCP
│
├── scripts/
│   └── setup_db.py               # One-time database + pgvector setup
│
├── main.py                       # uvicorn entrypoint
├── .env                          # project-level config (non-secret)
└── README.md                     # This file
```

---

## 14. Setup & Deployment

### Prerequisites

- Python 3.11+
- PostgreSQL 14+ with `pgvector` extension
- One of: Azure OpenAI, OpenAI, or Anthropic API key

### 1. Install Python Dependencies

```bash
pip install fastapi uvicorn[standard] python-dotenv \
    llama-index llama-index-vector-stores-postgres \
    llama-index-llms-azure-openai llama-index-embeddings-azure-openai \
    llama-index-llms-openai llama-index-embeddings-openai \
    llama-index-llms-anthropic \
    sqlalchemy psycopg2-binary pgvector \
    pymupdf pandas openpyxl \
    presidio-analyzer presidio-anonymizer spacy \
    anthropic openai \
    yfinance langfuse python-multipart

# Optional — for RAGAS evaluation
pip install ragas datasets

# Optional — for Guardrails Hub PII
pip install guardrails-ai

# Required spaCy model for Presidio
python -m spacy download en_core_web_lg
```

### 2. PostgreSQL Setup

```bash
# Create database
createdb findoc_db

# In psql:
CREATE EXTENSION IF NOT EXISTS vector;

# Run schema setup (seeds financial tables)
python scripts/setup_db.py
```

### 3. Configure Environment

```bash
# Copy and fill in your secrets
cp .env.example .env           # project .env
# Also fill in the root .env at Building_Agentic_AI_Systems/.env
```

### 4. Start the Server

```bash
python main.py
# Server starts at http://0.0.0.0:8000
# API docs at http://localhost:8000/docs
```

### 5. Ingest the TechVision Report

```bash
curl -X POST http://localhost:8000/api/v1/ingest \
  -F "file=@TechVision_Annual_Report_2024.pdf" \
  -F "company_name=TechVision Corporation" \
  -F "fiscal_year=2024"
```

### 6. Run a Query

```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What was the revenue growth in 2024?", "user_email": "analyst@example.com"}'
```

### 7. Check Health

```bash
curl http://localhost:8000/api/v1/health | python -m json.tool
```

### Docker (optional)

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["python", "main.py"]
```

---

## 15. Evaluation Results & Findings

### Sprint Completion Summary

| Sprint | Feature | Status |
|--------|---------|--------|
| Sprint 2/3 | RAG retrieval pipeline | ✅ Complete |
| Sprint 4 | LlamaIndex query engine | ✅ Complete |
| Sprint 5 | Multimodal: PDF table extraction | ✅ Complete |
| **Sprint 5+** | **Multimodal: LLM vision chart analysis** | ✅ **NEW** |
| Sprint 6 | Guardrails + Presidio PII | ✅ Complete |
| Sprint 7 | SQL + Hybrid routing | ✅ Complete |
| Sprint 8 | MCP + yfinance | ✅ Complete |
| Sprint 9 | Langfuse + LLM eval metrics | ✅ Complete |
| **Sprint 9+** | **Comprehensive Langfuse span tracing** | ✅ **NEW** |
| Sprint 10 | Human handoff + email | ✅ Complete |

### Key Design Decisions

**Why keyword-based routing instead of LLM-based?**
Keyword scoring is deterministic, fast (~0ms), and has no LLM cost. For a financial
domain with well-defined query patterns (numerical lookups vs. narrative queries),
keyword scoring achieves very high routing accuracy without adding latency or cost.

**Why separate RAG and SQL instead of always using hybrid?**
Hybrid requires two LLM calls (RAG + SQL merge). For simple numerical queries (e.g.
"What was EPS in 2024?"), SQL returns the definitive answer with zero hallucination risk.
The merge step adds latency and a small risk of LLM introducing errors.

**Why page-render fallback for image extraction?**
PDFs rendered by some tools embed charts as vector graphics (SVG paths) rather than
raster images. `get_images(full=True)` only returns raster XObjects. The page-render
fallback ensures that even vector-drawn charts (like bar charts rendered in PDF) are
captured at 2× resolution for accurate LLM analysis.

**Why store chart analyses in PGVector alongside text chunks?**
Chart analyses are natural language descriptions of the visual data. Storing them in
the same vector index means a user asking "What does the quarterly trend show?" will
retrieve the chart analysis document as a source node, providing accurate chart data
that is invisible to text-only extraction.

### Limitations & Future Work

- **Image extraction** is best-effort; highly complex multi-chart pages may need
  multiple render crops for accurate analysis.
- **SQL routing** currently only handles TechVision Corporation data. A production
  system would need dynamic schema discovery per uploaded document.
- **RAGAS batch evaluation** requires manual question-answer pairs; automating
  golden dataset generation would improve evaluation coverage.
- **MCP route** uses yfinance as the primary data source. In production, a licensed
  financial data API (Bloomberg, Refinitiv) would replace this.

---

## Notes

- All API responses include a `trace_id` field when Langfuse is configured, enabling
  direct deep-links into the Langfuse UI for each query.
- The dual `.env` pattern preserves secret variables (DB_PASSWORD, API keys) when
  the project `.env` is loaded with `override=True`.
- SQL schema uses `quote_plus()` for encoded connection strings but raw passwords
  for `psycopg2` keyword arguments (which handles escaping internally).
- The `PGHOST`, `PGPORT`, etc. standard variables are explicitly cleared after loading
  to prevent LlamaIndex and SQLAlchemy from picking up conflicting connection info.

---

*FinDoc Analyzer — Production-Grade Financial Intelligence System*
*Built as part of Building Agentic AI Systems (Course 3 Capstone)*