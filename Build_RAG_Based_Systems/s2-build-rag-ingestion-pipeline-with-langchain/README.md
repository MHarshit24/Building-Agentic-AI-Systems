## Project Context

You're building **Smart Auto Advisor**, an AI-powered conversational assistant for car manufacturers that helps customers get instant answers about vehicle models, features, pricing, and availability.

This practice builds on the previous practice to create a complete document ingestion pipeline that transforms raw documents (PDFs, HTML, text files) into searchable vector embeddings.

## Problem Statement

Build a robust ingestion pipeline that processes diverse document formats (PDFs, web pages, text files) and converts them into searchable vectors. Documents must be split into manageable chunks, embedded, and stored with metadata for accurate retrieval. Without a proper ingestion pipeline, you can't populate your knowledge base with company documents, product specs, or customer data.

You will complete three tasks to build this ingestion pipeline:

---

### **Task 1 — Document Loading and Processing**

#### Goal

Load documents from multiple sources (PDF, HTML, TXT, Web) and process them for ingestion.

#### Requirements

Create a document processing service that:

- Automatically detects file type
- Routes files to appropriate loaders
- Handles errors gracefully
- Preserves source file metadata

#### Implementation

**`DocumentProcessingService`** (`main/services/document_processing_service.py`) acts as the central router. It uses `detect_file_type()` to inspect the file extension and delegates to the appropriate loader service. All loaders attach `source_file` and `file_type` metadata to every `Document` object they return, ensuring traceability through the rest of the pipeline.

- **`PDFLoaderService`** uses LangChain's `PyPDFLoader`, which splits a PDF into one `Document` per page, preserving the `page` number in metadata.
- **`TextLoaderService`** uses LangChain's `TextLoader` with UTF-8 encoding, returning the entire file as a single `Document`.
- **`HTMLLoaderService`** uses LangChain's `BSHTMLLoader` with Python's built-in `html.parser`, cleanly extracting visible text from HTML files.
- **`WebLoaderService`** uses LangChain's `WebBaseLoader` with a `bs4.SoupStrainer` scoped to meaningful content tags (headings, paragraphs, lists, tables), filtering out navigation and boilerplate. It supports loading single or multiple URLs and gracefully returns an empty list on fetch failures.

`process_directory()` iterates over all supported files in a given directory (optionally recursive) and aggregates the resulting documents, skipping any file that fails to load with a warning rather than halting the entire batch.

---

### **Task 2 — Document Chunking and Embedding**

#### Goal

Split documents into manageable chunks and generate vector embeddings.

#### Requirements

- Implement intelligent chunking

- Generate embeddings

### **Task 3 — Complete Pipeline and REST API**

#### Goal

Build a complete ingestion pipeline with REST API endpoints for document upload and querying.

#### Requirements

- Create pipeline orchestration service

  - Coordinate document loading, chunking, and embedding

2. Implement REST API endpoints

# Evaluation Criteria

Ensure you evaluate your solution against the below criteria

1. Proper Document loader for pdf, txt, html are used
2. Document chunking is done using `RecursiveCharacterTextSplitter`
3. Chunks are properly embedded and stored in Postgres Database with pgVector
4. The pipeline performs basic semantic query

---

## Implementation Details

### Task 1 — Document Loading and Processing

**`DocumentProcessingService`** (`main/services/document_processing_service.py`) acts as the central router. It uses `detect_file_type()` to inspect the file extension and delegates to the appropriate loader service. All loaders attach `source_file` and `file_type` metadata to every `Document` object they return, ensuring traceability through the rest of the pipeline.

- **`PDFLoaderService`** uses LangChain's `PyPDFLoader`, which splits a PDF into one `Document` per page, preserving the `page` number in metadata.
- **`TextLoaderService`** uses LangChain's `TextLoader` with UTF-8 encoding, returning the entire file as a single `Document`.
- **`HTMLLoaderService`** uses LangChain's `BSHTMLLoader` with Python's built-in `html.parser`, cleanly extracting visible text from HTML files.
- **`WebLoaderService`** uses LangChain's `WebBaseLoader` with a `bs4.SoupStrainer` scoped to meaningful content tags (headings, paragraphs, lists, tables), filtering out navigation and boilerplate. It supports loading single or multiple URLs and gracefully returns an empty list on fetch failures.

`process_directory()` iterates over all supported files in a given directory (optionally recursive) and aggregates the resulting documents, skipping any file that fails to load with a warning rather than halting the entire batch.

### Task 2 — Document Chunking and Embedding

**`ChunkingService`** (`main/services/chunking_service.py`) wraps LangChain's `RecursiveCharacterTextSplitter`, configured with a default chunk size of 1000 characters and an overlap of 200 characters (both overridable via environment variables `CHUNK_SIZE` and `CHUNK_OVERLAP`). The splitter uses a hierarchy of separators — double newlines, single newlines, sentence-ending punctuation, and spaces — so splits happen at the most natural boundaries available in the text.

After splitting, each chunk is enriched with four metadata fields: `chunk_id` (sequential integer index), `chunk_identifier` (a human-readable string combining the source file name, page number if present, and chunk index), `chunk_size` (character count of the chunk content), and `upload_time` (ISO 8601 UTC timestamp of when the batch was processed).

**`EmbeddingService`** (`main/services/embedding_service.py`) uses LangChain's `AzureOpenAIEmbeddings` to call the configured Azure OpenAI deployment (`text-embedding-3-small`). Embeddings are stored in a PostgreSQL database via LangChain's `PGVector` integration under the collection `smart_auto_rag_ingestion`. The vectorstore is lazily initialised on first use and reused across calls within the same service instance.

### Task 3 — Complete Pipeline and REST API

**`InjectionPipelineService`** (`main/services/injection_pipeline_service.py`) orchestrates the three stages — loading, chunking, and embedding — into a single call. It exposes `process_file()`, `process_url()`, `process_directory()`, and a convenience `run()` method that targets the default documents directory. Each method returns a structured result dictionary with status, counts of documents loaded, chunks created, and embeddings stored, making it straightforward to inspect outcomes programmatically or surface them via the API.

**`QueryService`** (`main/services/query_service.py`) wraps the vectorstore's `similarity_search_with_score()` method, accepting a query string, a `top_k` count, and an optional metadata filter. It returns a list of `(Document, distance_score)` tuples, with the distance score reflecting the raw vector distance from the query embedding.

The **REST API** (`main/routes/ingestion_routes.py`) is built with FastAPI and exposes four endpoints under the `/api/v1` prefix:

- `GET /documents` — lists all files currently in the documents directory with name, size, extension, and upload timestamp.
- `POST /upload` — accepts a single file upload (PDF, TXT, HTML, HTM, or DOCX up to 10 MB), saves it with a timestamp prefix to prevent collisions, runs it through the full ingestion pipeline, and returns chunk and embedding counts in the response.
- `POST /query` — accepts a query string and optional `top_k` parameter, runs a semantic similarity search against the vector database, and returns the matching document chunks with their metadata and distance scores.
- `GET /` — returns API name, version, description, and a list of available endpoints.

### Configuration

**`config.py`** loads environment variables from two `.env` files in sequence. The root-level `.env` (three directories up from the config file) is loaded first and supplies `DB_PASSWORD`, `AZURE_OPENAI_ENDPOINT`, and `AZURE_OPENAI_API_KEY`. The project-level `.env` is then loaded with `override=True`, supplying all remaining non-sensitive configuration. The database password is percent-encoded using `urllib.parse.quote_plus` to safely handle any special characters in the connection URL.