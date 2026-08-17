from pydantic import BaseModel, Field
from typing import Optional


class ConceptRequest(BaseModel):
    """
    Request model for explaining a concept.
    """
    concept: str = Field(..., example="Recursion")
    level: Optional[str] = Field("beginner", example="intermediate")


class ExplanationResponse(BaseModel):
    """
    Response model for concept explanation.
    """
    concept: str
    explanation: str
    model_used: str
    confidence: Optional[float] = 0.9


class ErrorResponse(BaseModel):
    """
    Standard error response format.
    """
    error: str
    detail: str