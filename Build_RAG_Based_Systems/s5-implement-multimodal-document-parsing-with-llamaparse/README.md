## Multi-Modal Content Processing with LlamaIndex (Tables + Images)

## Project Context

You're building a **Personal Diet Counselling Assistant**, an AI-powered RAG system that helps users get personalized dietary advice, nutrition information, and meal recommendations based on their specific dietary needs and preferences.

This practice focuses on **multi-modal content processing** — extracting **tables and images** from documents (especially PDFs), converting them into text representations (table summaries + image captions), and indexing them alongside regular text for better retrieval.

## Problem Statement

Build a production-ready RAG system that can answer diet-specific queries using document knowledge. The key challenge here is that real documents contain **tables and images** that must be extracted and converted into searchable text.

You will complete the following implementation tasks to build the multi-modal ingestion pipeline:

---

### **Task 1 — Extract Tables from Parsed Text**

#### Goal

Detect markdown tables in parsed document text and return them as structured blocks.

#### Requirements

1. Scan markdown text and detect table blocks
2. Return table blocks with character offsets (start/end) and the table markdown
3. Return an empty list if no tables exist

**File**: `main/service/table_extraction.py` → `find_markdown_tables()` _(currently boilerplate)_

#### Implementation details

- The `find_markdown_tables()` implementation scans the parsed markdown line-by-line and detects contiguous blocks that look like markdown tables (lines containing the pipe character `|`). It keeps track of the character offset in the original string so each table is returned with precise `start` and `end` character indices.
- A block is considered a valid table if it contains at least two lines and the second line matches the markdown table separator pattern (dashes, pipes and optional alignment colons). For each valid table the function returns a tuple `(start_char_index, end_char_index, table_markdown)`.
- If no table-like blocks are found the function returns an empty list. The implementation is resilient to non-table pipe usage by requiring the header+separator pattern before accepting a block as a table.

---

### **Task 2 — Summarize Tables and Create Nodes**

#### Goal

Summarize extracted markdown tables and convert them into `TextNode` objects for indexing.

#### Requirements

1. Summarize each table into a concise natural language description using an LLM
2. Create `TextNode` objects for each summary
3. Attach metadata fields such as `source`, `content_type="table_summary"`, and `table_index`
4. Merge any additional metadata into each node

**File**: `main/service/table_processing.py` → `summarize_table()`, `build_nodes_from_tables()` _(currently boilerplate)_

#### Implementation details

- `summarize_table()` uses the project's configured LLM client (wrapped by `AzureOpenAI` from `llama_index.llms.azure_openai`) to produce a concise, single-sentence natural-language summary for a given markdown table. The function constructs a nutrition-focused prompt (the project context is a diet counselling assistant) and calls the LLM; it trims the result and returns it as the table summary.
- A simple fallback path is implemented: if the LLM call raises an exception the function returns a short descriptive fallback string containing the first portion of the table markdown so indexing can continue.
- `build_nodes_from_tables()` iterates the list of extracted table markdowns, summarizes each table with `summarize_table()` and creates `TextNode` objects (from `llama_index.core.schema`) for indexing. Each node receives metadata fields at minimum: `source` (document name), `content_type` set to `table_summary`, and a `table_index` (0-based). Any `additional_metadata` provided to the function is merged into each node's metadata so diet tags and traceability fields are preserved.

---

### **Task 3 — Extract Images from PDFs**

#### Goal

Extract embedded images from PDF documents and save them to disk for downstream captioning.

#### Requirements

1. Iterate through PDF pages and detect embedded images
2. Save extracted images into an output directory
3. Return a list of extracted image records with `path`, `page`, and `image_index`
4. Return an empty list if no images exist

**File**: `main/service/image_extraction.py` → `extract_images_from_pdf()` _(currently boilerplate)_

#### Implementation details

- Image extraction is implemented with PyMuPDF (`fitz`). The `extract_images_from_pdf()` function opens the PDF, iterates pages and calls `page.get_images()` to discover embedded images.
- For each discovered image the function uses the image XREF to extract raw bytes via `doc.extract_image(xref)` and saves the image into the provided `output_dir` using a filename pattern like `page{page_num}_img{index}.{ext}`. It returns a list of records `{"path": <path>, "page": <page_num>, "image_index": <index>}` for downstream captioning.
- The output directory is created if missing and the function gracefully logs and skips image extraction failures for individual images, returning an empty list when no images are found.

---

### **Task 4 — Caption Images**

#### Goal

Generate text captions for extracted images so they can be indexed and retrieved.

#### Requirements

1. Use a vision-capable model (or any image captioning method)
2. Take an image path and an optional prompt
3. Return a concise caption string suitable for indexing

**File**: `main/service/captioning.py` → `generate_caption()` _(currently boilerplate)_

#### Implementation details

- Image captioning is implemented to work with an Azure OpenAI vision-capable interface exposed via an `AzureOpenAI`-like client. The function reads the image bytes, base64-encodes them and constructs a `data:` URL payload to send as the image input to the vision endpoint.
- Required environment variables are validated up-front (`AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_LLM_DEPLOYMENT`, and optional `AZURE_OPENAI_API_VERSION`). The function calls the client using a single multimodal chat completion request containing the image payload plus a concise prompt asking for a nutritional/diet-focused caption.
- The response text is returned as the caption. If the vision call fails the function logs a warning and returns a simple fallback caption that preserves the image filename for traceability.

---

### **Task 5 — Integrate Multi-Modal Nodes into Ingestion**

#### Goal

Orchestrate table/image extraction + summarization/captioning and insert the resulting nodes into your vector index.

#### Requirements

1. Parse the document into text/markdown
2. Extract tables and build table summary nodes
3. Extract images and build image caption nodes
4. Ensure metadata is preserved for every node (source, content_type, page/table_index/image_index, diet tags)
5. Insert all nodes into the vector index

**File**: `main/service/rag_service.py` → `process_document()` _(currently boilerplate)_

#### Implementation details

- `process_document()` orchestrates the end-to-end ingestion pipeline and preserves metadata for traceability. High-level steps executed by the implementation:
	- Ensure the service is initialized: LLM and embedding models are configured from environment variables using `configure_llm_and_embeddings()` and assigned to the service instance.
	- Build initial file metadata using `get_file_metadata(pdf_path)`. If an `original_filename` is provided the metadata `source`/`file_path` are overridden and diet tags are re-extracted via `extract_diet_metadata_from_filename()`.
	- Parse the PDF into markdown text using `LlamaParse` (result_type="markdown") via `load_documents()`; the returned text is joined into a single string for processing.
	- Produce semantic text chunks using the project's `SemanticChunker` to create `TextNode` objects for the main text content; these nodes include the merged metadata so filters and diet tags are preserved.
	- Extract markdown tables from the parsed text using `find_markdown_tables()` and build table summary nodes via `build_nodes_from_tables()` (these nodes have `content_type: table_summary` and `table_index` metadata fields).
	- Extract embedded PDF images using `extract_images_from_pdf()` into a temporary directory. For each extracted image the pipeline calls `generate_caption()` to obtain a concise caption, wraps it into a `TextNode` with metadata including `content_type: image_caption`, `page` and `image_index`.
	- Combine text, table and image nodes into a single list and create / connect to a PostgreSQL-backed vector store (`PGVectorStore`) using `create_vector_store()`. The pipeline either creates a new `VectorStoreIndex` (initial indexing) or inserts nodes into an existing index.
	- After indexing, a query engine is created/updated by `create_query_engine()` so the index is immediately queryable.
- The function returns a result dictionary with processing statistics including `documents_indexed`, `total_nodes`, and breakdown counts for `text_nodes`, `table_nodes`, and `image_nodes`. Temporary image artifacts are cleaned up by using a `TemporaryDirectory` context.

---

### **Task 6 — Expose Upload Endpoint (API)**

#### Goal

Expose an API endpoint that accepts a document and triggers the multi-modal ingestion pipeline.

#### Requirements

1. Validate filename/extension and max size (10MB)
2. Persist the uploaded bytes for processing
3. Call `process_document()` (ingestion) and return the result
4. Cleanup temporary artifacts

**File**: `main/routes/routes.py` → `upload_document()` _(currently boilerplate)_

#### Implementation details

- The `POST /upload` endpoint validates the uploaded file and runs ingestion via the `RAGService` instance:
	- It validates that a filename was provided and that the file extension is allowed (`.pdf`, `.txt`, `.md`).
	- It enforces a maximum upload size of 10MB and returns an HTTP 400 error when exceeded.
	- Uploaded bytes are saved to a `tempfile.NamedTemporaryFile` and the temporary path is passed to `rag_service.process_document()` along with the original filename for metadata extraction.
	- On success the endpoint returns a compact processing summary (`message` and `documents_indexed`) using the `UploadResponse` model. All temporary files are removed in a `finally` block and errors are returned as appropriate `HTTPException`s with helpful messages.

---

## Evaluation Criteria

Ensure you evaluate your solution against the below criteria:

1. Multi-Modal Table Processing: Markdown tables are extracted, summarized, and indexed as separate nodes with `content_type="table_summary"`.
2. Multi-Modal Image Processing: PDF images are extracted, captioned, and indexed as separate nodes with `content_type="image_caption"`.
3. Metadata Preservation: Each node preserves consistent metadata (e.g., `source`, and table/image identifiers like `table_index`, `page`, `image_index`) to support traceability.
4. Upload + Ingestion API: `POST /upload` validates inputs and triggers ingestion, returning a processing summary (once implemented).
5. End-to-End Pipeline: The ingestion pipeline processes text + tables + images and stores everything in the vector database for retrieval.
