"""
Routes Module
FastAPI route handlers for document upload and querying.
"""

import os
import re
import logging
import tempfile
import datetime
import asyncio
from typing import List
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field, field_validator
from llama_index.core import SimpleDirectoryReader
from main.service.rag_service import get_query_engine, add_documents_to_index
from main.evaluation.dataset import get_langfuse_client
from main.evaluation.dataset_evaluation import (
    evaluate_faithfulness_score,
    evaluate_answer_relevance,
)
from main.handoff.handoff_service import (
    evaluate_score,
    send_handoff_email,
    generate_handoff_reference_id,
    evaluate_explicit_user_request,
    evaluate_confidence_score,
)
import secrets

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
    user_email: str = Field(..., min_length=3, max_length=320, description="User email for human handoff follow-up")
    
    @field_validator('question')
    @classmethod
    def validate_question(cls, v):
        """Validate and sanitize question input."""
        if not v or not v.strip():
            raise ValueError("Question cannot be empty")
        return v.strip()

    @field_validator("user_email")
    @classmethod
    def validate_user_email(cls, v: str):
        v = (v or "").strip()
        if "@" not in v or v.startswith("@") or v.endswith("@"):
            raise ValueError("Invalid user_email")
        return v


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
    """
    Sanitize filename to prevent path traversal and other security issues.
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename safe for filesystem operations
    """
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
    """
    Upload a document file for indexing.
    
    Accepts: .txt, .pdf, .md files (max 10MB)
    
    Returns:
        UploadResponse with message and number of documents indexed
    """
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
async def query_rag(request: QueryRequest, background_tasks: BackgroundTasks):
    """Query RAG system with evaluation and human handoff logic."""
    # TODO: Implement query endpoint with handoff logic
    
    # 1. Setup: Generate session_id, initialize conversation_flow
    # 2. RAG Query: Get query engine, execute query, build full_chunks list
    # 3. Langfuse: Start span, get trace_id
    # 4. Evaluations: Run faithfulness, relevance, confidence, explicit request checks (all async)
    # 5. Handoff Decision (priority order):
    #    - Explicit request → high priority
    #    - Confidence + risk → high priority
    #    - Score-based → normal priority
    # 6. If handoff triggered:
    #    - Generate reference_id, build handoff_context with all fields
    #    - Send email via background_tasks
    #    - Return fallback message with reference_id
    # 7. Normal response: Format source_nodes (truncate to 200 chars), return answer
    # 8. Error handling: Wrap in try/except, log errors, raise HTTPException

    try:
        # 1. Setup: Generate session_id, initialize conversation_flow
        session_id = secrets.token_hex(8)
        conversation_flow = ["session_start", "input_received"]
        logger.info(f"Session {session_id} started for user: {request.user_email}")

        # 2. RAG Query: Get query engine, execute query, build full_chunks list
        query_engine = get_query_engine(similarity_top_k=2)
        conversation_flow.append("rag_query_executed")

        response = query_engine.query(request.question)
        answer = str(response)

        # Build full_chunks list from source nodes
        full_chunks: List[str] = []
        if hasattr(response, "source_nodes") and response.source_nodes:
            for node in response.source_nodes:
                try:
                    full_chunks.append(node.text)
                except Exception:
                    continue

        no_chunks = len(full_chunks) == 0
        conversation_flow.append(f"chunks_retrieved: {len(full_chunks)}")
        logger.info(f"Session {session_id}: retrieved {len(full_chunks)} chunk(s)")

        # 3. Langfuse: Start span, get trace_id
        # Note: Langfuse v4 uses create_trace_id() + start_observation() instead of start_span()
        langfuse = get_langfuse_client()
        trace_id = langfuse.create_trace_id()
        span = langfuse.start_observation(
            trace_context={"trace_id": trace_id},
            name="rag_query_with_handoff",
            input={"question": request.question, "user_email": request.user_email},
            metadata={"session_id": session_id},
        )
        conversation_flow.append(f"langfuse_trace: {trace_id}")

        # Build context string for faithfulness evaluation
        context = "\n\n".join(full_chunks)

        # 4. Evaluations: Run faithfulness, relevance, confidence, explicit request checks (all async)
        faithfulness_task = asyncio.create_task(
            evaluate_faithfulness_score(langfuse, trace_id, request.question, context, answer)
        )
        relevance_task = asyncio.create_task(
            evaluate_answer_relevance(langfuse, trace_id, request.question, answer)
        )
        confidence_task = asyncio.create_task(
            evaluate_confidence_score(answer)
        )
        explicit_task = asyncio.create_task(
            evaluate_explicit_user_request(request.question)
        )

        faithfulness_score, relevance_score, confidence_result, explicit_result = await asyncio.gather(
            faithfulness_task, relevance_task, confidence_task, explicit_task
        )
        conversation_flow.append("evaluations_complete")

        logger.info(
            f"Session {session_id} "
            f"explicit_trigger={explicit_result.get('trigger')} "
            f"confidence_trigger={confidence_result.get('trigger')} "
            f"faithfulness={faithfulness_score:.2f} "
            f"relevance={relevance_score:.2f}"
        )

        # 5. Handoff Decision (priority order):
        #    - Explicit request → high priority
        #    - Confidence + risk → high priority
        #    - Score-based → normal priority
        handoff_triggered = False
        handoff_priority = "normal"
        handoff_reason = ""

        # Priority 1: Explicit user request for human help
        if explicit_result.get("trigger"):
            handoff_triggered = True
            handoff_priority = "high"
            handoff_reason = explicit_result.get("reason", "user explicitly requested human assistance")
            conversation_flow.append("handoff_trigger: explicit_user_request (high priority)")

        # Priority 2: Low confidence combined with score-based risk
        if not handoff_triggered and confidence_result.get("trigger"):
            score_result = evaluate_score(faithfulness_score, relevance_score, request.question, no_chunks)
            if score_result.get("trigger"):
                handoff_triggered = True
                handoff_priority = "high"
                handoff_reason = confidence_result.get("reason", "low confidence score")
                conversation_flow.append("handoff_trigger: confidence + score risk (high priority)")

        # Priority 3: Score-based trigger alone
        if not handoff_triggered:
            score_result = evaluate_score(faithfulness_score, relevance_score, request.question, no_chunks)
            if score_result.get("trigger"):
                handoff_triggered = True
                handoff_priority = "normal"
                handoff_reason = score_result.get("reason", "evaluation score below threshold")
                conversation_flow.append(f"handoff_trigger: score-based ({handoff_reason}) (normal priority)")

        # Update span and end it
        span.update(output={"answer": answer, "handoff_triggered": handoff_triggered})
        span.end()

        # 6. If handoff triggered:
        #    - Generate reference_id, build handoff_context with all fields
        #    - Send email via background_tasks
        #    - Return fallback message with reference_id
        if handoff_triggered:
            reference_id = generate_handoff_reference_id()
            conversation_flow.append(f"handoff_initiated: {reference_id}")

            handoff_context = {
                "reference_id": reference_id,
                "trace_id": trace_id,
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "priority": handoff_priority,
                "trigger_reason": handoff_reason,
                "user_metadata": {
                    "user_email": request.user_email,
                    "session_id": session_id,
                },
                "query_history": [request.question],
                "generated_answer": answer,
                "evaluation_scores": {
                    "faithfulness": faithfulness_score,
                    "relevance": relevance_score,
                    "confidence": confidence_result.get("confidence"),
                },
                "retrieved_chunks": full_chunks,
                "conversation_flow": conversation_flow,
            }

            background_tasks.add_task(send_handoff_email, handoff_context)
            logger.info(
                f"Session {session_id}: handoff triggered (priority={handoff_priority}, "
                f"reason={handoff_reason}, ref={reference_id})"
            )

            fallback_message = (
                f"I wasn't able to provide a confident answer to your question. "
                f"Your request has been escalated to our support team who will follow up "
                f"with you at {request.user_email}. "
                f"Your reference ID is: {reference_id}"
            )
            return QueryResponse(answer=fallback_message, source_nodes=[])

        # 7. Normal response: Format source_nodes (truncate to 200 chars), return answer
        conversation_flow.append("normal_response_returned")
        source_nodes = []
        if hasattr(response, "source_nodes") and response.source_nodes:
            for node in response.source_nodes:
                try:
                    source_nodes.append({
                        "text": node.text[:200] if node.text else "",
                        "score": node.score if hasattr(node, "score") else None,
                    })
                except Exception:
                    continue

        logger.info(f"Session {session_id}: normal response returned with {len(source_nodes)} source node(s)")
        return QueryResponse(answer=answer, source_nodes=source_nodes)

    # 8. Error handling: Wrap in try/except, log errors, raise HTTPException
    except HTTPException:
        raise
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