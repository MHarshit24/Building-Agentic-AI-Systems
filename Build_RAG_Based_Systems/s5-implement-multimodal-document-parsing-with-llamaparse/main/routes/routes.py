"""API routes for diet counselling assistant with metadata filtering."""
import logging
import os
import tempfile
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel, Field, field_validator

from ..service.rag_service import RAGService

logger = logging.getLogger(__name__)

router = APIRouter()
rag_service = RAGService()


class QueryRequest(BaseModel):
    """Request model for query endpoint with metadata filtering."""
    question: str = Field(
        ...,
        max_length=2000,
        description="Query question (max 2000 characters)",
        examples=["What are some healthy breakfast options for a vegetarian diet?"],
    )
    similarity_top_k: int = Field(
        default=2,
        ge=1,
        le=20,
        description="Number of top similar results to retrieve (1-20)",
        examples=[3],
    )
    filters: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional metadata filters (e.g., {'meal_type': 'breakfast', 'dietary_restriction': 'vegetarian'})",
        examples=[
            {"meal_type": "breakfast"},
            {"meal_type": "breakfast", "dietary_restriction": "vegetarian"},
        ],
    )
    
    @field_validator('question')
    @classmethod
    def validate_question(cls, v):
        if not v or not v.strip():
            raise ValueError("Question cannot be empty")
        return v.strip()


class NodeInfo(BaseModel):
    """Model for node information in query responses."""
    text: str
    score: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


class QueryResponse(BaseModel):
    """Response model for query endpoint."""
    answer: str
    source_nodes: List[NodeInfo]


class UploadResponse(BaseModel):
    """Response model for upload endpoint."""
    message: str
    documents_indexed: int


@router.get("/health")
async def health_check():
    """
    Health check endpoint.
    
    Returns:
        Service health status
    """
    return {
        "status": "healthy",
        "service": "Personal Diet Counselling Assistant API",
        "initialized": rag_service.is_initialized()
    }


@router.get("/")
async def root():
    """
    Root endpoint with API information and available metadata filters.
    
    Returns:
        API information and metadata filter options
    """
    return {
        "service": "Personal Diet Counselling Assistant API",
        "version": "1.0.0",
        "description": "RAG-based diet counselling system with multi-modal content processing",
        "docs": "/docs",
        "metadata_filters": {
            "meal_types": ["breakfast", "lunch", "dinner", "snack"],
            "dietary_restrictions": ["vegetarian", "vegan", "gluten-free", "keto", "diabetic", "low-sodium"],
            "nutrition_categories": ["protein", "carbohydrates", "vitamins", "minerals", "healthy-fats"],
            "topics": ["recipes", "meal-planning", "nutrition-facts", "dietary-guidelines"]
        },
        "example_queries": {
            "without_filter": {
                "question": "What are some healthy breakfast options?",
                "similarity_top_k": 3
            },
            "with_meal_type": {
                "question": "What are some healthy breakfast options?",
                "similarity_top_k": 3,
                "filters": {"meal_type": "breakfast"}
            },
            "with_multiple_filters": {
                "question": "What are some healthy breakfast options?",
                "similarity_top_k": 3,
                "filters": {
                    "meal_type": "breakfast",
                    "dietary_restriction": "vegetarian"
                }
            }
        }
    }


@router.post("/upload", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...)):
    """
    Upload and process a PDF document.
    
    Metadata is automatically assigned based on filename patterns:
    - Meal types: breakfast, lunch, dinner, snack
    - Dietary restrictions: vegetarian, vegan, gluten-free, keto, diabetic, low-sodium
    - Nutrition categories: protein, carbohydrates, vitamins, minerals, healthy-fats
    - Topics: recipes, meal-planning, nutrition-facts, dietary-guidelines
    
    Example filenames:
    - breakfast_vegetarian_recipes.pdf → meal_type: breakfast, dietary_restriction: vegetarian, topic: recipes
    - diabetic_meal_planning.pdf → dietary_restriction: diabetic, topic: meal-planning
    
    Args:
        file: PDF file to upload and process (max 10MB)
        
    Returns:
        Processing result with document count
    """
    logger.info("Upload document (boilerplate)")

    # TODO: Validate the uploaded file and process it for indexing.
    # HINT: Validate filename and file extension (e.g., allow .pdf/.txt/.md).
    # HINT: Enforce a max upload size (e.g., 10MB) and return HTTP 400 when exceeded.
    # HINT: Persist the uploaded bytes somewhere accessible to your processing logic
    #       (temporary file, object storage, etc.).
    # HINT: Call your document processing/indexing service and return:
    #   - message: str
    #   - documents_indexed: int
    # HINT: Ensure cleanup of any temporary artifacts you create.
    # Your code here:

    # Validate filename and file extension (allow .pdf/.txt/.md)
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided.")

    allowed_extensions = {".pdf", ".txt", ".md"}
    _, ext = os.path.splitext(file.filename)
    if ext.lower() not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{ext}' is not allowed. Allowed types: {', '.join(allowed_extensions)}"
        )

    # Read uploaded bytes
    file_bytes = await file.read()

    # Enforce a max upload size (10MB) and return HTTP 400 when exceeded
    max_size_bytes = 10 * 1024 * 1024  # 10 MB
    if len(file_bytes) > max_size_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"File size {len(file_bytes)} bytes exceeds the 10MB limit."
        )

    # Persist the uploaded bytes to a temporary file for processing logic
    tmp_file_path = None
    try:
        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=ext.lower(),
            prefix="upload_"
        ) as tmp_file:
            tmp_file.write(file_bytes)
            tmp_file_path = tmp_file.name

        logger.info(f"Saved upload to temp file: {tmp_file_path} ({len(file_bytes)} bytes)")

        # Call document processing/indexing service
        result = rag_service.process_document(
            pdf_path=tmp_file_path,
            original_filename=file.filename,
        )

        return UploadResponse(
            message=result.get("message", "Document processed successfully"),
            documents_indexed=result.get("documents_indexed", 1),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing uploaded document: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error processing document: {str(e)}")

    finally:
        # Ensure cleanup of any temporary artifacts
        if tmp_file_path and os.path.exists(tmp_file_path):
            try:
                os.remove(tmp_file_path)
                logger.info(f"Cleaned up temp file: {tmp_file_path}")
            except Exception as cleanup_err:
                logger.warning(f"Could not remove temp file {tmp_file_path}: {cleanup_err}")


@router.post(
    "/query",
    response_model=QueryResponse,
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "examples": {
                        "no_filters": {
                            "summary": "No filters",
                            "value": {
                                "question": "What are some healthy breakfast options?",
                                "similarity_top_k": 3,
                            },
                        },
                        "meal_type_filter": {
                            "summary": "Filter by meal type",
                            "value": {
                                "question": "Give me healthy breakfast options.",
                                "similarity_top_k": 3,
                                "filters": {"meal_type": "breakfast"},
                            },
                        },
                        "multiple_filters": {
                            "summary": "Filter by meal type + dietary restriction",
                            "value": {
                                "question": "Give me healthy breakfast options.",
                                "similarity_top_k": 3,
                                "filters": {
                                    "meal_type": "breakfast",
                                    "dietary_restriction": "vegetarian",
                                },
                            },
                        },
                        "diabetic_meal_planning": {
                            "summary": "Filter by dietary restriction + topic",
                            "value": {
                                "question": "Suggest a 1-day meal plan.",
                                "similarity_top_k": 3,
                                "filters": {
                                    "dietary_restriction": "diabetic",
                                    "topic": "meal-planning",
                                },
                            },
                        },
                    }
                }
            }
        }
    },
)
async def query_documents(request: QueryRequest):
    """
    Query the diet counselling system with optional metadata filtering.
    
    Supports filtering by:
    - meal_type: breakfast, lunch, dinner, snack
    - dietary_restriction: vegetarian, vegan, gluten-free, keto, diabetic, low-sodium
    - nutrition_category: protein, carbohydrates, vitamins, minerals, healthy-fats
    - topic: recipes, meal-planning, nutrition-facts, dietary-guidelines
    
    Args:
        request: Query request with question, similarity_top_k, and optional filters
        
    Returns:
        Answer to the query along with retrieved source nodes
    """
    logger.info(
        f"Received query request: question='{request.question[:50]}...', "
        f"similarity_top_k={request.similarity_top_k}, filters={request.filters}"
    )
    
    try:
        answer, nodes = rag_service.query(
            request.question,
            similarity_top_k=request.similarity_top_k,
            filters=request.filters
        )
        
        # Convert nodes to NodeInfo format
        node_infos = []
        for node in nodes:
            # Handle both NodeWithScore and direct Node objects
            if hasattr(node, 'node'):
                node_obj = node.node
                score = getattr(node, 'score', None)
            else:
                node_obj = node
                score = None
            
            # Extract text and metadata
            text = getattr(node_obj, 'text', str(node_obj))
            metadata = getattr(node_obj, 'metadata', None)
            
            node_infos.append(NodeInfo(
                text=text,
                score=score,
                metadata=metadata
            ))
        
        logger.info(
            f"Query completed successfully, answer length: {len(answer)} characters, "
            f"{len(node_infos)} nodes returned"
        )
        
        return QueryResponse(answer=answer, source_nodes=node_infos)
        
    except ValueError as e:
        # ValueError is raised when index is not initialized
        if "Index not initialized" in str(e) or "not initialized" in str(e).lower():
            logger.warning("Query attempted but no document has been processed yet")
            raise HTTPException(
                status_code=400,
                detail="No document has been processed yet. Please upload a document first."
            )
        raise
    except Exception as e:
        logger.error(f"Error processing query: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")    