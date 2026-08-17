from fastapi.testclient import TestClient
from app.main import app
from unittest.mock import patch

client = TestClient(app)


def test_root():
    response = client.get("/")
    assert response.status_code == 200

@patch("app.services.code_analysis_service.call_gemini")
def test_analyze_code(mock_gemini, client):

    mock_gemini.return_value = '''
    {
        "code_summary": "Adds two numbers",
        "detected_issues": [],
        "improvements": [],
        "best_practices": []
    }
    '''

    payload = {
        "code": "def add(a,b): return a+b",
        "language": "python",
        "experience_level": "beginner"
    }

    response = client.post("/analyze-code", json=payload)

    assert response.status_code == 200


@patch("app.services.code_analysis_service.call_gemini")
def test_explain_code(mock_gemini, client):

    mock_gemini.return_value = '''
    {
        "explanation": "Loop explanation",
        "complexity_level": "beginner",
        "key_concepts": ["loop"]
    }
    '''

    payload = {
        "code": "for i in range(5): print(i)",
        "language": "python",
        "experience_level": "beginner"
    }

    response = client.post("/explain-code", json=payload)

    assert response.status_code == 200


# Pydantic should reject empty code.
def test_analyze_code_invalid(client):

    payload = {
        "code": "",
        "language": "python",
        "experience_level": "beginner"
    }

    response = client.post("/analyze-code", json=payload)

    assert response.status_code == 422

def test_feedback_route(client):

    payload = {
        "code": "print('hi')",
        "rating": 5,
        "comment": "nice"
    }

    response = client.post("/feedback", json=payload)

    assert response.status_code == 200


def test_feedback_invalid_rating(client):

    payload = {
        "code": "print('hi')",
        "rating": 10,   # invalid
        "comment": "bad"
    }

    response = client.post("/feedback", json=payload)

    assert response.status_code == 422