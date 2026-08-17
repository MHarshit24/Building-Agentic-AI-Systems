"""Tests for RAG service."""
import pytest
from unittest.mock import MagicMock, patch, mock_open
import tempfile

from main.service.rag_service import RAGService


class TestRAGService:
    """Test RAG service functionality."""
    
    @pytest.fixture
    def rag_service(self):
        """Create a RAGService instance."""
        return RAGService()
    
    @patch("main.service.rag_service.configure_llm_and_embeddings")
    @patch("main.service.rag_service.SemanticChunker")
    def test_initialize(self, mock_chunker_class, mock_configure, rag_service):
        """Test service initialization."""
        mock_llm = MagicMock()
        mock_embed = MagicMock()
        mock_configure.return_value = (mock_llm, mock_embed)
        
        mock_chunker = MagicMock()
        mock_chunker_class.return_value = mock_chunker
        
        rag_service.initialize()
        
        assert rag_service._initialized is True
        assert rag_service.llm == mock_llm
        assert rag_service.embed_model == mock_embed
        assert rag_service.semantic_chunker == mock_chunker
    
    @patch("main.service.rag_service.create_vector_store")
    @patch("main.service.rag_service.VectorStoreIndex")
    def test_load_existing_index(self, mock_index_class, mock_vector_store, rag_service):
        """Test loading existing index."""
        rag_service._initialized = True
        rag_service.llm = MagicMock()
        rag_service.embed_model = MagicMock()
        
        mock_vector_store.return_value = MagicMock()
        mock_index = MagicMock()
        mock_index_class.from_vector_store.return_value = mock_index
        
        rag_service._load_existing_index()
        
        assert rag_service.index == mock_index
        assert rag_service.query_engine is not None
    
    @patch("main.service.rag_service.load_documents")
    @patch("main.service.rag_service.find_markdown_tables")
    @patch("main.service.rag_service.build_nodes_from_tables")
    @patch("main.service.rag_service.extract_images_from_pdf")
    @patch("main.service.rag_service.generate_caption")
    @patch("main.service.rag_service.create_vector_store")
    @patch("main.service.rag_service.VectorStoreIndex")
    @patch("main.service.rag_service.SemanticChunker")
    def test_process_document(
        self,
        mock_chunker_class,
        mock_index_class,
        mock_vector_store,
        mock_caption,
        mock_extract_images,
        mock_build_tables,
        mock_find_tables,
        mock_load_docs,
        rag_service
    ):
        """Test document processing."""
        # Setup mocks
        rag_service._initialized = True
        rag_service.llm = MagicMock()
        rag_service.embed_model = MagicMock()
        
        mock_chunker = MagicMock()
        mock_chunker.process.return_value = [
            MagicMock(text="Text chunk 1", metadata={"content_type": "text"}),
            MagicMock(text="Text chunk 2", metadata={"content_type": "text"})
        ]
        rag_service.semantic_chunker = mock_chunker
        
        # Mock document loading
        mock_load_docs.return_value = "Sample document text with tables and content."
        
        # Mock table extraction
        mock_find_tables.return_value = [
            (0, 100, "| Food | Calories |\n|------|----------|\n| Eggs | 70      |")
        ]
        mock_build_tables.return_value = [
            MagicMock(text="Table summary", metadata={"content_type": "table_summary"})
        ]
        
        # Mock image extraction
        mock_extract_images.return_value = [
            {"path": "/tmp/image1.png", "page": 0, "image_index": 0}
        ]
        mock_caption.return_value = "A healthy breakfast plate with fruits."
        
        # Mock vector store and index
        mock_vector_store.return_value = MagicMock()
        mock_index = MagicMock()
        mock_index_class.from_vector_store.side_effect = Exception("No existing index")
        mock_index_class.from_documents.return_value = mock_index
        
        # Process document
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_file:
            tmp_file.write(b"fake pdf content")
            tmp_path = tmp_file.name
        
        try:
            result = rag_service.process_document(
                tmp_path,
                original_filename="breakfast_vegetarian_recipes.pdf"
            )
            
            assert result["documents_indexed"] > 0
            assert "text_nodes" in result
            assert "table_nodes" in result
            assert "image_nodes" in result
            assert rag_service.index is not None  # Just check it's set, not exact object
        finally:
            import os
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    
    def test_query(self, rag_service):
        """Test querying the service."""
        # Mock the query engine
        mock_query_engine = MagicMock()
        mock_query_engine.query.return_value = (
            "Here are some healthy breakfast options...",
            [MagicMock()]
        )
        rag_service.query_engine = mock_query_engine
        
        answer, nodes = rag_service.query(
            "What are healthy breakfast options?",
            similarity_top_k=3,
            filters={"meal_type": "breakfast"}
        )
        
        assert answer is not None
        assert len(nodes) == 1
        mock_query_engine.query.assert_called_once_with(
            "What are healthy breakfast options?",
            similarity_top_k=3,
            filters={"meal_type": "breakfast"}
        )
    
    def test_query_not_initialized(self, rag_service):
        """Test querying when service is not initialized."""
        # Ensure service is not initialized
        rag_service.index = None
        rag_service.query_engine = None
        rag_service._index_loaded = True  # Prevent auto-loading
        
        with pytest.raises(ValueError, match="Index not initialized"):
            rag_service.query("Test question")
