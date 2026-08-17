# Product Manual RAG System - Evaluation Against SLO

## Project Context

You're building a **Product Manual RAG System**, an AI-powered system that helps users get answers to questions about product features, installation, configuration, troubleshooting, and usage instructions.

This practice focuses on **RAG system evaluation** — implementing automated evaluation pipelines using Langfuse and LLM-as-a-judge techniques. You'll learn how to create evaluation datasets, build evaluators that measure faithfulness and answer relevance, and run comprehensive evaluation pipelines that track quality metrics and SLO compliance.

## Problem Statement

Build a RAG system with automated evaluation capabilities. The system must support document indexing, query processing, and systematic evaluation using structured datasets. You need to implement LLM-as-a-judge evaluators that measure answer quality across multiple dimensions (faithfulness, relevance) and generate comprehensive evaluation reports.

You will complete multiple implementation tasks to build this evaluated RAG system:

---

### **Task 1 — Create Evaluation Dataset**

#### Goal

Build functionality to create structured evaluation datasets in Langfuse with test questions and expected answers.

#### Requirements

1. Implement `get_langfuse_client()` to initialize Langfuse client from environment variables

2. Implement `create_dataset()` to create dataset in Langfuse with metadata

3. Implement `add_items()` to add 10 test questions (3 easy, 4 medium, 3 hard) with metadata

4. Implement `main()` to orchestrate dataset creation

**File**: `main/evaluation/dataset.py`

#### Implementation Notes

`get_langfuse_client()` reads `LANGFUSE_SECRET_KEY`, `LANGFUSE_PUBLIC_KEY`, and `LANGFUSE_HOST` from environment variables and raises a `ValueError` if either key is missing. The client is initialized with these three credentials.

`create_dataset()` calls `langfuse.create_dataset()` with the dataset name, a description, and metadata containing `sprint="C3-S09"`, `type="product_manual_qa"`, `version="1.0"`, and `knowledge_base="product_manual"`.

`add_items()` defines 10 test cases covering the CloudSync Pro user manual — 3 easy questions on basic product overview, login, and system requirements; 4 medium questions on selective sync, conflict resolution, folder sharing, and file recovery; and 3 hard questions on corporate proxy configuration, storage quota management, and version history edge cases. Each item is added to Langfuse via `langfuse.create_dataset_item()` with `input` (the question), `expected_output` (the reference answer), and `metadata` containing `category`, `difficulty`, `manual_section`, and `source`. Hard questions additionally carry an `edge_case` field in their metadata.

`main()` sets `DATASET_NAME = "product_manual"`, orchestrates client creation, dataset creation, and item addition, then prints a summary showing the dataset name and question count breakdown by difficulty.

---

### **Task 2 — Implement LLM-as-a-Judge Evaluators and Pipeline**

#### Goal

Build evaluators that use LLM-as-a-judge to score answer quality and implement the complete evaluation pipeline.

#### Requirements

1. Implement `evaluate_faithfulness_score()` using LLM-as-a-judge

2. Implement `evaluate_answer_relevance()` using LLM-as-a-judge

3. Implement `query_with_evaluation()` to execute query and run evaluators

4. Implement `run_dataset_evaluation()` to run evaluation on dataset and calculate metrics

**File**: `main/evaluation/dataset_evaluation.py`

#### Implementation Notes

`evaluate_faithfulness_score()` builds a structured judge prompt containing the question, retrieved context, and answer, with a 5-point scoring rubric from 0.0 (contradicts context) to 1.0 (fully grounded). It calls `Settings.llm.complete()` to get the LLM judgment, extracts the score by scanning for a line starting with `Score:`, clamps the result to the 0.0–1.0 range, and attaches it to Langfuse via `langfuse.create_score()` with `name="faithfulness"`. Errors are caught and return 0.0 without crashing the pipeline.

`evaluate_answer_relevance()` follows the same pattern but evaluates how directly and completely the answer addresses the question, independent of any retrieved context. The score is attached to Langfuse with `name="answer_relevance"`.

`query_with_evaluation()` generates a trace ID via `langfuse.create_trace_id()`, opens a span with `langfuse.start_observation()` bound to that trace, executes the RAG query, extracts the full text of all source nodes to build the evaluation context, then runs both evaluators concurrently with `asyncio.gather()`. The span is updated with the answer and both scores before being ended. On any exception the span is still ended cleanly and the function returns zero scores rather than raising.

`run_dataset_evaluation()` initializes RAG services, loads and indexes the product manual document, fetches the Langfuse dataset, and loops through all 10 items calling `query_with_evaluation()` for each. After all queries complete it calculates average faithfulness, average answer relevance, and SLO compliance count at a 0.7 threshold, then prints a full summary including the three lowest-scoring questions for each metric and a per-question results table.

---

### **Task 3 — Add Evaluation to Query Endpoint**

#### Goal

Integrate automatic evaluation and tracing into the API query endpoint.

#### Requirements

1. Import Langfuse client and evaluator functions

2. Extract full context from source_nodes

3. Create Langfuse span and run evaluators asynchronously

4. Update span with scores and handle errors

**File**: `main/routes/routes.py` - `query_rag()`

#### Implementation Notes

`get_langfuse_client` and both evaluator functions are imported at the top of the routes module alongside the existing service imports.

Inside `query_rag()`, after the RAG response is received, the full text of every source node is collected into `eval_context_chunks` and joined with double newlines to form `eval_context` — this is kept separate from the truncated `display_text` used in the API response so the evaluators always receive the complete context.

A Langfuse trace ID is then created via `langfuse.create_trace_id()` and a span is opened with `langfuse.start_observation()` using `name="api_query"`. Both `evaluate_faithfulness_score()` and `evaluate_answer_relevance()` are run concurrently with `asyncio.gather()`. The span is then updated with the answer and both scores and ended, followed by `langfuse.flush()` to ensure the trace is dispatched.

The entire evaluation and tracing block is wrapped in a `try/except` so any failure in Langfuse connectivity or evaluation logic logs a warning and is silently skipped — the API response is always returned regardless.

---

## Evaluation Criteria

Ensure you evaluate your solution against the below criteria:

1. **Evaluation Dataset Creation**: Langfuse dataset is created with 10 test questions (3 easy, 4 medium, 3 hard) with proper metadata (category, difficulty, manual_section) and expected outputs. Dataset items are successfully added to Langfuse using langfuse.create_dataset_item().

2. **LLM-as-a-Judge Evaluators**: Faithfulness and answer relevance evaluators are implemented with structured prompts, score extraction from LLM judgments, and Langfuse score attachment. Evaluators return scores in 0.0-1.0 range and handle errors gracefully.

3. **Evaluation Pipeline**: Complete evaluation pipeline runs queries on all dataset items, executes evaluators asynchronously, calculates aggregate metrics (average scores, SLO compliance), and displays comprehensive results. All traces and scores are logged to Langfuse.

4. **Query Endpoint Evaluation**: Query endpoint integrates automatic evaluation and tracing. Full context is extracted for evaluation, Langfuse spans are created, evaluators run asynchronously, and scores are attached to traces. Evaluation errors don't break the API.

---

## Setup and Configuration

### Environment Variables

Two `.env` files are used. The root `.env` at `Building_Agentic_AI_Systems/` holds secrets that must never be overwritten:

- `AZURE_OPENAI_API_KEY`
- `AZURE_OPENAI_ENDPOINT`
- `DB_PASSWORD`
- `LANGFUSE_SECRET_KEY`
- `LANGFUSE_PUBLIC_KEY`

The project `.env` at the assignment root holds non-secret configuration:

- `DB_USER`, `DB_HOST`, `DB_PORT`, `DB_NAME=product_manual_rag_db`, `DB_TABLE_NAME=product_manual_vectors`
- `AZURE_OPENAI_EMBEDDING_DEPLOYMENT`, `AZURE_OPENAI_LLM_DEPLOYMENT`, `AZURE_OPENAI_API_VERSION`
- `LANGFUSE_HOST=https://cloud.langfuse.com`
- `API_HOST`, `API_PORT`, `API_RELOAD`, `API_LOG_LEVEL`, `CORS_ORIGINS`

### Database Setup

Create the PostgreSQL database before first run:

```
psql -U postgres -c "CREATE DATABASE product_manual_rag_db;"
```

### Run Order

1. Create the Langfuse evaluation dataset:
   `python -m main.evaluation.dataset`

2. Start the API server:
   `python main.py`

3. Run the full evaluation pipeline:
   `python -m main.evaluation.dataset_evaluation`

---

## Evaluation Results

The evaluation pipeline was run against all 10 dataset items using the CloudSync Pro user manual as the knowledge base.

| Metric | Score |
|---|---|
| Average Faithfulness | 0.925 |
| Average Answer Relevance | 0.800 |
| SLO Threshold | 0.7 |
| SLO Compliant Items | 8/10 (80.0%) |

The two items that missed SLO were the corporate proxy/SSL configuration question (low faithfulness — the manual lacks detailed proxy config content) and the storage quota management question (low answer relevance on that evaluation run). All other questions scored at or above the 0.7 threshold on both dimensions. All traces and scores were successfully logged to Langfuse.