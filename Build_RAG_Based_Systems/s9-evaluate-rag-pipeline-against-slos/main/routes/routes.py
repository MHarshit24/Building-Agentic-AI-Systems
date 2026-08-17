"""
Routes Module
FastAPI route handlers for document upload and querying.
"""

import os
import re
import logging
import asyncio
import tempfile
from typing import List
from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel, Field, field_validator
from llama_index.core import SimpleDirectoryReader
from main.service.rag_service import get_query_engine, add_documents_to_index
from main.evaluation.dataset import get_langfuse_client
from main.evaluation.dataset_evaluation import evaluate_faithfulness_score, evaluate_answer_relevance

logger = logging.getLogger(__name__)

router = APIRouter()

MAX_FILE_SIZE = 10 * 1024 * 1024
MAX_QUERY_LENGTH = 2000
MIN_SIMILARITY_TOP_K = 1
MAX_SIMILARITY_TOP_K = 20
ALLOWED_EXTENSIONS = {'.txt', '.pdf', '.md'}


class QueryRequest(BaseModel):
    """Request model for query endpoint."""
    question: str = Field(..., min_length=1, max_length=MAX_QUERY_LENGTH)
    
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


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "Sprint 9 Practice RAG API"}


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent path traversal and other security issues."""
    if not filename:
        raise ValueError("Filename cannot be empty")
    
    filename = os.path.basename(filename)
    filename = filename.replace('/', '_').replace('\\', '_')
    filename = re.sub(r'[^\w\s.-]', '', filename)
    
    if len(filename) > 255:
        name, ext = os.path.splitext(filename)
        filename = name[:250] + ext
    
    return filename


@router.post("/upload", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...)):
    """Upload a document file for indexing."""
    file_path = None
    try:
        if not file.filename:
            raise HTTPException(
                status_code=400,
                detail="Filename is required"
            )
        
        safe_filename = sanitize_filename(file.filename)
        file_ext = os.path.splitext(safe_filename)[1].lower()
        
        if file_ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"File type not supported. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
            )
        
        content = await file.read()
        
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File size exceeds maximum allowed size of {MAX_FILE_SIZE / (1024*1024):.1f}MB"
            )
        
        with tempfile.NamedTemporaryFile(
            mode='wb',
            suffix=file_ext,
            delete=False
        ) as tmp_file:
            tmp_file.write(content)
            file_path = tmp_file.name
        
        logger.info(f"File uploaded: {safe_filename} ({len(content)} bytes)")
        
        reader = SimpleDirectoryReader(input_files=[file_path])
        documents = reader.load_data()
        
        logger.info(f"Loaded {len(documents)} document(s) from {safe_filename}")
        
        result = add_documents_to_index(documents)
        
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
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as e:
                logger.warning(f"Failed to clean up temporary file {file_path}: {e}")


@router.post("/query", response_model=QueryResponse)
async def query_rag(request: QueryRequest):
    """
    Query the RAG system with a question.
    
    TODO: Add automatic evaluation and tracing:
    1. Import get_langfuse_client and evaluator functions
    2. Extract full context from source_nodes for evaluation
    3. Create Langfuse span for tracing
    4. Run faithfulness and answer relevance evaluators asynchronously
    5. Update span with scores and end it
    6. Handle evaluation errors gracefully (don't break API)
    """
    try:
        query_engine = get_query_engine(similarity_top_k=1)
        
        logger.info(f"Received query (similarity_top_k=1)")
        
        response = query_engine.query(request.question)
        answer = str(response)
        
        source_nodes = []
        # TODO: Also extract full context chunks for evaluation (not truncated)
        eval_context_chunks = []
        
        if hasattr(response, 'source_nodes') and response.source_nodes:
            for node in response.source_nodes:
                text = getattr(node, "text", "") or ""
                
                # TODO: Add full text to eval_context_chunks for evaluation
                # Add full text to eval_context_chunks for evaluation
                if text:
                    eval_context_chunks.append(text)
                
                display_text = text[:200] + "..." if len(text) > 200 else text
                source_nodes.append({
                    "text": display_text,
                    "score": float(node.score) if hasattr(node, 'score') else None,
                    "metadata": node.metadata if hasattr(node, 'metadata') else {}
                })
        
        # TODO: Join eval_context_chunks with "\n\n" to create eval_context
        # Join eval_context_chunks with "\n\n" to create eval_context
        eval_context = "\n\n".join(eval_context_chunks)
        
        # TODO: Add automatic evaluation and tracing
        # 1. Get Langfuse client
        # 2. Create span with name="api_query", input={"question": request.question}, metadata
        # 3. Get trace_id from span
        # 4. Run evaluate_faithfulness_score() and evaluate_answer_relevance() asynchronously
        # 5. Update span with scores and end it
        # 6. Wrap in try/except to handle evaluation errors gracefully
        try:
            # 1. Get Langfuse client
            langfuse = get_langfuse_client()

            # 2. Create span with name="api_query", input={"question": request.question}, metadata
            # Note: Langfuse v4 uses create_trace_id() + start_observation() instead of start_span()
            trace_id = langfuse.create_trace_id()
            span = langfuse.start_observation(
                trace_context={"trace_id": trace_id},
                name="api_query",
                input={"question": request.question},
                metadata={"similarity_top_k": 1, "source": "api_endpoint"}
            )

            # 3. Get trace_id from span
            # trace_id already set above via create_trace_id()

            # 4. Run evaluate_faithfulness_score() and evaluate_answer_relevance() asynchronously
            faithfulness_score, answer_relevance_score = await asyncio.gather(
                evaluate_faithfulness_score(langfuse, trace_id, request.question, eval_context, answer),
                evaluate_answer_relevance(langfuse, trace_id, request.question, answer)
            )

            # 5. Update span with scores and end it
            span.update(
                output={
                    "answer": answer,
                    "faithfulness_score": faithfulness_score,
                    "answer_relevance_score": answer_relevance_score
                }
            )
            span.end()
            langfuse.flush()

            logger.info(f"✓ Evaluation complete — faithfulness: {faithfulness_score:.2f}, relevance: {answer_relevance_score:.2f}")

        except Exception as e:
            # 6. Handle evaluation errors gracefully (don't break API)
            logger.warning(f"Evaluation/tracing failed (non-fatal): {e}")
        
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
        "message": "Sprint 9 Practice RAG API",
        "version": "1.0.0",
        "endpoints": {
            "POST /upload": "Upload documents for indexing",
            "POST /query": "Query the RAG system",
            "GET /health": "Health check"
        }
    }