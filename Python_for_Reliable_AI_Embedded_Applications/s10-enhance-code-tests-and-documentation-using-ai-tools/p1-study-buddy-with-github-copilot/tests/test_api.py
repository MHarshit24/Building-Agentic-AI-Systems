"""
Unit Tests for AI Tutor API

This module contains comprehensive unit tests for the FastAPI AI Tutor application.
Tests cover the root endpoint and explanation endpoint with mocked Gemini API calls.

Features:
    - Test root endpoint (GET /) for API information
    - Test /explain endpoint with successful explanations
    - Test /explain endpoint with API errors
    - Test /explain endpoint with validation errors
    - Mock OpenAI/Gemini API calls to avoid real API calls
    - Use FastAPI TestClient for testing
"""
import sys
import os

os.environ["TESTING"] = "true"
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient
from openai import APIError

# Import the FastAPI app from the main module
from app.main import app


@pytest.fixture
def client():
    """
    Fixture that provides a TestClient instance for testing the FastAPI app.
    
    The TestClient allows us to make test requests to the app without running
    a live server. It handles request/response cycle simulation.
    
    Returns:
        TestClient: A test client instance for the FastAPI app.
    """
    return TestClient(app)


class TestRootEndpoint:
    """
    Test suite for the root endpoint (GET /).
    
    The root endpoint returns API metadata including name, version, description,
    and links to documentation.
    """
    
    def test_root_endpoint_returns_200(self, client):
        """
        Test that GET / returns a 200 OK status code.
        
        This verifies that the root endpoint is accessible and responds successfully.
        """
        response = client.get("/")
        assert response.status_code == 200
    
    def test_root_endpoint_returns_api_metadata(self, client):
        """
        Test that GET / returns correct API metadata.
        
        Verifies that the response contains the expected structure including
        API name, version, description, and endpoint information.
        """
        response = client.get("/")
        data = response.json()
        
        # Check that all required fields are present
        assert "name" in data
        assert "version" in data
        assert "description" in data
        assert "documentation" in data
        assert "endpoints" in data
        
        # Verify specific values
        assert data["name"] == "AI Tutor API"
        assert data["version"] == "2.0.0"
        assert data["description"] == "Personalized Learning with Cloud AI Models"
    
    def test_root_endpoint_includes_documentation_links(self, client):
        """
        Test that GET / includes documentation links.
        
        Verifies that the response includes links to interactive documentation
        (Swagger/OpenAPI) and ReDoc documentation.
        """
        response = client.get("/")
        data = response.json()
        
        documentation = data["documentation"]
        assert "interactive" in documentation
        assert "redoc" in documentation
        assert documentation["interactive"] == "/docs"
        assert documentation["redoc"] == "/redoc"
    
    def test_root_endpoint_includes_endpoints_list(self, client):
        """
        Test that GET / includes a list of available endpoints.
        
        Verifies that the response includes the /explain and /explain/stream endpoints.
        """
        response = client.get("/")
        data = response.json()
        
        endpoints = data["endpoints"]
        assert "explain" in endpoints
        assert "explain/stream" in endpoints
        assert endpoints["explain"] == "/explain"
        assert endpoints["explain/stream"] == "/explain/stream"


class TestExplainEndpoint:
    """
    Test suite for the POST /explain endpoint.
    
    This endpoint accepts a concept and returns a full explanation from the AI model.
    """
    
    def test_explain_endpoint_returns_200_with_valid_concept(self, client):
        """
        Test that POST /explain returns 200 OK with a valid concept.
        
        This test mocks the Gemini API call and verifies that a successful
        explanation request returns the correct status code.
        """
        # Mock the Gemini API response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "RAG is a technique that combines retrieval with generation..."
        
        with patch("app.main.CLOUD_CLIENT.chat.completions.create", return_value=mock_response):
            response = client.post(
                "/explain",
                json={"concept": "RAG"}
            )
            assert response.status_code == 200
    
    def test_explain_endpoint_returns_explanation_response_structure(self, client):
        """
        Test that POST /explain returns the correct response structure.
        
        Verifies that the response includes concept, explanation, and model fields
        as defined in the ExplanationResponse schema.
        """
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "RAG combines document retrieval with LLM generation."
        
        with patch("app.main.CLOUD_CLIENT.chat.completions.create", return_value=mock_response), \
             patch("app.main.CLOUD_MODEL", "gpt-4"):
            response = client.post(
                "/explain",
                json={"concept": "RAG"}
            )
            data = response.json()
            
            # Verify response structure
            assert "concept" in data
            assert "explanation" in data
            assert "model" in data
            
            # Verify values
            assert data["concept"] == "RAG"
            assert data["explanation"] == "RAG combines document retrieval with LLM generation."
            assert data["model"] == "gpt-4"
    
    def test_explain_endpoint_with_different_concepts(self, client):
        """
        Test that POST /explain works with different concept inputs.
        
        Verifies that the endpoint correctly processes and returns explanations
        for various concepts.
        """
        concepts = ["Agents", "Prompting", "Function Calling"]
        
        for concept in concepts:
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message.content = f"Explanation for {concept}"
            
            with patch("app.main.CLOUD_CLIENT.chat.completions.create", return_value=mock_response):
                response = client.post(
                    "/explain",
                    json={"concept": concept}
                )
                data = response.json()
                
                assert response.status_code == 200
                assert data["concept"] == concept
    
    def test_explain_endpoint_returns_500_on_api_error(self, client):
        """
        Test that POST /explain returns 500 when the Gemini API fails.
        
        This verifies that API errors (authentication, rate limits from the API, etc.)
        are properly caught and returned as HTTP 500 errors.
        """
        # Mock an API error from the Gemini API
        with patch("app.main.CLOUD_CLIENT.chat.completions.create", 
                   side_effect=Exception("API authentication failed")):
            response = client.post(
                "/explain",
                json={"concept": "RAG"}
            )
            assert response.status_code == 500
            data = response.json()
            assert "detail" in data
    
    def test_explain_endpoint_returns_500_on_general_error(self, client):
        """
        Test that POST /explain returns 500 on unexpected internal errors.
        
        This verifies that unexpected exceptions (not APIError) are caught
        and handled gracefully.
        """
        # Mock a general exception
        with patch("app.main.CLOUD_CLIENT.chat.completions.create", 
                   side_effect=ValueError("Unexpected processing error")):
            response = client.post(
                "/explain",
                json={"concept": "RAG"}
            )
            assert response.status_code == 500
    
    def test_explain_endpoint_with_empty_concept_field(self, client):
        """
        Test that POST /explain handles empty concept field gracefully.
        
        This tests input validation by attempting to send a request with
        an empty or missing concept field.
        """
        # Sending request without concept field should fail validation
        response = client.post(
            "/explain",
            json={}
        )
        # FastAPI will return 422 Unprocessable Entity for validation errors
        assert response.status_code == 422
    
    def test_explain_endpoint_with_special_characters_in_concept(self, client):
        """
        Test that POST /explain handles special characters in concepts.
        
        Verifies that the endpoint correctly processes concepts with special
        characters like hyphens, slashes, or parentheses.
        """
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Explanation of complex concept"
        
        special_concept = "Multi-Agent-Systems (MAS)"
        
        with patch("app.main.CLOUD_CLIENT.chat.completions.create", return_value=mock_response):
            response = client.post(
                "/explain",
                json={"concept": special_concept}
            )
            data = response.json()
            
            assert response.status_code == 200
            assert data["concept"] == special_concept
    
    def test_explain_endpoint_with_long_explanation(self, client):
        """
        Test that POST /explain correctly handles long explanations.
        
        Verifies that the endpoint can process and return lengthy explanations
        from the AI model without truncation or errors.
        """
        long_explanation = "A" * 5000  # 5000 character explanation
        
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = long_explanation
        
        with patch("app.main.CLOUD_CLIENT.chat.completions.create", return_value=mock_response):
            response = client.post(
                "/explain",
                json={"concept": "LongConcept"}
            )
            data = response.json()
            
            assert response.status_code == 200
            assert len(data["explanation"]) == 5000


class TestExplainStreamEndpoint:
    """
    Test suite for the POST /explain/stream endpoint.
    
    This endpoint streams explanations using Server-Sent Events (SSE).
    """
    
    def test_explain_stream_endpoint_returns_200(self, client):
        """
        Test that POST /explain/stream returns 200 OK.
        
        Verifies that the streaming endpoint is accessible and returns
        a successful response.
        """
        # Create a mock streaming response
        mock_chunk_1 = Mock()
        mock_chunk_1.choices = [Mock()]
        mock_chunk_1.choices[0].delta.content = "RAG "
        
        mock_chunk_2 = Mock()
        mock_chunk_2.choices = [Mock()]
        mock_chunk_2.choices[0].delta.content = "is "
        
        mock_chunk_3 = Mock()
        mock_chunk_3.choices = [Mock()]
        mock_chunk_3.choices[0].delta.content = "great."
        
        # Mock the stream generator
        mock_stream = [mock_chunk_1, mock_chunk_2, mock_chunk_3]
        
        with patch("app.main.CLOUD_CLIENT.chat.completions.create", return_value=mock_stream):
            response = client.post(
                "/explain/stream",
                json={"concept": "RAG"}
            )
            assert response.status_code == 200
    
    def test_explain_stream_endpoint_returns_event_stream_content_type(self, client):
        """
        Test that POST /explain/stream returns correct content-type for SSE.
        
        Verifies that the response uses the text/event-stream MIME type
        required for Server-Sent Events.
        """
        # Create mock stream
        mock_chunk = Mock()
        mock_chunk.choices = [Mock()]
        mock_chunk.choices[0].delta.content = "content"
        
        with patch("app.main.CLOUD_CLIENT.chat.completions.create", return_value=[mock_chunk]):
            response = client.post(
                "/explain/stream",
                json={"concept": "RAG"}
            )
            
            assert "text/event-stream" in response.headers["content-type"]
    
    def test_explain_stream_endpoint_includes_cache_control_headers(self, client):
        """
        Test that POST /explain/stream includes proper cache control headers.
        
        Verifies that streaming responses include headers to prevent caching
        and maintain connection persistence.
        """
        mock_chunk = Mock()
        mock_chunk.choices = [Mock()]
        mock_chunk.choices[0].delta.content = "content"
        
        with patch("app.main.CLOUD_CLIENT.chat.completions.create", return_value=[mock_chunk]):
            response = client.post(
                "/explain/stream",
                json={"concept": "RAG"}
            )
            
            assert response.headers["cache-control"] == "no-cache"
            assert response.headers["connection"] == "keep-alive"
            assert response.headers["x-accel-buffering"] == "no"
    
    def test_explain_stream_endpoint_with_error(self, client):
        """
        Test that POST /explain/stream handles errors gracefully.
        
        Verifies that streaming errors are caught and sent as error SSE events
        rather than breaking the stream.
        """
        with patch("app.main.CLOUD_CLIENT.chat.completions.create", 
                   side_effect=Exception("Streaming API error")):
            response = client.post(
                "/explain/stream",
                json={"concept": "RAG"}
            )
            
            assert response.status_code == 200
            # The error should be in the stream as an SSE event
            content = response.text
            assert "error" in content.lower()


class TestAPIIntegration:
    """
    Integration tests that verify multiple components working together.
    """
    
    def test_root_and_explain_endpoints_are_documented(self, client):
        """
        Test that the root endpoint correctly lists the /explain endpoint.
        
        This integration test verifies that the root endpoint documentation
        is consistent with available endpoints.
        """
        # Get API info
        root_response = client.get("/")
        root_data = root_response.json()
        
        # Verify explain endpoint is documented
        assert "/explain" in root_data["endpoints"].values()
        
        # Verify explain endpoint is accessible
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Explanation"
        
        with patch("app.main.CLOUD_CLIENT.chat.completions.create", return_value=mock_response):
            explain_response = client.post(
                "/explain",
                json={"concept": "Test"}
            )
            assert explain_response.status_code == 200
    
    def test_multiple_explain_requests_are_independent(self, client):
        """
        Test that multiple explain requests don't interfere with each other.
        
        Verifies that the application correctly handles sequence of requests
        without state leakage between them.
        """
        responses_data = []
        concepts = ["Concept1", "Concept2", "Concept3"]
        
        for concept in concepts:
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message.content = f"Explanation of {concept}"
            
            with patch("app.main.CLOUD_CLIENT.chat.completions.create", return_value=mock_response):
                response = client.post(
                    "/explain",
                    json={"concept": concept}
                )
                responses_data.append(response.json())
        
        # Verify each response has correct data
        for i, data in enumerate(responses_data):
            assert data["concept"] == concepts[i]
            assert concepts[i] in data["explanation"]
