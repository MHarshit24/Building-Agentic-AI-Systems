"""Responsible for tests covering the health API endpoint."""

from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_ok():
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["error"] is None
    assert body["request_id"]
    assert body["data"]["status"] == "ok"
    assert "llm_configured" in body["data"]
