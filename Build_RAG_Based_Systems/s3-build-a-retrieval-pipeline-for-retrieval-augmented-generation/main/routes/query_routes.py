"""
API routes for RAG query pipeline.

TODO: Complete the implementation of query_rag() and retrieve_chunks() functions.
These endpoints handle RAG queries and semantic retrieval in the API.
"""

import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from urllib import request

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from ..services import query_with_error_handling
from ..config import logger

router = APIRouter()


def get_app_state():
    """Lazy import of app_state to avoid circular import"""
    from ..app import app_state
    return app_state


# ============================================================================
# Request/Response Models
# ============================================================================

class QueryRequest(BaseModel):
    """Request model for RAG query"""
    question: str = Field(
        ...,
        min_length=3,
        max_length=1000,
        description="User question to be answered using RAG",
        examples=["Benefits of EV Model?"]
    )
    top_k: Optional[int] = Field(
        default=None,
        ge=1,
        le=20,
        description="Number of chunks to retrieve (overrides default)"
    )
    include_sources: bool = Field(
        default=True,
        description="Include source documents in response"
    )


class RetrievalRequest(BaseModel):
    """Request model for retrieval-only endpoint"""
    query: str = Field(
        ...,
        min_length=3,
        max_length=1000,
        description="Query for semantic search",
        examples=["brake system maintenance"]
    )
    top_k: Optional[int] = Field(
        default=None,
        ge=1,
        le=20,
        description="Number of chunks to retrieve"
    )


class SourceDocument(BaseModel):
    """Model for source document metadata"""
    source: str = Field(description="Source document name")
    chunk_id: str = Field(description="Chunk identifier")
    content: str = Field(description="Chunk content")
    relevance_score: Optional[float] = Field(default=None, description="Similarity score")


class QueryResponse(BaseModel):
    """Response model for RAG query"""
    question: str = Field(description="Original question")
    answer: str = Field(description="Generated answer")
    sources: List[SourceDocument] = Field(description="Retrieved source documents")
    metadata: Dict[str, Any] = Field(description="Response metadata")
    timestamp: str = Field(description="Response timestamp")


class RetrievalResponse(BaseModel):
    """Response model for retrieval-only endpoint"""
    query: str = Field(description="Original query")
    chunks: List[SourceDocument] = Field(description="Retrieved chunks")
    count: int = Field(description="Number of chunks retrieved")
    timestamp: str = Field(description="Response timestamp")


class HealthResponse(BaseModel):
    """Response model for health check"""
    status: str = Field(description="Service status")
    database_connected: bool = Field(description="Database connection status")
    embedding_model_loaded: bool = Field(description="Embedding model status")
    llm_loaded: bool = Field(description="LLM status")
    timestamp: str = Field(description="Health check timestamp")


class MetricsResponse(BaseModel):
    """Response model for metrics endpoint"""
    total_queries: int = Field(description="Total queries processed")
    successful_queries: int = Field(description="Successful queries")
    failed_queries: int = Field(description="Failed queries")
    average_chunks_retrieved: float = Field(description="Average chunks per query")
    uptime_seconds: float = Field(description="Service uptime in seconds")


@router.post("/query", response_model=QueryResponse, tags=["RAG"])
async def query_rag(request: QueryRequest):
    """
    Execute RAG query with full pipeline
    
    This endpoint orchestrates the complete RAG pipeline: validates components,
    retrieves relevant chunks, generates answers using LLM, and returns
    response with source citations.
    
    Args:
        request: QueryRequest containing question, optional top_k, and include_sources flag
        
    Returns:
        QueryResponse with answer, sources, metadata, and timestamp
        
    Raises:
        HTTPException: If pipeline not initialized or query processing fails
        
    Hints:
        1. Get app_state using get_app_state()
        2. Increment total_queries counter
        3. Wrap logic in try-except blocks for error handling
        4. Validate RAG pipeline components (rag_chain and retriever)
        5. If not initialized, raise HTTPException with 503 status
        6. Handle custom top_k from request or use default from config
        7. Create custom retriever if top_k is provided, otherwise use default
        8. Execute query using query_with_error_handling()
        9. Check result status and handle failures
        10. Extract answer and update metrics
        11. Format sources from result if include_sources is True
        12. Build metadata dictionary with chunks_retrieved, top_k, model, etc.
        13. Update successful_queries counter
        14. Return QueryResponse with all data
        15. Handle HTTPException and general exceptions separately
    """    
    
    # TODO: Step 1 - Get app state and increment counter
    # Get app_state using get_app_state()
    # Increment app_state.total_queries

    app_state = get_app_state()

    app_state.total_queries += 1

    try:
        # TODO: Step 2 - Validate RAG pipeline components
        # Check if app_state.rag_chain and app_state.retriever are not None
        # If either is None, raise HTTPException with:
        #   - status_code: status.HTTP_503_SERVICE_UNAVAILABLE
        #   - detail: "RAG pipeline not initialized"

        if (
            app_state.rag_chain is None
            or
            app_state.retriever is None
        ):

            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="RAG pipeline not initialized"
            )

        # TODO: Step 3 - Determine top_k value
        # If request.top_k is provided, use it; otherwise use app_state.config['top_k']
        # Store in variable k

        k = (
            request.top_k
            if request.top_k
            else app_state.config["top_k"]
        )

        # TODO: Step 4 - Create or get retriever
        # If request.top_k is provided:
        #   - Create custom retriever from app_state.vectorstore.as_retriever()
        #   - Use search_type="similarity" and search_kwargs={"k": k}
        # Otherwise, use app_state.retriever

        if request.top_k:

            retriever = (
                app_state.vectorstore
                .as_retriever(
                    search_type="similarity",
                    search_kwargs={"k": k}
                )
            )

        else:

            retriever = app_state.retriever

        # TODO: Step 5 - Execute query
        # Call query_with_error_handling() with:
        #   - app_state.rag_chain
        #   - retriever (from step 4)
        #   - request.question
        # Store result

        result = query_with_error_handling(
            app_state.rag_chain,
            retriever,
            request.question
        )

        # TODO: Step 6 - Check query result status
        # If result["status"] is not "success":
        #   - Raise HTTPException with:
        #     * status_code: status.HTTP_500_INTERNAL_SERVER_ERROR
        #     * detail: result.get('error', 'Query processing failed')

        if result["status"] != "success":

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get(
                    "error",
                    "Query processing failed"
                )
            )

        # TODO: Step 7 - Extract answer and update metrics
        # Get answer from result["answer"]
        # Add retrieved_chunks count to app_state.total_chunks_retrieved

        answer = result["answer"]

        app_state.total_chunks_retrieved += (
            result.get(
                "retrieved_chunks",
                0
            )
        )

        # TODO: Step 8 - Format sources
        # Initialize empty sources list
        # If request.include_sources is True and "sources" in result:
        #   - Create list of SourceDocument objects from result["sources"]
        #   - Extract: source, chunk_id (as string), content (remove "..." from content_preview)
        #   - Set relevance_score to None

        sources = []

        if (
            request.include_sources
            and
            "sources" in result
        ):

            for source in result["sources"]:

                sources.append(

                    SourceDocument(

                        source=source["source"],

                        chunk_id=str(
                            source["chunk_id"]
                        ),

                        content=source[
                            "content_preview"
                        ].replace(
                            "...",
                            ""
                        ),

                        relevance_score=None
                    )
                )

        # TODO: Step 9 - Build metadata dictionary
        # Create metadata dict with:
        #   - chunks_retrieved: from result
        #   - top_k: k value
        #   - model: app_state.config['azure_llm_deployment']
        #   - has_sources: boolean (len(sources) > 0)
        #   - graceful_failure: from result quality_metrics

        metadata = {

            "chunks_retrieved":
                result.get(
                    "retrieved_chunks",
                    0
                ),

            "top_k":
                k,

            "model":
                app_state.config[
                    "azure_llm_deployment"
                ],

            "has_sources":
                len(sources) > 0,

            "graceful_failure":
                result.get(
                    "quality_metrics",
                    {}
                ).get(
                    "graceful_failure",
                    False
                )
        }

        # TODO: Step 10 - Update success metrics
        # Increment app_state.successful_queries

        app_state.successful_queries += 1

        # TODO: Step 11 - Return QueryResponse
        # Return QueryResponse with:
        #   - question: request.question
        #   - answer: answer from step 7
        #   - sources: sources list from step 8
        #   - metadata: metadata dict from step 9
        #   - timestamp: datetime.now().isoformat()

        return QueryResponse(

            question=request.question,

            answer=answer,

            sources=sources,

            metadata=metadata,

            timestamp=datetime.now().isoformat()
        )

    except HTTPException:
        # TODO: Step 12 - Handle HTTPException
        # Increment app_state.failed_queries
        # Re-raise the exception

        app_state.failed_queries += 1

        raise

    except Exception as e:
        # TODO: Step 13 - Handle general exceptions
        # Increment app_state.failed_queries
        # Raise HTTPException with:
        #   - status_code: status.HTTP_500_INTERNAL_SERVER_ERROR
        #   - detail: f"Query processing failed: {str(e)}"

        app_state.failed_queries += 1

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query processing failed: {str(e)}"
        )
@router.post("/retrieve", response_model=RetrievalResponse, tags=["Retrieval"])
async def retrieve_chunks(request: RetrievalRequest):
    """
    Retrieve relevant chunks without LLM generation
    
    This endpoint performs semantic search on the vectorstore and returns
    the top-k most relevant document chunks without generating an answer.
    
    Args:
        request: RetrievalRequest containing query and optional top_k
        
    Returns:
        RetrievalResponse with retrieved chunks, count, and timestamp
        
    Raises:
        HTTPException: If retrieval fails
        
    Hints:
        1. Get app_state using get_app_state()
        2. Wrap logic in try-except for error handling
        3. Determine top_k from request or use default from config
        4. Create retriever from vectorstore with custom k
        5. Invoke retriever to get documents
        6. Format documents into SourceDocument objects
        7. Return RetrievalResponse with chunks and metadata
        8. Handle exceptions with appropriate HTTPException
    """
    # TODO: Step 1 - Get app state
    # Get app_state using get_app_state()

    app_state = get_app_state()
    
    try:
        # TODO: Step 2 - Determine top_k value
        # Use request.top_k if provided, otherwise use app_state.config['top_k']
        # Store in variable k

        k = (
            request.top_k
            if request.top_k
            else app_state.config["top_k"]
        )
        
        # TODO: Step 3 - Create retriever
        # Create retriever from app_state.vectorstore.as_retriever()
        # Use search_type="similarity" and search_kwargs={"k": k}

        retriever = app_state.vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs={"k": k}
        )
        
        # TODO: Step 4 - Retrieve documents
        # Invoke retriever with request.query
        # Store documents in variable

        docs = retriever.invoke(
            request.query
        )
        
        # TODO: Step 5 - Format chunks for response
        # Create list of SourceDocument objects from retrieved documents:
        #   - source: from doc.metadata.get('source', 'Unknown')
        #   - chunk_id: from doc.metadata.get('chunk_id', 'N/A') as string
        #   - content: from doc.page_content
        #   - relevance_score: None

        chunks = []

        for doc in docs:

            chunks.append(

                SourceDocument(

                    source=doc.metadata.get(
                        "source",
                        "Unknown"
                    ),

                    chunk_id=str(
                        doc.metadata.get(
                            "chunk_id",
                            "N/A"
                        )
                    ),

                    content=doc.page_content,

                    relevance_score=None
                )
            )
        
        # TODO: Step 6 - Return response
        # Return RetrievalResponse with:
        #   - query: request.query
        #   - chunks: chunks list from step 5
        #   - count: length of chunks list
        #   - timestamp: datetime.now().isoformat()

        return RetrievalResponse(

            query=request.query,

            chunks=chunks,

            count=len(chunks),

            timestamp=datetime.now().isoformat()
        )
        
    except Exception as e:
        # TODO: Step 7 - Handle exceptions
        # Raise HTTPException with:
        #   - status_code: status.HTTP_500_INTERNAL_SERVER_ERROR
        #   - detail: f"Retrieval failed: {str(e)}"

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Retrieval failed: {str(e)}"
        )


@router.get("/", tags=["General"])
async def root():
    """Root endpoint with API information"""
    return {
        "service": "AutoMind RAG Query API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "query": "/query",
            "retrieve": "/retrieve",
            "health": "/health",
            "metrics": "/metrics",
            "docs": "/docs"
        }
    }


@router.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """
    Health check endpoint.
    
    Returns the operational status of all components.
    Checks if components are initialized (does not test actual connectivity).
    """
    logger.debug("Health check requested")
    app_state = get_app_state()
    try:
        # Check if components are initialized
        # Note: This checks initialization status, not actual connectivity
        # For production, consider adding actual connection tests
        db_connected = app_state.vectorstore is not None
        embedding_loaded = app_state.embeddings is not None
        llm_loaded = app_state.llm is not None
        
        status_value = "healthy" if all([db_connected, embedding_loaded, llm_loaded]) else "degraded"
        logger.debug(f"Health status: {status_value} (DB: {db_connected}, Embeddings: {embedding_loaded}, LLM: {llm_loaded})")
        
        return HealthResponse(
            status=status_value,
            database_connected=db_connected,
            embedding_model_loaded=embedding_loaded,
            llm_loaded=llm_loaded,
            timestamp=datetime.now().isoformat()
        )
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Health check failed"
        )


@router.get("/metrics", response_model=MetricsResponse, tags=["Monitoring"])
async def get_metrics():
    """
    Get pipeline metrics and statistics
    
    Returns usage statistics and performance metrics
    """
    logger.debug("Metrics requested")
    app_state = get_app_state()
    uptime = (datetime.now() - app_state.start_time).total_seconds()
    
    avg_chunks = (
        app_state.total_chunks_retrieved / app_state.successful_queries
        if app_state.successful_queries > 0
        else 0.0
    )
    
    logger.debug(f"Current metrics: {app_state.total_queries} total queries, {app_state.successful_queries} successful")
    
    return MetricsResponse(
        total_queries=app_state.total_queries,
        successful_queries=app_state.successful_queries,
        failed_queries=app_state.failed_queries,
        average_chunks_retrieved=avg_chunks,
        uptime_seconds=uptime
    )
