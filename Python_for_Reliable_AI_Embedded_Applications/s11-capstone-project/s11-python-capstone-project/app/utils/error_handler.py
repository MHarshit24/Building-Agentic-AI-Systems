from fastapi import HTTPException

def handle_llm_error(error: Exception):
    """
    Standard fallback response when LLM fails.

    Returns structured JSON instead of plain string.
    """

    return {
        "error": "AI_SERVICE_ERROR",
        "message": "AI service temporarily unavailable",
        "details": str(error)
    }




def raise_ai_service_error():
    """
    Raise 503 error when AI service is unavailable.
    """
    raise HTTPException(
        status_code=503,
        detail={
            "error": "AI_SERVICE_ERROR",
            "message": "AI service temporarily unavailable"
        }
    )


def raise_internal_error():
    """
    Raise 500 error for unexpected server issues.
    """
    raise HTTPException(
        status_code=500,
        detail={
            "error": "INTERNAL_SERVER_ERROR",
            "message": "Unexpected server error occurred, Please check the Code"
        }
    )


def raise_bad_request(msg: str):
    """
    Raise 400 error for invalid user input.

    Args:
        msg (str): Custom error message
    """
    raise HTTPException(
        status_code=400,
        detail={
            "error": "BAD_REQUEST",
            "message": msg
        }
    )
