from fastapi import APIRouter, HTTPException
from app.models.request_models import CodeRequest
from app.services.code_analysis_service import process_code
from fastapi.responses import StreamingResponse
from app.services.llm_service import stream_gemini
from app.utils.prompt_builder import build_prompt
import asyncio
from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi import Request
from app.models.feedback_model import FeedbackRequest
from app.services.feedback_service import save_feedback
from pydantic import ValidationError

router = APIRouter()

limiter = Limiter(key_func=get_remote_address)


@router.post(
    "/analyze-code",
    responses={
        200: {"description": "Successful analysis"},
        400: {"description": "Bad request"},
        429: {"description": "Rate limit exceeded"},
        500: {"description": "Internal server error"},
        503: {"description": "AI service unavailable"}
    }
)
@limiter.limit("1/minute")
def analyze_code_route(request: Request, data: CodeRequest):
    """
    Analyze the given code snippet.

    This endpoint processes the user code and returns:
    - Code summary
    - Detected issues
    - Suggested improvements
    - Best practices

    Parameters:
        data (CodeRequest): Contains code, language, and experience level

    Returns:
        AnalyzeResponse: Structured response with analysis results
    """
    return process_code(data, task="analyze")


@router.post("/analyze-code/stream")
@limiter.limit("5/minute")
async def analyze_code_stream(request: Request, data: CodeRequest):
    """
    Stream the analysis of the given code snippet in real-time.

    Returns:
        StreamingResponse: Chunked plain-text stream of AI analysis
    """
    prompt = build_prompt(
        data.code,
        data.language,
        data.experience_level,
        "analyze"
    )

    async def event_generator():
        for chunk in stream_gemini(prompt):
            yield chunk
            await asyncio.sleep(0.02)

    return StreamingResponse(event_generator(), media_type="text/plain")


@router.post("/explain-code")
@limiter.limit("10/minute")
def explain_code_route(request: Request, data: CodeRequest):
    """
    Explain the given code in a simple and understandable way.

    The explanation is tailored based on the user's experience level.

    Returns:
        ExplainResponse: Explanation with key concepts
    """
    return process_code(data, task="explain")


@router.post("/improve-code")
@limiter.limit("10/minute")
def improve_code_route(request: Request, data: CodeRequest):
    """
    Suggest improvements and optimized version of the code.

    Returns:
        ImproveResponse: Suggestions and optimized code
    """
    return process_code(data, task="improve")


@router.post("/review-code")
@limiter.limit("10/minute")
def review_code_route(request: Request, data: CodeRequest):
    """
    Perform a detailed code review.

    Includes:
    - Code quality score
    - Issues
    - Improvements
    - Security concerns

    Returns:
        ReviewResponse: Detailed review report
    """
    return process_code(data, task="review")


@router.post("/feedback")
@limiter.limit("20/minute")
def feedback_route(request: Request, data: FeedbackRequest):
    """
    Save user feedback for the AI response.

    Stores feedback in:
    - PostgreSQL database
    - JSON log file

    Returns:
        dict: Success or failure message
    """
    return save_feedback(data)