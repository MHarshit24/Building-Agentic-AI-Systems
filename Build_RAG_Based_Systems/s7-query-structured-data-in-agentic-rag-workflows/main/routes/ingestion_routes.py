"""
Ingestion Routes - API endpoints for ingesting policy documents
"""
from typing import List
import logging

from fastapi import APIRouter, UploadFile, File, HTTPException
from llama_index.core import Document

from main.service.tools import add_documents


# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/documents/upload")
async def upload_documents(files: List[UploadFile] = File(...)):
    """
    Upload one or more text documents and ingest them into the pgvector-backed store.
    """
    try:
        logger.info(f"Starting document upload for {len(files)} file(s)")
        
        docs: list[Document] = []
        for file in files:
            logger.info(f"Processing file: {file.filename}")
            raw = await file.read()
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                logger.error(f"Failed to decode file {file.filename} as UTF-8")
                raise HTTPException(
                    status_code=400,
                    detail=f"File {file.filename} is not valid UTF-8 text.",
                )
            docs.append(
                Document(
                    text=text,
                    metadata={"filename": file.filename},
                )
            )
        
        logger.info(f"Created {len(docs)} Document objects, calling add_documents()...")
        
        ingestion_result = add_documents(docs)
        
        logger.info(f"Successfully ingested {len(docs)} document(s)")

        return {
            "uploaded": len(docs),
            "filenames": [f.filename for f in files],
            "nodes_created": ingestion_result["nodes_count"],
            "table_name": ingestion_result["table_name"]
        }
    except HTTPException:
        # re-raise HTTPExceptions as-is
        raise
    except Exception as e:
        logger.error(f"Failed to ingest documents: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to ingest documents: {e}",
        )
