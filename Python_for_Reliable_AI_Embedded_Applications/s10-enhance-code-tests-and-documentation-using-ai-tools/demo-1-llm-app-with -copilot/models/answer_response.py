"""
Answer Response Model

This module contains the Pydantic model for formatting API responses.
"""

from pydantic import BaseModel


class AnswerResponse(BaseModel):
    """
    Response model for AI answers.
    
    This model formats the API response containing the AI-generated answer
    that will be sent back to the client.
    
    Attributes:
        answer: The AI's answer
    """
    answer: str
