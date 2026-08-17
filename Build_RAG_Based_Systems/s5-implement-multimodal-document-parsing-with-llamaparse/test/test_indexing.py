"""Tests for indexing and metadata extraction."""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from main.service.metadata import extract_diet_metadata_from_filename, get_file_metadata
from main.service.rag_service import configure_llm_and_embeddings, create_vector_store


class TestMetadataExtraction:
    """Test diet-specific metadata extraction from filenames."""
    
    def test_extract_breakfast_metadata(self):
        """Test extraction of breakfast meal type."""
        metadata = extract_diet_metadata_from_filename("breakfast_recipes.pdf")
        assert metadata["meal_type"] == "breakfast"
    
    def test_extract_vegetarian_metadata(self):
        """Test extraction of vegetarian dietary restriction."""
        metadata = extract_diet_metadata_from_filename("vegetarian_meals.txt")
        assert metadata["dietary_restriction"] == "vegetarian"
    
    def test_extract_multiple_metadata(self):
        """Test extraction of multiple metadata fields."""
        metadata = extract_diet_metadata_from_filename("breakfast_vegetarian_recipes.pdf")
        assert metadata["meal_type"] == "breakfast"
        assert metadata["dietary_restriction"] == "vegetarian"
        assert metadata["topic"] == "recipes"
    
    def test_extract_protein_metadata(self):
        """Test extraction of nutrition category."""
        metadata = extract_diet_metadata_from_filename("protein_nutrition_facts.pdf")
        assert metadata["nutrition_category"] == "protein"
        assert metadata["topic"] == "nutrition-facts"
    
    def test_extract_diabetic_metadata(self):
        """Test extraction of diabetic dietary restriction."""
        metadata = extract_diet_metadata_from_filename("diabetic_meal_planning.pdf")
        assert metadata["dietary_restriction"] == "diabetic"
        assert metadata["topic"] == "meal-planning"
    
    def test_no_metadata_extracted(self):
        """Test file with no matching metadata."""
        metadata = extract_diet_metadata_from_filename("generic_document.pdf")
        assert len(metadata) == 0
    
    def test_case_insensitive_extraction(self):
        """Test that extraction is case-insensitive."""
        metadata = extract_diet_metadata_from_filename("BREAKFAST_VEGETARIAN.PDF")
        assert metadata["meal_type"] == "breakfast"
        assert metadata["dietary_restriction"] == "vegetarian"
    
    def test_gluten_free_with_hyphen(self):
        """Test extraction of gluten-free with hyphen."""
        metadata = extract_diet_metadata_from_filename("gluten_free_dinner.pdf")
        assert metadata["dietary_restriction"] == "gluten-free"


class TestFileMetadata:
    """Test file metadata extraction."""
    
    @pytest.fixture
    def temp_file(self, tmp_path):
        """Create a temporary file for testing."""
        file_path = tmp_path / "breakfast_vegetarian_recipes.pdf"
        file_path.write_bytes(b"fake pdf content")
        return str(file_path)
    
    def test_get_file_metadata(self, temp_file):
        """Test getting file metadata with diet tags."""
        metadata = get_file_metadata(temp_file)
        
        assert "source" in metadata
        assert "file_path" in metadata
        assert "file_extension" in metadata
        assert "file_size" in metadata
        assert metadata["meal_type"] == "breakfast"
        assert metadata["dietary_restriction"] == "vegetarian"
        assert metadata["topic"] == "recipes"


class TestLLMConfiguration:
    """Test LLM and embedding configuration."""
    
    @patch.dict("os.environ", {
        "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com/",
        "AZURE_OPENAI_API_KEY": "test-key",
        "AZURE_OPENAI_API_VERSION": "2024-02-15-preview",
        "AZURE_OPENAI_LLM_DEPLOYMENT": "gpt-4o-mini",
        "AZURE_OPENAI_EMBEDDING_DEPLOYMENT": "text-embedding-3-small"
    })
    @patch("main.service.rag_service.AzureOpenAI")
    @patch("main.service.rag_service.AzureOpenAIEmbedding")
    def test_configure_llm_and_embeddings(self, mock_embedding, mock_llm):
        """Test LLM and embedding configuration."""
        llm, embed_model = configure_llm_and_embeddings()
        
        assert llm is not None
        assert embed_model is not None
        mock_llm.assert_called_once()
        mock_embedding.assert_called_once()
    
    @patch.dict("os.environ", {}, clear=True)
    def test_configure_missing_env_vars(self):
        """Test that missing environment variables raise error."""
        with pytest.raises(EnvironmentError):
            configure_llm_and_embeddings()


class TestVectorStore:
    """Test vector store creation."""
    
    @patch.dict("os.environ", {
        "DB_HOST": "localhost",
        "DB_PORT": "5432",
        "DB_NAME": "rag_db",
        "DB_USER": "user",
        "DB_PASSWORD": "password",
        "DB_TABLE_NAME": "test_table"
    })
    @patch("main.service.rag_service.PGVectorStore")
    def test_create_vector_store(self, mock_pgvector):
        """Test vector store creation."""
        mock_pgvector.from_params.return_value = MagicMock()
        
        vector_store = create_vector_store(embed_dim=1536)
        
        assert vector_store is not None
        mock_pgvector.from_params.assert_called_once()
    
    @patch.dict("os.environ", {
        "DB_HOST": "localhost",
        "DB_PORT": "5432",
        "DB_NAME": "rag_db",
        "DB_USER": "user",
        "DB_TABLE_NAME": "test_table"
    }, clear=True)
    def test_create_vector_store_missing_password(self):
        """Test that missing password raises error."""
        with pytest.raises(EnvironmentError):
            create_vector_store()
    
    @patch.dict("os.environ", {
        "DB_HOST": "localhost",
        "DB_PORT": "5432",
        "DB_NAME": "rag_db",
        "DB_USER": "user",
        "DB_PASSWORD": "password"
    }, clear=True)
    def test_create_vector_store_missing_table_name(self):
        """Test that missing table name raises error."""
        with pytest.raises(EnvironmentError):
            create_vector_store()
