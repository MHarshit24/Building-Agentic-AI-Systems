
from unittest.mock import patch
from app.services.llm_service import call_gemini


@patch("app.services.llm_service.client.models.generate_content")
def test_llm_call(mock_gemini):

    class MockResponse:
        text = "Mocked response"

    mock_gemini.return_value = MockResponse()

    response = call_gemini("test prompt")

    assert response == "Mocked response"


@patch("app.services.llm_service.client.models.generate_content")
def test_llm_error(mock_gemini):

    mock_gemini.side_effect = Exception("API failed")

    from fastapi import HTTPException
    import pytest

    with pytest.raises(HTTPException):
        call_gemini("test")