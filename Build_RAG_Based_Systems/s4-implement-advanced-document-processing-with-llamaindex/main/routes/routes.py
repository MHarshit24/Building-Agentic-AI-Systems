"""
Routes Module
FastAPI route handlers for document upload and diet counselling queries.

This module provides:
- Document upload with automatic diet-specific metadata assignment
- Query endpoint with optional metadata filtering for targeted diet information
"""

import os
import re
import logging
import tempfile
from typing import List, Optional, Dict
from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel, Field, field_validator
from llama_index.core import SimpleDirectoryReader
from llama_index.core.vector_stores import MetadataFilters, ExactMatchFilter
from main.service import get_query_engine, add_documents_to_index, get_file_metadata

logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

# Configuration constants
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_QUERY_LENGTH = 2000
MIN_SIMILARITY_TOP_K = 1
MAX_SIMILARITY_TOP_K = 20
ALLOWED_EXTENSIONS = {'.txt', '.pdf', '.md'}


# Request/Response Models
class QueryRequest(BaseModel):
    """Request model for diet counselling query endpoint."""
    question: str = Field(
        ..., 
        min_length=1, 
        max_length=MAX_QUERY_LENGTH,
        examples=["What are some healthy breakfast options for a vegetarian diet?"]
    )
    similarity_top_k: int = Field(
        default=2, 
        ge=MIN_SIMILARITY_TOP_K, 
        le=MAX_SIMILARITY_TOP_K,
        examples=[3]
    )
    filters: Optional[Dict[str, str]] = Field(
        default=None, 
        description="Optional metadata filters for targeted diet information. Examples: {'meal_type': 'breakfast'}, {'dietary_restriction': 'vegetarian'}, {'nutrition_category': 'protein'}",
        examples=[{"meal_type": "breakfast", "dietary_restriction": "vegetarian"}]
    )
    
    @field_validator('question')
    @classmethod
    def validate_question(cls, v):
        """Validate and sanitize question input."""
        if not v or not v.strip():
            raise ValueError("Question cannot be empty")
        return v.strip()


class QueryResponse(BaseModel):
    """Response model for query endpoint."""
    answer: str
    source_nodes: List[dict] = []


class UploadResponse(BaseModel):
    """Response model for upload endpoint."""
    message: str
    documents_indexed: int


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent path traversal and other security issues.
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename safe for filesystem operations
    """
    if not filename:
        raise ValueError("Filename cannot be empty")
    
    # Remove path components
    filename = os.path.basename(filename)
    
    # Remove any remaining path separators
    filename = filename.replace('/', '_').replace('\\', '_')
    
    # Remove dangerous characters
    filename = re.sub(r'[^\w\s.-]', '', filename)
    
    # Limit length
    if len(filename) > 255:
        name, ext = os.path.splitext(filename)
        filename = name[:250] + ext
    
    return filename


@router.post("/upload", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...)):
    """
    Upload a diet-related document file for indexing with automatic metadata assignment.
    
    Accepts: .txt, .pdf, .md files (max 10MB)
    
    Metadata is automatically assigned based on filename:
    - Meal types: breakfast, lunch, dinner, snack
    - Dietary restrictions: vegetarian, vegan, gluten-free, keto, diabetic, low-sodium
    - Nutrition categories: protein, carbohydrates, vitamins, minerals, healthy-fats
    - Topics: recipes, meal-planning, nutrition-facts, dietary-guidelines
    """
    file_path = None
    try:
        # Validate filename
        if not file.filename:
            raise HTTPException(
                status_code=400,
                detail="Filename is required"
            )
        
        # Sanitize filename to prevent path traversal
        safe_filename = sanitize_filename(file.filename)
        file_ext = os.path.splitext(safe_filename)[1].lower()
        
        # Validate file type
        if file_ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"File type not supported. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
            )
        
        # Read file content with size limit
        content = await file.read()
        
        # Validate file size
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File size exceeds maximum allowed size of {MAX_FILE_SIZE / (1024*1024):.1f}MB"
            )
        
        # Create temporary file for processing
        with tempfile.NamedTemporaryFile(
            mode='wb',
            suffix=file_ext,
            delete=False
        ) as tmp_file:
            tmp_file.write(content)
            file_path = tmp_file.name
        
        logger.info(f"File uploaded: {safe_filename} ({len(content)} bytes)")
        
        # TODO: Load document using SimpleDirectoryReader
        # HINT: Create a SimpleDirectoryReader with input_files=[file_path]
        # HINT: Call load_data() to load the documents
        # Your code here:
        documents = SimpleDirectoryReader(input_files=[file_path]).load_data()
        
        # TODO: Get expected metadata for the document
        # HINT: Use get_file_metadata(safe_filename) to extract metadata from filename
        # Your code here:
        expected_metadata = get_file_metadata(safe_filename)
        
        # TODO: Apply metadata to all loaded documents
        # HINT: Loop through documents and replace each doc.metadata with expected_metadata.copy()
        # HINT: Use .copy() to avoid sharing the same dictionary reference
        # Your code here:
        for doc in documents:
            doc.metadata = expected_metadata.copy()
        
        # TODO: Add documents to the index
        # HINT: Call add_documents_to_index(documents) to index the documents
        # HINT: Store the result in a variable
        # Your code here:
        result = add_documents_to_index(documents)
        
        # TODO: Return UploadResponse with success message and document count
        # HINT: Use result["message"] and len(documents)
        # Your code here:
        return UploadResponse(
            message=result["message"],
            documents_indexed=len(documents)
        )
        
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Validation error: {e}", exc_info=True)
        raise HTTPException(
            status_code=400,
            detail="Invalid file or request"
        )
    except Exception as e:
        logger.error(f"Error uploading document: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to process document"
        )
    finally:
        # Always clean up temporary file
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as e:
                logger.warning(f"Failed to clean up temporary file {file_path}: {e}")


@router.post("/query", response_model=QueryResponse)
async def query_rag(request: QueryRequest):
    """
    Query the diet counselling RAG system with a question.
    
    Supports optional metadata filtering to target specific:
    - Meal types (breakfast, lunch, dinner, snack)
    - Dietary restrictions (vegetarian, vegan, gluten-free, keto, diabetic, low-sodium)
    - Nutrition categories (protein, carbohydrates, vitamins, minerals, healthy-fats)
    - Topics (recipes, meal-planning, nutrition-facts, dietary-guidelines)
    
    Returns answer and source nodes used for the response.
    """
    try:
        # TODO: Construct metadata filters if provided
        # HINT: Initialize metadata_filters as None
        # HINT: If request.filters is provided:
        #   1. Create a list of ExactMatchFilter objects for each key-value pair
        #   2. Wrap them in a MetadataFilters object
        # Your code here:
        metadata_filters = None
        if request.filters:
            metadata_filters = MetadataFilters(
                filters=[
                    ExactMatchFilter(key=k, value=v)
                    for k, v in request.filters.items()
                ]
            )
        
        # TODO: Get query engine with specified parameters
        # HINT: Call get_query_engine() with similarity_top_k and filters
        # Your code here:
        query_engine = get_query_engine(
            similarity_top_k=request.similarity_top_k,
            filters=metadata_filters
        )
        
        # TODO: Execute the query
        # HINT: Call query_engine.query() with request.question
        # Your code here:
        response = query_engine.query(request.question)
        
        # TODO: Extract the answer from response
        # HINT: Convert response to string
        # Your code here:
        answer = str(response)
        
        # Extract source nodes (already implemented)
        source_nodes = []
        if hasattr(response, 'source_nodes') and response.source_nodes:
            logger.info(f"Retrieved {len(response.source_nodes)} source node(s)")
            for i, node in enumerate(response.source_nodes, 1):
                node_metadata = node.metadata if hasattr(node, 'metadata') else {}
                logger.info(f"Source node {i} metadata: {node_metadata}")
                source_nodes.append({
                    "text": node.text[:200] + "..." if len(node.text) > 200 else node.text,
                    "score": float(node.score) if hasattr(node, 'score') else None,
                    "metadata": node_metadata
                })
        else:
            logger.warning("No source nodes retrieved from query")
        
        # TODO: Return QueryResponse with answer and source_nodes
        # Your code here:
        return QueryResponse(
            answer=answer,
            source_nodes=source_nodes
        )
        
    except ValueError as e:
        logger.error(f"Validation error: {e}", exc_info=True)
        raise HTTPException(
            status_code=400,
            detail="Invalid query request"
        )
    except Exception as e:
        logger.error(f"Error processing query: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to process query"
        )


@router.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "Personal Diet Counselling Assistant API",
        "description": "RAG-based system for diet information and counselling using LlamaIndex",
        "endpoints": {
            "POST /upload": "Upload diet-related documents for indexing (auto-assigns metadata based on filename)",
            "POST /query": "Query the diet counselling system (supports metadata filters for targeted information)",
            "GET /health": "Health check"
        },
        "metadata_filters": {
            "meal_type": ["breakfast", "lunch", "dinner", "snack"],
            "dietary_restriction": ["vegetarian", "vegan", "gluten-free", "keto", "diabetic", "low-sodium"],
            "nutrition_category": ["protein", "carbohydrates", "vitamins", "minerals", "healthy-fats"],
            "topic": ["recipes", "meal-planning", "nutrition-facts", "dietary-guidelines"]
        }
    }