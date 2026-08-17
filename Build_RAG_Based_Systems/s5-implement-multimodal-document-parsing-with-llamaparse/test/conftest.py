"""Pytest configuration and fixtures for diet counselling assistant tests."""
import pytest
import os
from pathlib import Path

# Set test environment variables
# Azure OpenAI Configuration
os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
os.environ.setdefault("AZURE_OPENAI_API_KEY", "test-key")
os.environ.setdefault("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
os.environ.setdefault("AZURE_OPENAI_LLM_DEPLOYMENT", "gpt-4o-mini")
os.environ.setdefault("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-small")

# PostgreSQL Database Configuration
os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "5432")
os.environ.setdefault("DB_USER", "user")
os.environ.setdefault("DB_PASSWORD", "password")
os.environ.setdefault("DB_NAME", "rag_db")
os.environ.setdefault("DB_TABLE_NAME", "company_policies")

# LlamaCloud API Key
os.environ.setdefault("LLAMA_CLOUD_API_KEY", "llx-test-key")


@pytest.fixture
def test_data_dir():
    """Return path to test data directory."""
    return Path(__file__).parent / "data"


@pytest.fixture
def sample_pdf_path(test_data_dir):
    """Return path to sample PDF file."""
    return test_data_dir / "sample.pdf"
