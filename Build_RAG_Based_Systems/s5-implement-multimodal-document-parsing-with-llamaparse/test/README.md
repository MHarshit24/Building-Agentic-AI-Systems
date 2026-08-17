# Test Suite for Diet Counselling Assistant

This directory contains comprehensive test cases for the Personal Diet Counselling Assistant.

## Test Files

- **test_indexing.py**: Tests for metadata extraction, file metadata, LLM configuration, and vector store creation
- **test_semantic_chunking.py**: Tests for semantic text chunking functionality
- **test_table_extraction.py**: Tests for table extraction and processing
- **test_image_extraction.py**: Tests for image extraction and captioning
- **test_query_engine.py**: Tests for query engine with metadata filtering
- **test_rag_service.py**: Tests for the main RAG service orchestrator
- **test_routes.py**: Tests for FastAPI routes and endpoints
- **conftest.py**: Pytest configuration and shared fixtures

## Running Tests

**Important**: Always use `uv run python -m pytest` to ensure tests run with the correct Python version (3.12) and virtual environment.

### Run all tests:

```bash
uv run python -m pytest
```

### Run with verbose output:

```bash
uv run python -m pytest -v
```

### Run specific test file:

```bash
uv run python -m pytest test/test_indexing.py
```

### Run specific test class:

```bash
uv run python -m pytest test/test_indexing.py::TestMetadataExtraction
```

### Run with coverage:

```bash
uv run python -m pytest --cov=main --cov-report=html
```

### Install dev dependencies (if needed):

```bash
uv sync --dev
# Or manually:
uv pip install pytest pytest-asyncio pytest-cov pytest-mock httpx
```

## Test Coverage

The test suite covers:

1. **Metadata Extraction**: Filename-based diet metadata extraction
2. **Document Processing**: Multi-modal content processing (text, tables, images)
3. **Query Engine**: Querying with and without metadata filters
4. **API Endpoints**: All REST API endpoints with various scenarios
5. **Error Handling**: Invalid inputs, missing configurations, etc.

## Mocking

Tests use extensive mocking to avoid:

- Actual Azure OpenAI API calls
- Real PostgreSQL database connections
- LlamaParse API calls
- File system operations (where possible)

This ensures tests run quickly and don't require external services.

## Environment Variables

Test environment variables are set in `conftest.py`. These are automatically loaded before tests run and don't require a `.env` file for testing.
