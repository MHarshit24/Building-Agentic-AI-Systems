"""Tests for query engine creation with metadata filtering."""
import pytest
from unittest.mock import MagicMock

from main.service.query_engine import create_query_engine


class TestCreateQueryEngine:
    """Test query engine creation with optional metadata filters."""
    
    @pytest.fixture
    def mock_index(self):
        """Create a mock vector store index."""
        return MagicMock()
    
    @pytest.fixture
    def mock_llm(self):
        """Create a mock LLM."""
        return MagicMock()

    def test_create_query_engine_without_filters(self, mock_index, mock_llm):
        qe = create_query_engine(mock_index, mock_llm, similarity_top_k=2)
        assert qe is not None
        mock_index.as_query_engine.assert_called_once()

    def test_create_query_engine_with_dict_filters(self, mock_index, mock_llm):
        qe = create_query_engine(
            mock_index,
            mock_llm,
            similarity_top_k=3,
            filters={"meal_type": "breakfast"},
        )
        assert qe is not None
        mock_index.as_query_engine.assert_called_once()
