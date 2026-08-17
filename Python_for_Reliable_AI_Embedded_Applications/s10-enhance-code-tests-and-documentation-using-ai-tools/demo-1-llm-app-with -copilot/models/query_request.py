"""
Query Request Model

This module contains the Pydantic model for validating incoming user questions.
"""

from pydantic import BaseModel


class QueryRequest(BaseModel):
    """
    Request model for user questions.
    
    This model validates incoming API requests containing user questions
    for the AI to process.
    
    Attributes:
        prompt: The user's question or prompt
    """
    prompt: str

