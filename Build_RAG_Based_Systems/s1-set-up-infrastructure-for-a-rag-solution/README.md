## Project Context

You're building **Smart Auto Advisor**, an AI-powered conversational assistant for car manufacturers that helps customers get instant answers about vehicle models, features, pricing, and availability.

This practice focuses on the **foundation layer** — setting up the vector database infrastructure and understanding how embeddings work. You'll learn how to convert text into vector embeddings, store them in PostgreSQL with PgVector, and perform semantic similarity searches.

## Problem Statement

Establish the foundational understanding of how text is converted into vector embeddings, how to store and retrieve embeddings efficiently, and how semantic similarity search works. Without a proper vector database infrastructure, you can't build a functional RAG system that retrieves relevant information from knowledge bases.

You will complete three tasks to build this foundation:

---

### **Task 1 — Setup PostgreSQL with PgVector Extension**

#### Goal

Prepare a PostgreSQL database with vector search capabilities.

#### Requirements

1. Install PostgreSQL on your system
2. Enable the PgVector extension

---

### **Task 2 — Generate and Store Embeddings**

#### Goal

Create vector embeddings for sample automotive text(sample_data.py) and store them in the database using(embedding_setup.py).

#### Requirements

1. Configure Azure OpenAI credentials in `.env`
2. Initialize Azure OpenAI embeddings (1536 dimensions using text-embedding-3-small)
3. Generate embeddings for sample automotive text
4. Create a PGVector vectorstore connection
5. Store embeddings in PostgreSQL database with metadata

---

### **Task 3 — Complete Pipeline and REST API**

#### Goal

Build a complete infrastructure setup with REST API endpoints for document upload and querying.

#### Requirements

1. Create pipeline orchestration service:

   - Coordinate embedding generation and storage
   - Handle CRUD operations (Create, Read)
   - Provide error handling and logging

2. Implement REST API endpoints:

   - Document upload endpoint
   - Query endpoint for similarity search

3. Run and Test the Application

---

# Evaluation Criteria

Ensure you evaluate your solution against the below criteria:

1. PostgreSQL database is properly configured with PgVector extension enabled
2. Azure OpenAI embeddings are correctly initialized and configured (text-embedding-3-small, 1536 dimensions)
3. Embeddings are properly generated and stored in PostgreSQL database with pgVector
4. The pipeline performs basic semantic query operations successfully

---

# Implementation

## Project Structure

```
├── main/
│   ├── __init__.py
│   ├── app.py                  # FastAPI application and middleware setup
│   ├── config.py               # Configuration loading and logging setup
│   ├── embedding_setup.py      # End-to-end pipeline: DB check, embeddings, CRUD, search
│   ├── sample_data.py          # Sample automotive documents and sentences
│   ├── routes/
│   │   └── routes.py           # REST API endpoint definitions and Pydantic models
│   └── services/
│       └── vectorstore_service.py  # VectorstoreService class (singleton)
├── tests/
│   ├── __init__.py
│   ├── conftest.py             # Shared pytest fixtures
│   ├── test_config.py          # Tests for configuration and logging
│   ├── test_embedding_setup.py # Tests for all pipeline functions
│   └── test_sample_data.py     # Tests for sample data constants
├── main.py                     # Application entry point (uvicorn)
├── pyproject.toml              # Project dependencies and tooling config
├── uv.lock                     # Locked dependency versions
├── .env                        # Environment variables (not committed)
├── .env.example                # Template showing required environment variables
└── .gitignore
```

## Environment Configuration

Two `.env` files are used and loaded in sequence by `config.py`:

- A base `.env` higher up in the directory tree holds `DB_PASSWORD` (shared across projects)
- A project-level `.env` holds all other variables: Azure OpenAI credentials, database connection details, and the collection name

The project-level `.env` is loaded with `override=True` so its values take precedence, while `DB_PASSWORD` is read from the base file before the override happens, preserving both.

Required environment variables:

| Variable | Description |
|---|---|
| DB_USER | PostgreSQL username |
| DB_PASSWORD | PostgreSQL password (loaded from base .env) |
| DB_HOST | Database host |
| DB_PORT | Database port |
| DB_NAME | Database name |
| AZURE_OPENAI_ENDPOINT | Azure OpenAI resource endpoint |
| AZURE_OPENAI_API_KEY | Azure OpenAI API key |
| AZURE_OPENAI_DEPLOYMENT | Embedding model deployment name |
| AZURE_OPENAI_API_VERSION | API version (default: 2024-02-01) |
| COLLECTION_NAME | PGVector collection name (default: automind_embedding) |

## Task 1 — Database Setup

PostgreSQL is used with the `pgvector` extension, which adds a native vector data type and similarity search operators. The `check_database_connection` function in `embedding_setup.py` verifies the connection and automatically enables the extension if it is not already present.

The database used for this project is `automind_db`, which had the `vector` extension (version 0.8.2) pre-installed. LangChain's PGVector integration automatically creates the required tables (`langchain_pg_collection` and `langchain_pg_embedding`) on first use.

## Task 2 — Embeddings Generation and Storage

### Embedding Model

Azure OpenAI's `text-embedding-3-small` model is used to convert text into 1536-dimensional vector embeddings. The model is initialised via `AzureOpenAIEmbeddings` from `langchain-openai` and configured with the endpoint, deployment name, API key, and API version from the environment.

### Sample Data

`sample_data.py` contains two sources of data:

- `SAMPLE_DOCUMENTS` — two pre-built LangChain `Document` objects representing real automotive content (vehicle specifications and pricing for the 2024 EcoSport Hybrid), each with structured metadata including document name, category, model, section, page, and a unique ID
- `SAMPLE_SENTENCES` — five plain text strings covering automotive topics (engine, sensor, brake, transmission, calibration), used by unit tests

### Storage

Documents are stored in PostgreSQL via LangChain's `PGVector` class. Each document's text is converted to a vector embedding by Azure OpenAI, then written to the `langchain_pg_embedding` table alongside its metadata and a reference to the named collection in `langchain_pg_collection`. Stored documents receive auto-generated UUIDs as their primary identifiers.

## Task 3 — Pipeline Service and REST API

### REST API

The FastAPI application exposes two endpoints under the `/api/v1` prefix:

**POST /api/v1/upload**

Accepts a JSON body with a `doc_id` (required), `content` (required), and optional `metadata` dictionary. The `doc_id` is merged into the metadata before storage. Returns a success flag, a status message, and the generated document ID.

**POST /api/v1/query**

Accepts a `query` string and an optional `top_k` integer (1–10, default 1). Performs a semantic similarity search against all stored documents and returns the ranked results, each containing the document content and its metadata.

Both endpoints use typed Pydantic request and response models, and handle errors with appropriate HTTP status codes (422 for validation errors, 500 for unexpected failures).

The Swagger UI is available at `http://localhost:8000/docs` when the server is running.

### Embedding Setup Pipeline

`embedding_setup.py` also exposes standalone functions that mirror the steps of the pipeline and are independently testable:

- `normalize_db_url` — converts SQLAlchemy-style connection strings to psycopg2-compatible format
- `check_database_connection` — verifies the PostgreSQL connection and ensures the vector extension is enabled
- `initialize_embeddings` — creates an `AzureOpenAIEmbeddings` instance from a config dict
- `create_vectorstore` — creates a `PGVector` store instance, returning `None` on failure rather than raising
- `insert_sample_data` — converts a list of plain strings into `Document` objects with standard metadata and inserts them
- `read_all_embeddings` — reads all stored embeddings for a collection directly via SQL
- `perform_similarity_search` — runs a scored similarity search and logs ranked results with distance and similarity scores

Running `embedding_setup.py` directly as a script executes the full pipeline in sequence: connection check, service initialisation, document insertion, and a test similarity search.

## Running the Application

**Run the full pipeline (Tasks 1 & 2):**

```bash
python -m main.embedding_setup
```

**Start the API server (Task 3):**

```bash
uvicorn main.app:app --host 0.0.0.0 --port 8000 --reload
```

**Run the unit tests:**

```bash
pytest tests/ -v
```

All 38 tests pass. Tests use mocks for the database and Azure OpenAI, so no live credentials or database connection are required to run them.

## Verification

After running `embedding_setup.py`, the database can be inspected to confirm documents were stored:

```bash
psql -U postgres -d automind_db -c "SELECT COUNT(*) FROM langchain_pg_embedding;"
```

The similarity search output confirms semantic relevance — a query about EcoSport Hybrid pricing returns the Pricing Guide document as rank 1 (similarity 0.83) and the Vehicle Catalog as rank 2 (similarity 0.82).