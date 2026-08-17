"""
Shared pytest fixtures and configuration.
"""

import os
import pytest
from unittest.mock import MagicMock, Mock
from typing import Dict, Any


@pytest.fixture
def mock_config() -> Dict[str, Any]:
    """Provide a mock configuration dictionary."""
    return {
        "database_url": "postgresql+psycopg://user:pass@localhost:5432/test_db",
        "azure_endpoint": "https://test.openai.azure.com/",
        "azure_api_key": "test-api-key",
        "azure_embedding_deployment": "text-embedding-3-small",
        "api_version": "2024-02-01",
        "collection_name": "test_collection",
    }


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Set up mock environment variables."""
    env_vars = {
        "DB_USER": "test_user",
        "DB_PASSWORD": "test_password",
        "DB_HOST": "localhost",
        "DB_PORT": "5432",
        "DB_NAME": "test_db",
        "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com/",
        "AZURE_OPENAI_API_KEY": "test-api-key",
        "AZURE_OPENAI_DEPLOYMENT": "text-embedding-3-small",
        "AZURE_OPENAI_API_VERSION": "2024-02-01",
        "COLLECTION_NAME": "test_collection",
    }
    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)
    return env_vars


@pytest.fixture
def mock_embeddings():
    """Provide a mock embeddings object."""
    mock = MagicMock()
    mock.embed_query.return_value = [0.1] * 1536
    mock.embed_documents.return_value = [[0.1] * 1536] * 5
    return mock


@pytest.fixture
def mock_vectorstore():
    """Provide a mock PGVector store."""
    mock = MagicMock()
    mock.add_documents.return_value = ["id1", "id2", "id3", "id4", "id5"]
    mock.similarity_search_with_score.return_value = [
        (
            MagicMock(
                page_content="Test content 1",
                metadata={"document": "Test Doc", "id": "doc_1"},
            ),
            0.1,
        ),
        (
            MagicMock(
                page_content="Test content 2",
                metadata={"document": "Test Doc", "id": "doc_2"},
            ),
            0.2,
        ),
    ]
    return mock


@pytest.fixture
def mock_db_connection(mocker):
    """Provide a mock database connection."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = Mock(return_value=None)
    mock_conn.__enter__ = Mock(return_value=mock_conn)
    mock_conn.__exit__ = Mock(return_value=None)
    
    mock_cursor.fetchone.return_value = ("PostgreSQL 14.0",)
    mock_cursor.fetchall.return_value = [
        ("id1", "Test document 1", {"document": "Test Doc", "id": "doc_1"}),
        ("id2", "Test document 2", {"document": "Test Doc", "id": "doc_2"}),
    ]
    
    mocker.patch("psycopg2.connect", return_value=mock_conn)
    return mock_conn

