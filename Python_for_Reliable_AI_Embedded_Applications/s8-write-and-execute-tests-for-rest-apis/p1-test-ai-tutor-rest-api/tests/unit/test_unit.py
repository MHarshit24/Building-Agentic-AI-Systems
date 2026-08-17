import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from app.main import app, limiter

client = TestClient(app)


# ------------------------------------------------------------
# Reset rate limiter before every test
# ------------------------------------------------------------
@pytest.fixture(autouse=True)
def reset_rate_limit():
    limiter.reset()


# ============================================================
# 1. /explain — SUCCESS
# ============================================================

@pytest.mark.unit
@patch("app.main.client.models.generate_content")
def test_explain_success(mock_generate):

    mock_response = MagicMock()
    mock_response.text = "Mocked structured explanation"
    mock_generate.return_value = mock_response

    payload = {
        "concept": "Artificial Intelligence",
        "level": "beginner"
    }

    response = client.post("/explain", json=payload)

    assert response.status_code == 200

    data = response.json()
    assert data["concept"] == "Artificial Intelligence"
    assert data["explanation"] == "Mocked structured explanation"
    assert "Cloud Model" in data["model_used"]
    assert data["confidence"] == 0.95


# ============================================================
# 2. /explain — LLM FAILURE
# ============================================================

@pytest.mark.unit
@patch("app.main.client.models.generate_content")
def test_explain_llm_failure(mock_generate):

    mock_generate.side_effect = Exception("Gemini crashed")

    payload = {
        "concept": "AI",
        "level": "beginner"
    }

    response = client.post("/explain", json=payload)

    assert response.status_code == 500
    assert "Error generating explanation" in response.json()["detail"]


# ============================================================
# 3. /personalize — SUCCESS
# ============================================================

@pytest.mark.unit
@patch("app.main.requests.post")
def test_personalize_success(mock_post):

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "response": "Mocked creative explanation"
    }

    mock_post.return_value = mock_response

    payload = {
        "concept": "Machine Learning",
        "level": "intermediate"
    }

    response = client.post("/personalize", json=payload)

    assert response.status_code == 200

    data = response.json()
    assert data["concept"] == "Machine Learning"
    assert data["explanation"] == "Mocked creative explanation"
    assert data["model_used"] == "Local Model: phi3:mini"
    assert data["confidence"] == 0.85


# ============================================================
# 4. /personalize — LOCAL MODEL FAILURE
# ============================================================

@pytest.mark.unit
@patch("app.main.requests.post")
def test_personalize_local_error(mock_post):

    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Ollama failed"

    mock_post.return_value = mock_response

    payload = {
        "concept": "Deep Learning",
        "level": "advanced"
    }

    response = client.post("/personalize", json=payload)

    # Because HTTPException(503) gets caught and converted to 500
    assert response.status_code == 500


# ============================================================
# 5. /personalize — EXCEPTION
# ============================================================

@pytest.mark.unit
@patch("app.main.requests.post")
def test_personalize_exception(mock_post):

    mock_post.side_effect = Exception("Connection error")

    payload = {
        "concept": "Neural Networks",
        "level": "beginner"
    }

    response = client.post("/personalize", json=payload)

    assert response.status_code == 500


# ============================================================
# 6. /explain/stream — SUCCESS
# ============================================================

@pytest.mark.unit
@patch("app.main.client.models.generate_content_stream")
def test_stream_explain_success(mock_stream):

    chunk1 = MagicMock()
    chunk1.text = "Hello "

    chunk2 = MagicMock()
    chunk2.text = "World"

    mock_stream.return_value = [chunk1, chunk2]

    payload = {
        "concept": "AI",
        "level": "beginner"
    }

    response = client.post("/explain/stream", json=payload)

    assert response.status_code == 200
    assert "Hello World" in response.text


# ============================================================
# 7. /personalize/stream — SUCCESS
# ============================================================

@pytest.mark.unit
@patch("app.main.requests.post")
def test_stream_personalize_success(mock_post):

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.iter_lines.return_value = [
        b'{"response": "Part1 "}',
        b'{"response": "Part2"}'
    ]

    mock_post.return_value.__enter__.return_value = mock_response

    payload = {
        "concept": "AI",
        "level": "beginner"
    }

    response = client.post("/personalize/stream", json=payload)

    assert response.status_code == 200
    assert "Part1 Part2" in response.text


# ============================================================
# 8. Validation Error
# ============================================================

@pytest.mark.unit
def test_validation_error():

    # Missing required field 'concept'
    payload = {
        "level": "beginner"
    }

    response = client.post("/explain", json=payload)

    assert response.status_code == 422