"""Tests for semantic chunking."""
import pytest
from unittest.mock import MagicMock, patch, PropertyMock

from main.service.semantic_chunking import SemanticChunker
from llama_index.core.schema import TextNode


class TestSemanticChunker:
    """Test semantic chunking functionality."""
    
    @pytest.fixture
    def mock_embed_model(self):
        """Create a mock embedding model."""
        mock = MagicMock()
        mock.dimension = 1536
        return mock
    
    @pytest.fixture
    def chunker(self, mock_embed_model):
        """Create a SemanticChunker instance."""
        with patch("main.service.semantic_chunking.SemanticSplitterNodeParser") as mock_parser_class:
            mock_parser = MagicMock()
            mock_parser_class.return_value = mock_parser
            chunker = SemanticChunker(mock_embed_model)
            # Ensure parser is the mocked one
            chunker.parser = mock_parser
            yield chunker
    
    @patch("main.service.semantic_chunking.SemanticSplitterNodeParser")
    def test_chunker_initialization(self, mock_parser_class, mock_embed_model):
        """Test chunker initialization."""
        mock_parser = MagicMock()
        mock_parser_class.return_value = mock_parser
        chunker = SemanticChunker(mock_embed_model)
        assert chunker.embed_model == mock_embed_model
        assert chunker.parser is not None
    
    def test_process_empty_text(self, chunker):
        """Test processing empty text."""
        nodes = chunker.process("")
        assert nodes == []
    
    def test_process_text(self, chunker):
        """Test processing text content."""
        mock_nodes = [
            TextNode(text="Chunk 1", metadata={"content_type": "text"}),
            TextNode(text="Chunk 2", metadata={"content_type": "text"})
        ]
        chunker.parser.get_nodes_from_documents.return_value = mock_nodes
        
        text = "This is a sample text about healthy breakfast options."
        metadata = {"source": "test.pdf", "meal_type": "breakfast"}
        
        nodes = chunker.process(text, metadata)
        
        assert len(nodes) == 2
        assert all(node.metadata.get("content_type") == "text" for node in nodes)
        assert all(node.metadata.get("source") == "test.pdf" for node in nodes)
        assert all(node.metadata.get("meal_type") == "breakfast" for node in nodes)
    
    def test_process_with_metadata(self, chunker):
        """Test processing with additional metadata."""
        mock_nodes = [TextNode(text="Chunk", metadata={})]
        chunker.parser.get_nodes_from_documents.return_value = mock_nodes
        
        metadata = {
            "source": "breakfast_recipes.pdf",
            "meal_type": "breakfast",
            "dietary_restriction": "vegetarian"
        }
        
        nodes = chunker.process("Sample text", metadata)
        
        assert len(nodes) == 1
        assert nodes[0].metadata["content_type"] == "text"
        assert nodes[0].metadata["meal_type"] == "breakfast"
        assert nodes[0].metadata["dietary_restriction"] == "vegetarian"
