"""
Models package for LLM App with GitHub Copilot Demo

This package contains all Pydantic models used for request validation
and response formatting in the API.
"""

from .query_request import QueryRequest
from .answer_response import AnswerResponse

__all__ = ["QueryRequest", "AnswerResponse"]
