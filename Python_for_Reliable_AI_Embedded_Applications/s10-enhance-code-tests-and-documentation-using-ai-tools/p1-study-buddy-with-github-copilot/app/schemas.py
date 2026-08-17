

from pydantic import BaseModel, Field


class ConceptRequest(BaseModel):
   
    concept: str = Field(..., description="Agentic AI concept to explain", example="RAG")


class ExplanationResponse(BaseModel):
   
    concept: str = Field(..., description="The concept explained")
    explanation: str = Field(..., description="The generated explanation")
    model: str = Field(..., description="AI model used")


class ErrorResponse(BaseModel):
   
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    status_code: int = Field(..., description="HTTP status code")
