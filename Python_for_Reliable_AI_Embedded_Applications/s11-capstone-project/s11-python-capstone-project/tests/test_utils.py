from app.utils.error_handler import raise_ai_service_error, raise_internal_error
from app.utils.language_detector import detect_language
from app.utils.language_detector import detect_language
from app.utils.prompt_builder import build_prompt
import pytest
from fastapi import HTTPException
from app.utils.language_detector import detect_language

def test_detect_python():

    code = "def add(a,b): return a+b"

    result = detect_language(code)

    assert result == "python"


def test_internal_error():
    with pytest.raises(HTTPException) as exc:
        raise_internal_error()

    assert exc.value.status_code == 500

def test_language_detector_python():
    assert detect_language("def add(a,b): return a+b") == "python"


def test_language_detector_java():
    assert detect_language("public static void main") == "java"


def test_language_detector_unknown():
    assert detect_language("random text") == "unknown"


def test_prompt_builder_analyze():
    prompt = build_prompt("print('hi')", "python", "beginner", "analyze")
    assert "code_summary" in prompt


def test_prompt_builder_explain():
    prompt = build_prompt("print('hi')", "python", "beginner", "explain")
    assert "explanation" in prompt    


def test_error_handler():
    with pytest.raises(HTTPException) as exc:
        raise_ai_service_error()
    assert exc.value.status_code == 503    

def test_prompt_builder_improve():
    prompt = build_prompt("print('hi')", "python", "expert", "improve")
    assert "suggested_improvements" in prompt


def test_prompt_builder_review():
    prompt = build_prompt("print('hi')", "python", "expert", "review")
    assert "overall_score" in prompt    