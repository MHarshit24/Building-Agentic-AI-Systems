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
# 1. /explain — Integration Test
# ============================================================

@pytest.mark.integration
@patch("app.main.client.models.generate_content")
def test_explain_integration(mock_generate):

    mock_response = MagicMock()
    mock_response.text = "Integration explanation"
    mock_generate.return_value = mock_response

    payload = {
        "concept": "Artificial Intelligence",
        "level": "beginner"
    }

    response = client.post("/explain", json=payload)

    assert response.status_code == 200

    data = response.json()
    assert data["concept"] == "Artificial Intelligence"
    assert data["explanation"] == "Integration explanation"
    assert "Cloud Model" in data["model_used"]
    assert data["confidence"] == 0.95


# ============================================================
# 2. /personalize — Integration Test
# ============================================================

@pytest.mark.integration
@patch("app.main.requests.post")
def test_personalize_integration(mock_post):

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "response": "Creative integration explanation"
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
    assert data["explanation"] == "Creative integration explanation"
    assert data["model_used"] == "Local Model: phi3:mini"
    assert data["confidence"] == 0.85


# ============================================================
# 3. /explain/stream — Integration Test
# ============================================================

@pytest.mark.integration
@patch("app.main.client.models.generate_content_stream")
def test_stream_explain_integration(mock_stream):

    chunk1 = MagicMock()
    chunk1.text = "Stream "

    chunk2 = MagicMock()
    chunk2.text = "Test"

    mock_stream.return_value = [chunk1, chunk2]

    payload = {
        "concept": "AI",
        "level": "beginner"
    }

    response = client.post("/explain/stream", json=payload)

    assert response.status_code == 200
    assert "Stream Test" in response.text


# ============================================================
# 4. /personalize/stream — Integration Test
# ============================================================

@pytest.mark.integration
@patch("app.main.requests.post")
def test_stream_personalize_integration(mock_post):

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.iter_lines.return_value = [
        b'{"response": "PartA "}',
        b'{"response": "PartB"}'
    ]

    mock_post.return_value.__enter__.return_value = mock_response

    payload = {
        "concept": "AI",
        "level": "beginner"
    }

    response = client.post("/personalize/stream", json=payload)

    assert response.status_code == 200
    assert "PartA PartB" in response.text


# ============================================================
# 5. Rate Limiting Test
# ============================================================

@pytest.mark.integration
@patch("app.main.client.models.generate_content")
def test_rate_limiting(mock_generate):

    mock_response = MagicMock()
    mock_response.text = "Rate limit test"
    mock_generate.return_value = mock_response

    payload = {
        "concept": "AI",
        "level": "beginner"
    }

    # 3 allowed
    client.post("/explain", json=payload)
    client.post("/explain", json=payload)
    client.post("/explain", json=payload)

    # 4th should fail
    response = client.post("/explain", json=payload)

    assert response.status_code == 429