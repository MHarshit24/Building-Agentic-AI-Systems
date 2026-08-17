"""
Pydantic models for AI Tutor API request/response schemas.
"""

from pydantic import BaseModel, Field


class ConceptRequest(BaseModel):
    """Request model: User sends a concept to explain"""
    concept: str = Field(..., description="Agentic AI concept to explain", min_length=1)

class ErrorResponse(BaseModel):
    """Error response model: Standardized error format"""
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    status_code: int = Field(..., description="HTTP status code")


class ModelResponse(BaseModel):
    """Single model response"""
    model: str = Field(..., description="Model name")
    explanation: str = Field(..., description="Generated explanation")
    success: bool = Field(..., description="Whether generation succeeded")
    error_message: str = Field(default="", description="Error message if failed")


class DualExplanationResponse(BaseModel):
    """Response model: Returns explanations from both Gemini and Ollama"""
    concept: str = Field(..., description="The concept explained")
    gemini_response: ModelResponse = Field(..., description="Response from Gemini (cloud)")
    ollama_response: ModelResponse = Field(..., description="Response from Ollama (local)")
