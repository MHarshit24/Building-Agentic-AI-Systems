from app.models.response_models import (
    ExplainResponse, 
    ImproveResponse, 
    AnalyzeResponse, 
    ReviewResponse,
    MentorResponse
)
from app.utils.prompt_builder import build_prompt
from app.services.llm_service import call_gemini
from app.utils.language_detector import detect_language
import json
from app.utils.database import save_ai_log

def process_code(request, task="analyze"):
    """
    Process user code using AI model.

    Steps:
    - Detect programming language
    - Build prompt
    - Call Gemini API
    - Parse AI response
    - Return structured output

    Args:
        request: CodeRequest object
        task (str): analyze / explain / improve / review

    Returns:
        Response model based on task
    """  
    language = request.language or detect_language(request.code)

    prompt = build_prompt(
        request.code,
        language,
        request.experience_level,
        task
    )

    ai_response = call_gemini(prompt)


    save_ai_log(
        request.code,
        language,
        request.experience_level,
        task,
        ai_response
    )

    try:
        cleaned = ai_response.strip()

        if cleaned.startswith("```"):
            cleaned = cleaned.replace("```json", "").replace("```", "").strip()

        parsed = json.loads(cleaned)

        # Return appropriate response based on task
        if task == "explain":
            return ExplainResponse(
                explanation=parsed.get("explanation", ""),
                complexity_level=parsed.get("complexity_level", "intermediate"),
                key_concepts=parsed.get("key_concepts", [])
            )
        elif task == "improve":
            return ImproveResponse(
                current_code_summary=parsed.get("current_code_summary", ""),
                suggested_improvements=parsed.get("suggested_improvements", []),
                optimized_code=parsed.get("optimized_code"),
                performance_gain=parsed.get("performance_gain")
            )
        elif task == "review":
            return ReviewResponse(
                overall_score=parsed.get("overall_score", 5),
                explanation=parsed.get("explanation", ""),
                detected_issues=parsed.get("detected_issues", []),
                improvements=parsed.get("improvements", []),
                best_practices=parsed.get("best_practices", []),
                security_concerns=parsed.get("security_concerns", []),
                maintainability_score=parsed.get("maintainability_score", 5)
            )
        else:  # analyze
            return AnalyzeResponse(
                code_summary=parsed.get("code_summary", ""),
                detected_issues=parsed.get("detected_issues", []),
                improvements=parsed.get("improvements", []),
                best_practices=parsed.get("best_practices", [])
            )

    except Exception:
        # Fallback to generic response if parsing fails
        if task == "explain":
            return ExplainResponse(
                explanation=ai_response,
                complexity_level="intermediate",
                key_concepts=[]
            )
        elif task == "improve":
            return ImproveResponse(
                current_code_summary=ai_response,
                suggested_improvements=[],
                optimized_code=None,
                performance_gain=None
            )
        elif task == "review":
            return ReviewResponse(
                overall_score=5,
                explanation=ai_response,
                detected_issues=[],
                improvements=[],
                best_practices=[],
                security_concerns=[],
                maintainability_score=5
            )
        else:  # analyze
            return AnalyzeResponse(
                code_summary=ai_response,
                detected_issues=[],
                improvements=[],
                best_practices=[]
            )