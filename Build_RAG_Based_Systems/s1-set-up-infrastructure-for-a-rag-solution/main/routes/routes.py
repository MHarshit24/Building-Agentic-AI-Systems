"""
API routes and models for vectorstore operations.
"""

import logging
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

# TODO: Import your service here
from main.services.vectorstore_service import get_vectorstore_service

logger = logging.getLogger(__name__)

# --------------------------
# Pydantic Models
# --------------------------

class UploadDataRequest(BaseModel):
    """Request model for uploading string data."""
    doc_id: str = Field(..., description="Unique identifier for the document")
    content: str = Field(..., description="The text content to add to the vectorstore")
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional metadata to attach to the document (e.g., document name, category, etc.)"
    )


class UploadDataResponse(BaseModel):
    """Response model for upload operation."""
    success: bool = Field(..., description="Whether the upload was successful")
    message: str = Field(..., description="Status message")
    document_id: Optional[str] = Field(default=None, description="ID of the inserted document")


class QueryRequest(BaseModel):
    """Request model for querying the vectorstore."""
    query: str = Field(..., description="The search query text")
    top_k: Optional[int] = Field(
        default=1,
        ge=1,
        le=10,
        description="Number of results to return (1-10, default: 1)"
    )


class QueryResult(BaseModel):
    """Model for a single query result."""
    content: str = Field(..., description="The document content")
    metadata: Dict[str, Any] = Field(..., description="Document metadata")


class QueryResponse(BaseModel):
    """Response model for query operation."""
    success: bool = Field(..., description="Whether the query was successful")
    query: str = Field(..., description="The original query")
    results: List[QueryResult] = Field(..., description="List of query results")
    count: int = Field(..., description="Number of results returned")


# --------------------------
# API Routes
# --------------------------

router = APIRouter(prefix="/api/v1", tags=["vectorstore"])


@router.post("/upload", response_model=UploadDataResponse, status_code=status.HTTP_201_CREATED)
async def upload_data(request: UploadDataRequest):
    """
    Upload/add string data to the vectorstore.
    
    - **doc_id**: Unique identifier for the document (required)
    - **content**: The text content to add
    - **metadata**: Optional metadata (e.g., document name, category, etc.)
    """
    try:
        # TODO: Get your service instance here
        service = get_vectorstore_service()
        
        # TODO: Prepare metadata (merge doc_id into metadata if needed)
        metadata = request.metadata or {}
        metadata["doc_id"] = request.doc_id
        
        # TODO: Call your service method to add the document
        document_id = service.add_document(content=request.content, metadata=metadata)
        
        # TODO: Replace the placeholder below with actual document_id from service call
        # document_id is now set above from the service call
        
        # Return success response
        return UploadDataResponse(
            success=True,
            message="Document added successfully",
            document_id=document_id
        )
    except Exception as e:
        # TODO: Add specific exception handling here
        # Handle different types of exceptions (ValidationError, ValueError, ConnectionError, etc.)
        # Log errors appropriately using logger
        # Return appropriate HTTP status codes and error messages using HTTPException
        logger.error(f"Upload failed: {e}")
        if isinstance(e, ValueError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(e)
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload document: {str(e)}"
        )


@router.post("/query", response_model=QueryResponse)
async def query_vectorstore(request: QueryRequest):
    """
    Query the vectorstore for similar documents.
    
    - **query**: The search query text
    - **top_k**: Number of results to return (1-10, default: 1)
    """
    try:
        # TODO: Get your service instance here
        service = get_vectorstore_service()
        
        # TODO: Call your service method to query the vectorstore
        results = service.query(query_text=request.query, top_k=request.top_k)
        
        # TODO: Replace the placeholder below with actual results from service call
        # results is now set above from the service call
        
        # TODO: Transform service results into QueryResult objects
        query_results = [
            QueryResult(
                content=result["content"],
                metadata=result["metadata"]
            )
            for result in results
        ]
        
        # Return success response
        return QueryResponse(
            success=True,
            query=request.query,
            results=query_results,
            count=len(query_results)
        )
    except Exception as e:
        # TODO: Add specific exception handling here
        # Handle different types of exceptions (ValidationError, ValueError, ConnectionError, etc.)
        # Log errors appropriately using logger
        # Return appropriate HTTP status codes and error messages using HTTPException
        logger.error(f"Query failed: {e}")
        if isinstance(e, ValueError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(e)
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to query vectorstore: {str(e)}"
        )