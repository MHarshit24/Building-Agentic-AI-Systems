"""Tests for API routes."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
import tempfile
import os

from main.app import app


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def mock_rag_service():
    """Create a mock RAG service."""
    with patch("main.routes.routes.rag_service") as mock:
        yield mock


class TestHealthCheck:
    """Test health check endpoint."""
    
    def test_health_check(self, client, mock_rag_service):
        """Test health check endpoint."""
        mock_rag_service.is_initialized.return_value = True
        
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "Personal Diet Counselling Assistant API"
        assert data["initialized"] is True


class TestRootEndpoint:
    """Test root endpoint."""
    
    def test_root_endpoint(self, client):
        """Test root endpoint returns API information."""
        response = client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        assert "service" in data
        assert "version" in data
        assert "metadata_filters" in data
        assert "example_queries" in data


class TestUploadEndpoint:
    """Test document upload endpoint."""
    
    def test_upload_pdf(self, client, mock_rag_service):
        """Test uploading a PDF document."""
        mock_rag_service.process_document.return_value = {
            "message": "Successfully indexed 10 document chunk(s)",
            "documents_indexed": 10,
            "text_nodes": 5,
            "table_nodes": 3,
            "image_nodes": 2
        }
        
        # Create a temporary PDF file
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_file:
            tmp_file.write(b"fake pdf content")
            tmp_path = tmp_file.name
        
        try:
            with open(tmp_path, "rb") as f:
                response = client.post(
                    "/upload",
                    files={"file": ("breakfast_vegetarian_recipes.pdf", f, "application/pdf")}
                )
            
            assert response.status_code == 200
            data = response.json()
            assert data["message"] == "Successfully indexed 10 document chunk(s)"
            assert data["documents_indexed"] == 10
            mock_rag_service.process_document.assert_called_once()
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    
    def test_upload_invalid_file_type(self, client):
        """Test uploading invalid file type."""
        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as tmp_file:
            tmp_file.write(b"fake content")
            tmp_path = tmp_file.name
        
        try:
            with open(tmp_path, "rb") as f:
                response = client.post(
                    "/upload",
                    files={"file": ("test.exe", f, "application/x-msdownload")}
                )
            
            assert response.status_code == 400
            assert "not allowed" in response.json()["detail"].lower()
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    
    def test_upload_file_too_large(self, client):
        """Test uploading file that exceeds size limit."""
        # Create a large file (11MB)
        large_content = b"x" * (11 * 1024 * 1024)
        
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_file:
            tmp_file.write(large_content)
            tmp_path = tmp_file.name
        
        try:
            with open(tmp_path, "rb") as f:
                response = client.post(
                    "/upload",
                    files={"file": ("large.pdf", f, "application/pdf")}
                )
            
            assert response.status_code == 400
            assert "size" in response.json()["detail"].lower()
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    
    def test_upload_missing_file(self, client):
        """Test uploading without file."""
        response = client.post("/upload")
        assert response.status_code == 422  # Validation error


class TestQueryEndpoint:
    """Test query endpoint."""
    
    def test_query_without_filters(self, client, mock_rag_service):
        """Test querying without metadata filters."""
        mock_rag_service.query.return_value = (
            "Here are some healthy breakfast options: oatmeal, fruits, and yogurt.",
            [
                MagicMock(
                    node=MagicMock(
                        text="Oatmeal with fruits is a healthy breakfast option.",
                        metadata={"source": "breakfast_recipes.pdf", "content_type": "text"}
                    ),
                    score=0.9
                )
            ]
        )
        
        response = client.post(
            "/query",
            json={
                "question": "What are some healthy breakfast options?",
                "similarity_top_k": 3
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert "source_nodes" in data
        assert len(data["source_nodes"]) == 1
        assert data["source_nodes"][0]["metadata"]["source"] == "breakfast_recipes.pdf"
    
    def test_query_with_filters(self, client, mock_rag_service):
        """Test querying with metadata filters."""
        mock_rag_service.query.return_value = (
            "Here are vegetarian breakfast options: oatmeal, fruits, and yogurt.",
            [
                MagicMock(
                    node=MagicMock(
                        text="Vegetarian breakfast options include oatmeal and fruits.",
                        metadata={
                            "source": "breakfast_vegetarian_recipes.pdf",
                            "meal_type": "breakfast",
                            "dietary_restriction": "vegetarian",
                            "content_type": "text"
                        }
                    ),
                    score=0.95
                )
            ]
        )
        
        response = client.post(
            "/query",
            json={
                "question": "What are some healthy breakfast options?",
                "similarity_top_k": 3,
                "filters": {
                    "meal_type": "breakfast",
                    "dietary_restriction": "vegetarian"
                }
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert len(data["source_nodes"]) == 1
        assert data["source_nodes"][0]["metadata"]["meal_type"] == "breakfast"
        assert data["source_nodes"][0]["metadata"]["dietary_restriction"] == "vegetarian"
        
        # Verify service was called with filters
        # Check that query was called (may be called multiple times due to startup)
        assert mock_rag_service.query.called
        # Get the last call (most recent)
        last_call = mock_rag_service.query.call_args
        assert last_call is not None
        assert last_call[0][0] == "What are some healthy breakfast options?"  # question
        assert last_call[1]["similarity_top_k"] == 3
        assert last_call[1]["filters"] == {"meal_type": "breakfast", "dietary_restriction": "vegetarian"}
    
    def test_query_not_initialized(self, client, mock_rag_service):
        """Test querying when service is not initialized."""
        mock_rag_service.query.side_effect = ValueError("Index not initialized. Please process a document first.")
        
        response = client.post(
            "/query",
            json={
                "question": "What are healthy breakfast options?",
                "similarity_top_k": 3
            }
        )
        
        assert response.status_code == 400
        assert "no document" in response.json()["detail"].lower()
    
    def test_query_invalid_request(self, client):
        """Test querying with invalid request."""
        # Missing question
        response = client.post(
            "/query",
            json={
                "similarity_top_k": 3
            }
        )
        assert response.status_code == 422  # Validation error
        
        # Empty question
        response = client.post(
            "/query",
            json={
                "question": "",
                "similarity_top_k": 3
            }
        )
        assert response.status_code == 422
    
    def test_query_invalid_similarity_top_k(self, client):
        """Test querying with invalid similarity_top_k."""
        response = client.post(
            "/query",
            json={
                "question": "Test question",
                "similarity_top_k": 25  # Exceeds max of 20
            }
        )
        assert response.status_code == 422
    
    def test_query_question_too_long(self, client):
        """Test querying with question that exceeds max length."""
        long_question = "x" * 2001  # Exceeds max of 2000
        
        response = client.post(
            "/query",
            json={
                "question": long_question,
                "similarity_top_k": 3
            }
        )
        assert response.status_code == 422
