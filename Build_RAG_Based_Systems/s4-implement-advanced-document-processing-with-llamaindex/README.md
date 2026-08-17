# Advanced Document Processing with LlamaIndex

## Project Context

You're building a **Personal Diet Counselling Assistant**, an AI-powered RAG system that helps users get personalized dietary advice, nutrition information, and meal recommendations based on their specific dietary needs and preferences.

This practice focuses on **advanced document processing** — implementing semantic chunking, metadata filtering, and building a complete RAG pipeline with LlamaIndex. You'll learn how to process documents intelligently, create vector indexes with metadata, and build query engines that support targeted retrieval.

## Problem Statement

Build a production-ready RAG system that can handle diet-specific queries with precision. The system must support semantic chunking for better context preservation, automatic metadata extraction from filenames, and filtered queries to retrieve relevant information from specific document categories (meal types, dietary restrictions, nutrition categories).

You will complete multiple implementation tasks to build this RAG system:

---

### **Task 1 — Setup Azure OpenAI Services**

#### Goal

Initialize Azure OpenAI LLM and Embedding models for the RAG system.

#### Requirements

1. Configure Azure OpenAI credentials in `.env`
2. Initialize AzureOpenAI LLM (gpt-4o-mini)
3. Initialize AzureOpenAIEmbedding (text-embedding-3-small, 1536 dimensions)
4. Assign models to LlamaIndex Settings for global access

Implementation Details:
- The service layer loads both root and project `.env` files, preserving secret values and validating Azure and database variables.
- The Azure OpenAI LLM is initialized using the configured deployment name and endpoint, defaulting to `gpt-4o-mini` when the model name is not explicitly provided.
- The embedding model is created with the `text-embedding-3-small` default and 1536-dimensional embeddings.
- Both the LLM and embedding instances are assigned to `Settings.llm` and `Settings.embed_model` so LlamaIndex can use them globally.

**File**: `main/service/rag_service.py`

---

### **Task 2 — Setup Vector Index with PGVector**

#### Goal

Create and manage a persistent vector index using PostgreSQL with PGVector extension.

#### Requirements

1. Initialize PGVectorStore with database connection parameters
2. Create StorageContext from the vector store
3. Implement logic to load existing index or create a new empty one
4. Handle exceptions gracefully for missing indexes

Implementation Details:
- The index loader uses `PGVectorStore.from_params()` with PostgreSQL credentials from environment variables and an explicit embedding dimension of 1536.
- A `StorageContext` is constructed from the vector store so LlamaIndex can access the persistent storage layer.
- The loader attempts to open an existing index via `VectorStoreIndex.from_vector_store()` and falls back to creating a new empty `VectorStoreIndex` if no persisted index is found.
- Exceptions are caught and logged, allowing the application to initialize a fresh index for first-time runs.

**File**: `main/service/rag_service.py` - `load_or_create_index()`

---

### **Task 3 — Implement Semantic Chunking**

#### Goal

Set up semantic chunking to split documents intelligently based on content similarity.

#### Requirements

1. Create SemanticSplitterNodeParser with:
   - Embedding model for similarity calculation
   - Buffer size (sentences on either side of splits)
   - Breakpoint percentile threshold
2. Generate nodes from documents using the semantic splitter
3. Preserve document metadata in generated nodes

Implementation Details:
- The semantic chunking module creates a `SemanticSplitterNodeParser` configured with the embedding model, buffer size, and breakpoint percentile threshold.
- Document nodes are generated through the parser so text is split by semantic content rather than fixed size alone.
- Metadata is preserved by generating nodes directly from the input documents, ensuring diet-specific tags remain attached to each chunk.

**File**: `main/service/semantic_chunking.py`

---

### **Task 4 — Build Query Engine**

#### Goal

Create a query engine that supports similarity search and metadata filtering.

#### Requirements

1. Create query engine from VectorStoreIndex
2. Configure similarity_top_k parameter
3. Support optional metadata filters for targeted retrieval
4. Return query engine instance

Implementation Details:
- The query engine layer creates a fresh query engine from the vector index on each request.
- It passes the Azure OpenAI LLM and the requested `similarity_top_k` value so retrieval is tuned to the desired result count.
- Optional metadata filters are forwarded to the engine, enabling constrained search over diet-specific categories.
- The module returns the configured query engine instance for query execution.

**File**: `main/service/query_engine.py`

---

### **Task 5 — Implement Document Upload Processing**

#### Goal

Build the document upload pipeline with automatic metadata assignment.

#### Requirements

1. Load documents using SimpleDirectoryReader
2. Extract metadata from filename using get_file_metadata()
3. Apply metadata to all loaded documents
4. Add documents to index with semantic chunking
5. Return upload response with success message

Implementation Details:
- The upload route validates filename, extension, and file size before accepting the document.
- Incoming files are written to a temporary location and loaded with `SimpleDirectoryReader`.
- Metadata is extracted from the sanitized filename using `get_file_metadata()`, then copied onto each loaded document.
- Documents are indexed with semantic chunking via `add_documents_to_index()`, and the response returns a success message plus document count.

**File**: `main/routes/routes.py` - `upload_document()`

---

### **Task 6 — Implement Query Processing**

#### Goal

Build the query endpoint with metadata filtering support.

#### Requirements

1. Construct MetadataFilters from request filters (if provided)
2. Get query engine with similarity_top_k and filters
3. Execute query with user's question
4. Extract answer from response
5. Return QueryResponse with answer and source nodes

Implementation Details:
- The query route constructs metadata filters from the request dictionary using `ExactMatchFilter` objects.
- It obtains a query engine with the requested `similarity_top_k` and optional filters.
- The question is executed against the engine, and the response text is extracted as the final answer.
- Source nodes are collected from the engine response and returned alongside the answer to show retrieval provenance.

**File**: `main/routes/routes.py` - `query_rag()`

---

### **Task 7 — Add Documents to Index**

#### Goal

Implement the complete indexing pipeline with semantic chunking.

#### Requirements

1. Get embedding model using get_embed_model()
2. Create semantic splitter using create_semantic_splitter()
3. Generate nodes from documents using generate_nodes_from_documents()
4. Insert each node into the index
5. Handle errors during insertion
6. Return success message with document count

Implementation Details:
- The indexing pipeline retrieves the embedding model from the initialized services and builds a semantic splitter.
- It generates semantic nodes for each document so text is split based on content similarity.
- All generated nodes are inserted into the persistent vector index, with insertion errors logged for visibility.
- The function returns a success dictionary summarizing how many documents were indexed.

**File**: `main/service/rag_service.py` - `add_documents_to_index()`

## Evaluation Criteria

Ensure you evaluate your solution against the below criteria:

1. Azure OpenAI Integration: LLM and Embedding models are correctly initialized and configured (text-embedding-3-small, 1536 dimensions)
2. Vector Database Setup: PostgreSQL database is properly configured with PGVector extension and LlamaIndex PGVectorStore connection is established
3. Index Management: LlamaIndex VectorStoreIndex is successfully created and loaded from PostgreSQL with proper StorageContext
4. Semantic Chunking: LlamaIndex SemanticSplitterNodeParser is implemented with embedding model and generates nodes preserving metadata
5. Query Engine Creation: LlamaIndex QueryEngine is created from VectorStoreIndex with metadata filtering support using MetadataFilters
6. Complete RAG Pipeline: The LlamaIndex RAG pipeline performs semantic search operations with metadata filtering successfully
