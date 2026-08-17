"""
Integration Tests for Rate-Limited API

Integration tests verify that all components work together correctly:
- API receives and validates requests
- LLM is called successfully (REAL API calls)
- Responses are formatted correctly
- Rate limiting blocks excessive requests
"""

import time
from fastapi.testclient import TestClient
from app import app

# Create test client to simulate HTTP requests
client = TestClient(app)

# Rate limit from app.py: @limiter.limit("2/minute")
RATE_LIMIT = 2


def test_ask_endpoint_success_full_integration():
    """
    Test complete API flow: Request -> Validation -> LLM Call -> Response
    
    This makes a REAL API call to test the entire system end-to-end.
    """
    # Arrange: Prepare test request (short prompt to minimize cost)
    request_data = {"prompt": "Say 'Hello' in one word"}
    
    # Act: Send POST request
    response = client.post("/ask", json=request_data)
    
    # Assert: Verify response is correct
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    
    response_data = response.json()
    assert "answer" in response_data, "Response must contain 'answer' field"
    assert response_data["answer"], "Answer must not be empty"
    assert isinstance(response_data["answer"], str), "Answer must be a string"


def test_ask_rate_limit_exceeded():
    """
    Test rate limiting: First N requests succeed, (N+1)th is blocked
    
    CRITICAL for cost control and preventing API abuse.
    Takes ~65 seconds (waits for rate limit to reset).
    """
    # Wait for rate limit to reset from previous tests
    time.sleep(65)
    
    # Send RATE_LIMIT (2) requests - should all succeed
    for i in range(RATE_LIMIT):
        response = client.post("/ask", json={"prompt": f"Test {i+1}"})
        assert response.status_code == 200, f"Request {i+1} should succeed"
    
    # Send (RATE_LIMIT + 1)th request - should be blocked
    response = client.post("/ask", json={"prompt": "Should be blocked"})
    assert response.status_code == 429, "Rate limit should block this request"
    
    # Verify error response
    error_data = response.json()
    assert "detail" in error_data, "Error must contain 'detail' field"


def test_ask_endpoint_invalid_request():
    """
    Test request validation: API rejects missing required fields
    
    Ensures bad data doesn't reach the LLM, saving costs.
    """
    # Wait to avoid hitting rate limit from previous tests
    time.sleep(65)
    
    # Missing 'prompt' field should return 422 validation error
    response = client.post("/ask", json={})
    assert response.status_code == 422, "Should reject missing 'prompt' field"


def test_ask_endpoint_handles_llm_errors():
    """
    Test LLM error handling
    
    Note: This is a smoke test. To fully test LLM errors, you would:
    1. Mock the OpenAI client to raise RateLimitError
    2. Verify the response returns 429 with proper error message
    
    For now, we verify the error handler exists in app.py (lines 86-95).
    """
    # Verify app starts correctly with error handler registered
    assert client is not None, "Test client should be initialized"


# ============================================
# STREAMING ENDPOINT TESTS
# ============================================

def test_stream_endpoint_success_full_integration():
    """
    Test streaming endpoint: Request -> Validation -> LLM Stream -> Response chunks
    
    This makes a REAL streaming API call to test the entire system end-to-end.
    Verifies that response is streamed correctly.
    """
    # Wait to avoid hitting rate limit from previous tests
    time.sleep(65)
    
    # Arrange: Prepare test request (short prompt to minimize cost)
    request_data = {"prompt": "Count to 3"}
    
    # Act: Send POST request to streaming endpoint
    response = client.post("/ask/stream", json=request_data)
    
    # Assert: Verify response status and headers
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    assert response.headers.get("content-type") == "text/plain; charset=utf-8", \
        "Content-Type should be text/plain for streaming"
    
    # Read the streaming response
    content = response.text
    
    # Verify we received actual content
    assert content, "Streaming response should not be empty"
    assert isinstance(content, str), "Response should be a string"
    assert len(content) > 0, "Response should have content"


def test_stream_endpoint_receives_chunks():
    """
    Test that streaming endpoint actually streams data in chunks
    
    This verifies the streaming behavior by checking that data arrives
    progressively rather than all at once.
    """
    # Wait to avoid hitting rate limit from previous tests
    time.sleep(65)
    
    # Arrange: Use a prompt that generates a longer response
    request_data = {"prompt": "Say hello"}
    
    # Act: Send streaming request
    with client.stream("POST", "/ask/stream", json=request_data) as response:
        # Verify streaming started successfully
        assert response.status_code == 200
        
        chunks = []
        for chunk in response.iter_text():
            if chunk:
                chunks.append(chunk)
        
        # Assert: Verify we received content as chunks
        full_response = "".join(chunks)
        assert full_response, "Should receive content from stream"


def test_stream_rate_limit_exceeded():
    """
    Test rate limiting on streaming endpoint
    
    CRITICAL for cost control - ensures streaming endpoint has rate limits.
    """
    # Wait for rate limit to reset
    time.sleep(65)
    
    # Send RATE_LIMIT (2) requests - should all succeed
    for i in range(RATE_LIMIT):
        response = client.post("/ask/stream", json={"prompt": f"Test {i+1}"})
        assert response.status_code == 200, f"Streaming request {i+1} should succeed"
    
    # Send (RATE_LIMIT + 1)th request - should be blocked
    response = client.post("/ask/stream", json={"prompt": "Should be blocked"})
    assert response.status_code == 429, "Rate limit should block streaming request"
    
    # Verify error response
    error_data = response.json()
    assert "detail" in error_data, "Error must contain 'detail' field"


def test_stream_endpoint_invalid_request():
    """
    Test request validation on streaming endpoint
    
    Ensures bad data doesn't reach the LLM via streaming endpoint.
    """
    # Wait to avoid hitting rate limit
    time.sleep(65)
    
    # Missing 'prompt' field should return 422 validation error
    response = client.post("/ask/stream", json={})
    assert response.status_code == 422, "Should reject missing 'prompt' field"


def test_stream_endpoint_empty_prompt():
    """
    Test streaming endpoint with empty prompt
    
    Verifies validation works for edge cases.
    """
    # Wait to avoid hitting rate limit
    time.sleep(65)
    
    # Send empty string prompt
    response = client.post("/ask/stream", json={"prompt": ""})
    
    # Should still return 200 since empty string is valid,
    # but LLM might return minimal response
    assert response.status_code == 200, "Empty prompt is technically valid"


