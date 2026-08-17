"""
Query Routes - API endpoints for querying the healthcare analytics agent
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List

from main.service.query_service import execute_hybrid_query

router = APIRouter()


class QueryRequest(BaseModel):
    question: str = Field(..., description="The question to ask the healthcare analytics agent", min_length=1)
    
    class Config:
        json_schema_extra = {
            "example": {
                "question": "Is our Cardiology readmission rate meeting the 2025 target?"
            }
        }


class QueryResponse(BaseModel):
    question: str
    answer: str
    tools_used: Optional[List[str]] = None
    sources_used: Optional[str] = None


@router.post("/query", response_model=QueryResponse)
async def query_agent(request: QueryRequest):
    """
    Query the Healthcare Analytics Agentic RAG system with a question.
    
    The agent will automatically decide whether to:
    - Query the hospital database (for patient counts, utilization rates, readmission stats)
    - Search policy documents (for targets, benchmarks, protocols, guidelines)
    - Use both sources and synthesize the answer
    
    Returns the answer along with which tools were used.
    """
    try:
        # Execute hybrid query using the service layer
        result = await execute_hybrid_query(request.question)
        
        # Convert to response model
        return QueryResponse(**result.to_dict())
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")
