"""
Tests for embedding setup and vector database operations.
"""

import os
import sys
import pytest
from unittest.mock import MagicMock, Mock, patch, call
from langchain_core.documents import Document

# Add parent directory to path to import main modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from main.embedding_setup import (
    normalize_db_url,
    check_database_connection,
    initialize_embeddings,
    create_vectorstore,
    insert_sample_data,
    read_all_embeddings,
    perform_similarity_search,
)


class TestNormalizeDbUrl:
    """Test database URL normalization."""

    def test_normalize_psycopg2_url(self):
        """Test normalization of psycopg2 URL."""
        url = "postgresql+psycopg2://user:pass@host:5432/db"
        result = normalize_db_url(url)
        assert result == "postgresql://user:pass@host:5432/db"

    def test_normalize_psycopg_url(self):
        """Test normalization of psycopg URL."""
        url = "postgresql+psycopg://user:pass@host:5432/db"
        result = normalize_db_url(url)
        assert result == "postgresql://user:pass@host:5432/db"

    def test_normalize_already_normal_url(self):
        """Test that already normalized URL remains unchanged."""
        url = "postgresql://user:pass@host:5432/db"
        result = normalize_db_url(url)
        assert result == url


class TestTestDatabaseConnection:
    """Test database connection and PgVector extension check."""

    @patch("main.embedding_setup.psycopg2.connect")
    def test_database_connection_success_with_extension(self, mock_connect, mock_config):
        """Test successful database connection when extension exists."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=None)
        
        mock_cursor.fetchone.side_effect = [
            ("PostgreSQL 14.0, compiled by...",),  # version query
            ("vector",),  # extension exists
        ]
        
        result = check_database_connection(mock_config["database_url"])
        assert result is True
        assert mock_cursor.execute.call_count == 2

    @patch("main.embedding_setup.psycopg2.connect")
    def test_database_connection_success_creates_extension(self, mock_connect, mock_config):
        """Test successful database connection when extension needs to be created."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=None)
        
        mock_cursor.fetchone.side_effect = [
            ("PostgreSQL 14.0, compiled by...",),  # version query
            None,  # extension doesn't exist
        ]
        
        result = check_database_connection(mock_config["database_url"])
        assert result is True
        assert mock_cursor.execute.call_count == 3  # version, check, create

    @patch("main.embedding_setup.psycopg2.connect")
    def test_database_connection_failure(self, mock_connect, mock_config):
        """Test database connection failure handling."""
        mock_connect.side_effect = Exception("Connection failed")
        
        result = check_database_connection(mock_config["database_url"])
        assert result is False


class TestInitializeEmbeddings:
    """Test Azure OpenAI embeddings initialization."""

    @patch("main.embedding_setup.AzureOpenAIEmbeddings")
    def test_initialize_embeddings_success(self, mock_embeddings_class, mock_config):
        """Test successful embeddings initialization."""
        mock_embeddings = MagicMock()
        mock_embeddings_class.return_value = mock_embeddings
        
        result = initialize_embeddings(mock_config)
        
        assert result == mock_embeddings
        mock_embeddings_class.assert_called_once_with(
            azure_endpoint=mock_config["azure_endpoint"],
            azure_deployment=mock_config["azure_embedding_deployment"],
            api_key=mock_config["azure_api_key"],
            api_version=mock_config["api_version"],
        )

    def test_initialize_embeddings_missing_deployment(self, mock_config):
        """Test that missing deployment raises ValueError."""
        mock_config.pop("azure_embedding_deployment")
        
        with pytest.raises(ValueError, match="Missing Azure embedding deployment"):
            initialize_embeddings(mock_config)

    @patch("main.embedding_setup.AzureOpenAIEmbeddings")
    def test_initialize_embeddings_initialization_error(self, mock_embeddings_class, mock_config):
        """Test that initialization errors are raised."""
        mock_embeddings_class.side_effect = Exception("Initialization failed")
        
        with pytest.raises(Exception, match="Initialization failed"):
            initialize_embeddings(mock_config)


class TestCreateVectorstore:
    """Test PGVector store creation."""

    @patch("main.embedding_setup.PGVector")
    def test_create_vectorstore_success(self, mock_pgvector_class, mock_config, mock_embeddings):
        """Test successful vectorstore creation."""
        mock_vectorstore = MagicMock()
        mock_pgvector_class.return_value = mock_vectorstore
        
        result = create_vectorstore(mock_config, mock_embeddings)
        
        assert result == mock_vectorstore
        mock_pgvector_class.assert_called_once_with(
            embeddings=mock_embeddings,
            collection_name=mock_config["collection_name"],
            connection=mock_config["database_url"],
        )

    @patch("main.embedding_setup.PGVector")
    def test_create_vectorstore_failure(self, mock_pgvector_class, mock_config, mock_embeddings):
        """Test vectorstore creation failure handling."""
        mock_pgvector_class.side_effect = Exception("Creation failed")
        
        result = create_vectorstore(mock_config, mock_embeddings)
        
        assert result is None


class TestInsertSampleData:
    """Test sample data insertion."""

    def test_insert_sample_data_success(self, mock_vectorstore):
        """Test successful sample data insertion."""
        sample_sentences = [
            "Test sentence 1",
            "Test sentence 2",
            "Test sentence 3",
        ]
        
        result = insert_sample_data(mock_vectorstore, sample_sentences)
        
        assert result == ["id1", "id2", "id3", "id4", "id5"]
        assert mock_vectorstore.add_documents.called
        call_args = mock_vectorstore.add_documents.call_args[0][0]
        assert len(call_args) == 3
        assert all(isinstance(doc, Document) for doc in call_args)
        assert call_args[0].page_content == "Test sentence 1"
        assert call_args[0].metadata["id"] == "doc_1"

    def test_insert_sample_data_failure(self, mock_vectorstore):
        """Test sample data insertion failure handling."""
        mock_vectorstore.add_documents.side_effect = Exception("Insert failed")
        sample_sentences = ["Test sentence 1"]
        
        result = insert_sample_data(mock_vectorstore, sample_sentences)
        
        assert result == []

    def test_insert_sample_data_metadata_structure(self, mock_vectorstore):
        """Test that inserted documents have correct metadata structure."""
        sample_sentences = ["Test sentence 1"]
        
        insert_sample_data(mock_vectorstore, sample_sentences)
        
        call_args = mock_vectorstore.add_documents.call_args[0][0]
        doc = call_args[0]
        assert "document" in doc.metadata
        assert "section" in doc.metadata
        assert "page" in doc.metadata
        assert "id" in doc.metadata


class TestReadAllEmbeddings:
    """Test reading embeddings from database."""

    @patch("main.embedding_setup.psycopg2.connect")
    def test_read_all_embeddings_success(self, mock_connect, mock_config):
        """Test successful reading of embeddings."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=None)
        
        mock_cursor.fetchall.return_value = [
            ("id1", "Test document 1", {"document": "Test Doc", "id": "doc_1"}),
            ("id2", "Test document 2", {"document": "Test Doc", "id": "doc_2"}),
        ]
        
        result = read_all_embeddings(mock_config)
        
        assert len(result) == 2
        assert result[0][0] == "id1"
        assert result[0][1] == "Test document 1"

    @patch("main.embedding_setup.psycopg2.connect")
    def test_read_all_embeddings_failure(self, mock_connect, mock_config):
        """Test reading embeddings failure handling."""
        mock_connect.side_effect = Exception("Connection failed")
        
        result = read_all_embeddings(mock_config)
        
        assert result == []

    @patch("main.embedding_setup.psycopg2.connect")
    def test_read_all_embeddings_query_execution(self, mock_connect, mock_config):
        """Test that correct SQL query is executed."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=None)
        
        mock_cursor.fetchall.return_value = []
        
        read_all_embeddings(mock_config)
        
        assert mock_cursor.execute.called
        call_args = mock_cursor.execute.call_args
        assert "langchain_pg_embedding" in call_args[0][0]
        assert "collection_id" in call_args[0][0]
        assert call_args[0][1] == (mock_config["collection_name"],)


class TestPerformSimilaritySearch:
    """Test similarity search functionality."""

    def test_perform_similarity_search_success(self, mock_vectorstore):
        """Test successful similarity search."""
        perform_similarity_search(mock_vectorstore, "test query", top_k=2)
        
        mock_vectorstore.similarity_search_with_score.assert_called_once_with("test query", k=2)

    def test_perform_similarity_search_no_results(self, mock_vectorstore):
        """Test similarity search with no results."""
        mock_vectorstore.similarity_search_with_score.return_value = []
        
        # Should not raise exception, just log warning
        perform_similarity_search(mock_vectorstore, "test query")
        
        mock_vectorstore.similarity_search_with_score.assert_called_once()

    def test_perform_similarity_search_default_top_k(self, mock_vectorstore):
        """Test that default top_k is 3."""
        perform_similarity_search(mock_vectorstore, "test query")
        
        mock_vectorstore.similarity_search_with_score.assert_called_once_with("test query", k=3)

    def test_perform_similarity_search_custom_top_k(self, mock_vectorstore):
        """Test similarity search with custom top_k."""
        perform_similarity_search(mock_vectorstore, "test query", top_k=5)
        
        mock_vectorstore.similarity_search_with_score.assert_called_once_with("test query", k=5)

    def test_perform_similarity_search_failure(self, mock_vectorstore):
        """Test similarity search failure handling."""
        mock_vectorstore.similarity_search_with_score.side_effect = Exception("Search failed")
        
        # Should not raise exception, just log error
        perform_similarity_search(mock_vectorstore, "test query")
        
        mock_vectorstore.similarity_search_with_score.assert_called_once()

