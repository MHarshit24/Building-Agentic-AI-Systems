## Investment Advisor RAG System with Fusion Retrieval and Guardrails

## Project Context

You're building an **Investment Advisor RAG System**, an AI-powered retrieval system that helps users get accurate financial information, investment advice, and policy details from financial documents. The system must handle both exact keyword matching (for terms like "RMD", "401(k)") and semantic understanding (e.g., "risk-averse" → "Conservative profile"), while ensuring security through comprehensive guardrails.

This practice focuses on **fusion retrieval** — combining multiple retrieval methods (BM25 keyword search + Vector semantic search) using Reciprocal Rank Fusion (RRF) for optimal results, and implementing **comprehensive guardrails** for PII protection, input validation, and output sanitization.

## Problem Statement

Build a production-ready RAG system that can answer financial queries using document knowledge with enhanced retrieval accuracy and security. The key challenges are:

1. **Retrieval Accuracy**: Combining keyword-based (BM25) and semantic (vector) search to handle both exact term queries and conceptual queries
2. **Security**: Protecting sensitive information (PII) in both input queries and output responses
3. **Input Validation**: Blocking malicious queries (prompt injection, toxic content)
4. **Output Sanitization**: Automatically redacting PII from generated responses

You will complete the following implementation tasks to build the RAG system with fusion retrieval and guardrails:

---

### **Task 1 — Implement Query API Endpoint**

#### Goal

Create a FastAPI endpoint that accepts user queries and returns structured responses with answers, retrieved chunks, and validation results.

#### Requirements

1. Start a performance timer to measure query processing time
2. Get the active RAG service instance
3. Call the service's query method with the user's query text
4. Transform the service result into a QueryResponse object with proper type mapping
5. Handle exceptions and return appropriate HTTP error responses

**Implementation**: The endpoint initializes a performance timer using `time.perf_counter()` to measure execution time. It retrieves the active RAG service via `get_active_service()` helper function, calls the service's `query()` method with the user's query text, and maps the resulting dictionary to a properly typed `QueryResponse` object with nested `ValidationResults`. All retrieved nodes are transformed into `NodeResponse` objects, and any exceptions are caught and returned as HTTP 500 errors with descriptive messages.

**File**: `main/routes/query_routes.py` → `query()` _(currently boilerplate)_

---

### **Task 2 — Initialize Fusion Retrieval System**

#### Goal

Set up the fusion retrieval infrastructure by creating vector and BM25 retrievers and combining them using QueryFusionRetriever.

#### Requirements

1. Create a StorageContext from the vector store
2. Create a VectorStoreIndex from the vector store and storage context
3. Create a vector retriever from the index with configured similarity top k
4. Load all nodes from the vector store for BM25 retriever (with error handling)
5. Create BM25 retriever if nodes are available, otherwise set to None
6. Create a QueryFusionRetriever combining both retrievers with RRF mode
7. Create a RetrieverQueryEngine from the fusion retriever

**Implementation**: The fusion retrieval system is initialized by creating a `StorageContext` from the vector store, then building a `VectorStoreIndex` on top of it. A vector retriever is created with configurable similarity top-k. All nodes are loaded from the vector store for the BM25 retriever, with error handling for empty stores or connection issues. If nodes exist, a `BM25Retriever` is instantiated; otherwise, the system gracefully falls back to vector-only search. The two retrievers are combined using `QueryFusionRetriever` with reciprocal rerank fusion mode, and finally a `RetrieverQueryEngine` is built from the fusion retriever to enable answer generation.

**File**: `main/service/fusion_retrieval.py` → `_init_retrievers()` _(currently boilerplate)_

---

### **Task 3 — Implement Query and Retrieve Methods**

#### Goal

Implement methods to query the fusion retrieval system for answers and retrieve relevant document chunks.

#### Requirements

1. **Query Method**: Call the query engine with query text and convert the result to a string
2. **Retrieve Method**: Use the fusion retriever to get relevant nodes, then transform each node into a RetrievedChunk object by extracting text, score (with getattr fallback), and source from metadata (filename or source_path)

**Implementation**: The `query()` method invokes `self.query_engine.query()` with the query text and returns the string representation of the result. The `retrieve()` method calls `self.fusion_retriever.retrieve()` to obtain relevant document nodes, then transforms each node into a `RetrievedChunk` dataclass by extracting the text content, relevance score (with None fallback if unavailable), and source file information from node metadata (checking filename first, then source_path). The method handles missing metadata gracefully using try/except blocks and returns a list of structured chunks.

**File**: `main/service/fusion_retrieval.py` → `query()`, `retrieve()` _(currently boilerplate)_

---

### **Task 4 — Initialize Guardrails Validator**

#### Goal

Set up the Guardrails Hub DetectPII validator for PII detection and redaction.

#### Requirements

1. Initialize `_pii_guard` to None
2. Import Guard and DetectPII from guardrails library
3. Create a Guard instance and configure it with DetectPII to detect various PII entity types (EMAIL_ADDRESS, PHONE_NUMBER, US_SSN, CREDIT_CARD, US_PASSPORT, US_DRIVER_LICENSE, PERSON, LOCATION, DATE_TIME)
4. Set `on_fail="fix"` for automatic redaction
5. Handle exceptions gracefully - if initialization fails, keep `_pii_guard` as None

**Implementation**: The validator initializes by setting `_pii_guard` to None, then attempts a two-tier approach: first trying to import and configure GuardrailsHub's DetectPII validator with automatic redaction (`on_fail="fix"`), which sets `_pii_guard` to the configured Guard instance. If GuardrailsHub is unavailable, it falls back to Presidio's `AnalyzerEngine` and `AnonymizerEngine` for identical PII detection and anonymization behavior. In the Presidio fallback case, `_pii_guard` is set to the sentinel string "presidio" to indicate which implementation is active. A list of 9 PII entity types is configured across both implementations (EMAIL_ADDRESS, PHONE_NUMBER, US_SSN, CREDIT_CARD, US_PASSPORT, US_DRIVER_LICENSE, PERSON, LOCATION, DATE_TIME). If both approaches fail, `_pii_guard` remains None, gracefully disabling PII checking. Each stage logs appropriate warnings or success messages.

**File**: `main/service/guardrails.py` → `__init__()` _(currently boilerplate)_

---

### **Task 5 — Implement Input Validation**

#### Goal

Validate user input queries to ensure they are not empty or only whitespace.

#### Requirements

1. Check if the input text is empty or contains only whitespace characters
2. Return `InputDecision(allowed=False, reason="Empty query")` if input is invalid
3. Return `InputDecision(allowed=True, reason=None)` if input is valid

**Implementation**: The method checks if the input text is empty or contains only whitespace using a simple boolean check (`not text or not text.strip()`). If the text is invalid, it returns `InputDecision(allowed=False, reason="Empty query")`; otherwise, it returns `InputDecision(allowed=True, reason=None)` to allow the query to proceed.

**File**: `main/service/guardrails.py` → `decide_input()` _(currently boilerplate)_

---

### **Task 6 — Implement Output Sanitization**

#### Goal

Validate and sanitize output text using the Guardrails Hub DetectPII validator to detect and redact PII.

#### Requirements

1. Initialize tracking variables (pii_summaries list, pii_detected boolean, output_sanitized boolean, sanitized text)
2. If `_pii_guard` is available, validate the text through the guard
3. Extract validated output from the result and compare with original text
4. If PII was detected and redacted, update tracking variables and add summary message
5. Handle validation errors gracefully by keeping original text
6. Return `OutputDecision` with all validation results (blocked, reason, sanitized_text, pii_detected, pii_summaries, output_sanitized)

**Implementation**: The method initializes tracking variables for PII summaries, detection status, and sanitization status, with the sanitized text defaulting to the input. If `_pii_guard` is available (not None), it uses a dual-path strategy: if `_pii_guard` equals "presidio", it calls `_analyzer.analyze()` and `_anonymizer.anonymize()` for Presidio-based detection and redaction; otherwise, it calls `_pii_guard.validate()` for GuardrailsHub Guard validation. The validated or anonymized text is compared with the original—if different, it sets `pii_detected=True`, `output_sanitized=True`, and appends "PII detected and redacted" to the summaries, then updates the sanitized text. Validation errors are caught and silently handled, preserving the original text. The method returns an `OutputDecision` dataclass containing all tracking information, the sanitized text, and the blocked/reason flags.

**File**: `main/service/guardrails.py` → `validate_and_sanitize_output()` _(currently boilerplate)_

---

### **Task 7 — Initialize RAG Service**

#### Goal

Set up the RAG service by creating the vector store, fusion retrieval service, and validator.

#### Requirements

1. Store instance variables (table_name, similarity_top_k)
2. Create PGVectorStore from environment variables (host, port, database, user, password, table_name, embed_dim)
3. Initialize FusionRetrievalService with the vector store and configuration
4. Set up the validator (use provided validator or get from app.py using get_validator function)

**Implementation**: The service stores `table_name` and `similarity_top_k` as instance variables, then creates a `PGVectorStore` by reading database connection parameters from environment variables (DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD). The database password is URL-encoded using `quote_plus()` to handle special characters. The `FusionRetrievalService` is instantiated with the vector store and configured with reciprocal rerank fusion mode. The validator is either used directly if provided or imported from the app module using `get_validator()`. Initialization is logged with timing and configuration details.

**File**: `main/service/rag_service.py` → `__init__()` _(currently boilerplate)_

---

### **Task 8 — Implement RAG Query Orchestration**

#### Goal

Orchestrate the complete RAG pipeline: input validation → retrieval → answer generation → output sanitization.

#### Requirements

1. Initialize validation_results dictionary with default values (input_allowed, input_block_reason, pii_detected, pii_summaries, output_sanitized, output_blocked, output_block_reason)
2. Validate input using validator's decide_input method
3. If input is blocked, return early with blocked response including validation results
4. Try to retrieve and generate answer using retrieval service (query and retrieve methods)
5. Handle retrieval errors gracefully (e.g., no documents available) and return appropriate error response
6. Validate and sanitize output using validator's validate_and_sanitize_output method
7. Update validation_results with output validation results
8. Return final result dictionary with query, sanitized answer, retrieved nodes, and validation results
**Implementation**: The orchestration method initializes a validation results dictionary with default values for input/output validation, PII detection, and blocking status. Input is validated using `decide_input()`; if blocked, it returns early with a descriptive message. The retrieval service's `query()` and `retrieve()` methods are called within a try/except block to handle cases where no documents are available. Output is sanitized using `validate_and_sanitize_output()`, and all validation results are merged into the tracking dictionary. Performance metrics (execution time, PII detection, sanitization status, chunk count) are logged, and a final result dictionary is returned containing the original query, sanitized answer, retrieved nodes with metadata, and complete validation results.
**File**: `main/service/rag_service.py` → `query()` _(currently boilerplate)_

## Evaluation Criteria

Ensure you evaluate your solution against the below criteria:

1. **Fusion Retrieval Initialization**: The fusion retrieval system successfully initializes with both vector and BM25 retrievers (when nodes are available), combines them using QueryFusionRetriever with RRF mode, and creates a query engine.

2. **Query and Retrieve Methods**: The query method returns string answers from the query engine, and the retrieve method returns a list of RetrievedChunk objects with proper text, score, and source extraction from node metadata.

3. **Guardrails Initialization**: The GuardrailsValidator successfully initializes with DetectPII validator configured for multiple PII entity types, with graceful error handling if initialization fails.

4. **Input Validation**: The decide_input method correctly identifies empty or whitespace-only queries and returns appropriate InputDecision objects.

5. **Output Sanitization**: The validate_and_sanitize_output method detects PII in output text, redacts it using the guard, tracks detection status, and returns OutputDecision with all validation results.

6. **End-to-End Pipeline**: The complete system processes queries through input validation → fusion retrieval → answer generation → output sanitization, returning structured responses with retrieved chunks and validation results.
