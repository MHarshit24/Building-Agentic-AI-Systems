from __future__ import annotations

import logging
import os
from typing import List, Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from llama_index.core import Document

from main.service.ingestion_pipeline import IngestionPipeline
from main.service.rag_service import RAGService
import time


router = APIRouter(prefix="/api/ingestion", tags=["ingestion"])
logger = logging.getLogger(__name__)

# Global state: keep a service instance for this process
_active_service: Optional[RAGService] = None


class UploadResponse(BaseModel):
    message: str
    uploaded_files: List[str]
    total_documents: int
    total_chunks: int


@router.post("/upload", response_model=UploadResponse)
async def upload(files: List[UploadFile] = File(..., description=".txt or .pdf files")):
    """Upload docs (in-memory read), then persist embeddings to Postgres."""
    global _active_service

    tmp_dir = os.getenv("TMP_UPLOAD_DIR", "/tmp")
    os.makedirs(tmp_dir, exist_ok=True)

    # We still avoid keeping originals long-term; we use a tmp path for PDF parsing.
    saved_paths: List[str] = []
    uploaded_files: List[str] = []

    try:
        t0 = time.perf_counter()
        logger.info("upload.request files=%d tmp_dir=%s", len(files), tmp_dir)
        for f in files:
            if not (f.filename.endswith(".txt") or f.filename.endswith(".pdf")):
                raise HTTPException(status_code=400, detail=f"Unsupported file type: {f.filename}")

            target_path = os.path.join(tmp_dir, f"investment_rag_{f.filename}")
            content = await f.read()
            with open(target_path, "wb") as out:
                out.write(content)

            saved_paths.append(target_path)
            uploaded_files.append(f.filename)

        pipeline = IngestionPipeline()
        result = pipeline.ingest_paths(saved_paths)

        _active_service = RAGService(table_name=result.table_name)

        logger.info(
            "upload.success total_documents=%d total_chunks=%d uploaded_files=%s",
            result.total_documents,
            result.total_chunks,
            uploaded_files,
        )
        logger.info("upload.done ms=%.1f", (time.perf_counter() - t0) * 1000)
        return UploadResponse(
            message="Upload ingested. Embeddings stored in Postgres.",
            uploaded_files=uploaded_files,
            total_documents=result.total_documents,
            total_chunks=result.total_chunks,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("upload.error %s", e)
        raise HTTPException(status_code=500, detail=f"Upload failed: {e}")


def get_active_service() -> RAGService:
    """Return an initialized RAGService, loading from Postgres if needed."""
    global _active_service

    if _active_service is None:
        table = os.getenv("DB_TABLE_NAME", "investment_advisor_docs")
        logger.info("active_service.init table=%s", table)
        _active_service = RAGService(table_name=table)

    return _active_service
