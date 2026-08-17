"""
FinDoc Analyzer — POST /api/v1/ingest
Dual .env loader: root .env (secrets) + project .env (config).
ingest_routes.py: main/routes/ingest_routes.py
  parents[5] = Building_Agentic_AI_Systems  -> root .env
  parents[2] = FinDoc Analyzer              -> project .env

Updated (Sprint5 Multimodal Enhancement):
  - After table/SQL extraction, image documents produced by PDFImageAnalyzer
    are fed back into ingest_documents() so LLM chart analyses are indexed
    in PGVector alongside text chunks — enabling RAG queries over chart data.
"""

import os
import re
import sys
import logging
import tempfile
import uuid
from pathlib import Path
from typing import Optional
from urllib.parse import quote_plus
from dotenv import load_dotenv

from fastapi import APIRouter, UploadFile, File, HTTPException, Form, BackgroundTasks, status
from llama_index.core import SimpleDirectoryReader

from main.models import IngestResponse
from main.services.rag_service import ingest_documents
from main.services.sql_service import setup_financial_tables
from main.services.table_extractor import extract_and_store_financial_data

router = APIRouter()
logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".pdf", ".txt", ".csv", ".xlsx", ".xls", ".md"}
MAX_FILE_SIZE_MB   = int(os.getenv("MAX_FILE_SIZE_MB", "50"))


def _load_env():
    if "pytest" in sys.modules:
        return
    base_dir = Path(__file__).resolve().parents[5]
    base_env_path = base_dir / ".env"
    if base_env_path.exists():
        load_dotenv(dotenv_path=base_env_path)
    else:
        load_dotenv()
        logger.warning(f"Root .env not found at {base_env_path}")
    _preserved = {
        "DB_PASSWORD":           os.getenv("DB_PASSWORD"),
        "AZURE_OPENAI_API_KEY":  os.getenv("AZURE_OPENAI_API_KEY"),
        "AZURE_OPENAI_ENDPOINT": os.getenv("AZURE_OPENAI_ENDPOINT"),
        "LANGFUSE_PUBLIC_KEY":   os.getenv("LANGFUSE_PUBLIC_KEY"),
        "LANGFUSE_SECRET_KEY":   os.getenv("LANGFUSE_SECRET_KEY"),
        "LANGFUSE_HOST":         os.getenv("LANGFUSE_HOST"),
    }
    proj_dir = Path(__file__).resolve().parents[2]
    proj_env_path = proj_dir / ".env"
    if proj_env_path.exists():
        load_dotenv(dotenv_path=proj_env_path, override=True)
    else:
        load_dotenv()
        logger.warning(f"Project .env not found at {proj_env_path}")
    for key, val in _preserved.items():
        if val:
            os.environ[key] = val
    for var in ["DATABASE_URL", "POSTGRES_URL", "PGHOST", "PGPORT",
                "PGUSER", "PGPASSWORD", "PGDATABASE"]:
        os.environ.pop(var, None)


_load_env()


@router.post(
    "/ingest",
    response_model=IngestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest a financial document",
    description=(
        "Upload a financial report (PDF, TXT, CSV, XLSX). "
        "Pipeline: file validation → SimpleDirectoryReader → SentenceSplitter "
        "→ PGVector embedding store → table extraction → SQL insertion "
        "→ chart/image analysis via LLM vision → chart insights indexed in RAG."
    ),
)
async def ingest_document(
    background_tasks: BackgroundTasks,
    file:         UploadFile = File(..., description="Financial report (PDF/TXT/CSV/XLSX)"),
    company_name: Optional[str] = Form(None, description="Company name for metadata"),
    fiscal_year:  Optional[int] = Form(None, description="Fiscal year (e.g. 2024)"),
):
    """
    Full ingestion pipeline:
    1. Validate file type and size
    2. Save to temp file
    3. Load via SimpleDirectoryReader
    4. Run IngestionPipeline → PGVector
    5. Extract financial tables → SQL insertion
    6. Extract and analyze chart images via LLM vision (NEW)
    7. Index chart analysis Documents into PGVector RAG (NEW)
    8. Ensure SQL schema exists in background
    """
    file_path: Optional[str] = None

    try:
        # ── 1. Validate ───────────────────────────────────────────
        original_name = file.filename or "upload"
        safe_filename = re.sub(r"[^\w\-_. ]", "_", original_name)
        _, file_ext   = os.path.splitext(safe_filename.lower())

        if file_ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported type '{file_ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
            )

        content = await file.read()
        size_mb = len(content) / (1024 * 1024)
        if size_mb > MAX_FILE_SIZE_MB:
            raise HTTPException(
                status_code=413,
                detail=f"File {size_mb:.1f} MB exceeds limit of {MAX_FILE_SIZE_MB} MB",
            )

        logger.info(f"Processing upload: {safe_filename} ({size_mb:.2f} MB)")

        # ── 2. Write temp file ────────────────────────────────────
        with tempfile.NamedTemporaryFile(mode="wb", suffix=file_ext, delete=False) as tmp:
            tmp.write(content)
            file_path = tmp.name

        # ── 3. Load via SimpleDirectoryReader ─────────────────────
        reader    = SimpleDirectoryReader(input_files=[file_path])
        documents = reader.load_data()

        if not documents:
            raise HTTPException(
                status_code=400,
                detail="No content could be extracted from the file"
            )

        doc_id = str(uuid.uuid4())
        for doc in documents:
            doc.metadata.update({
                "source_file":  safe_filename,
                "document_id":  doc_id,
                "company_name": company_name or "unknown",
                "fiscal_year":  str(fiscal_year) if fiscal_year else "unknown",
                "file_type":    file_ext.lstrip("."),
            })

        logger.info(f"Loaded {len(documents)} document(s) from {safe_filename}")

        # ── 4. PGVector ingestion pipeline ────────────────────────
        rag_result = ingest_documents(documents, chunk_size=512, chunk_overlap=50)

        # ── 5 + 6. Table/SQL extraction + image analysis ──────────
        extraction_result = {
            "metrics_extracted":    0,
            "metrics_inserted":     0,
            "tables_found":         0,
            "footnotes_found":      0,
            "image_analyses_count": 0,
            "image_documents":      [],
        }

        if file_ext in (".pdf", ".csv", ".xlsx", ".xls"):
            try:
                extraction_result = extract_and_store_financial_data(
                    file_path=file_path,
                    company_name=company_name or "unknown",
                    fiscal_year=fiscal_year,
                    analyze_images=(file_ext == ".pdf"),  # images only from PDFs
                    original_filename=safe_filename,      # FIX: pass original filename
                )
                logger.info(
                    f"Extraction complete: "
                    f"{extraction_result['tables_found']} tables, "
                    f"{extraction_result['metrics_inserted']} SQL metrics, "
                    f"{extraction_result['image_analyses_count']} image analyses"
                )
            except Exception as e:
                logger.warning(f"Table/image extraction warning (non-fatal): {e}")

        # ── 7. Index chart analysis Documents into RAG (NEW) ──────
        image_docs       = extraction_result.get("image_documents", [])
        image_rag_result = {"documents_indexed": 0, "chunks_created": 0}

        if image_docs:
            # Tag image documents with same document_id for traceability
            for img_doc in image_docs:
                img_doc.metadata["document_id"] = doc_id
            try:
                image_rag_result = ingest_documents(
                    image_docs, chunk_size=1024, chunk_overlap=100
                )
                logger.info(
                    f"Indexed {image_rag_result['documents_indexed']} image analysis "
                    f"document(s) into RAG "
                    f"({image_rag_result['chunks_created']} chunks)"
                )
            except Exception as e:
                logger.warning(f"Image RAG indexing warning (non-fatal): {e}")

        # ── 8. Ensure SQL schema in background ────────────────────
        background_tasks.add_task(_ensure_sql_tables)

        tables_found     = extraction_result.get("tables_found", 0)
        metrics_inserted = extraction_result.get("metrics_inserted", 0)
        img_count        = extraction_result.get("image_analyses_count", 0)

        return IngestResponse(
            message=(
                f"Successfully ingested '{safe_filename}'. "
                f"Vector chunks: {rag_result['chunks_created']}. "
                f"Tables extracted: {tables_found}, "
                f"metrics stored in SQL: {metrics_inserted}. "
                f"Chart images analyzed and indexed: {img_count}."
            ),
            documents_indexed=rag_result["documents_indexed"] + image_rag_result["documents_indexed"],
            chunks_created=rag_result["chunks_created"] + image_rag_result["chunks_created"],
            document_id=doc_id,
            file_name=safe_filename,
            file_type=file_ext.lstrip("."),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ingestion failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Document ingestion failed: {str(e)}"
        )
    finally:
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as cleanup_err:
                logger.warning(f"Temp file cleanup failed: {cleanup_err}")


def _ensure_sql_tables():
    """Background task — ensure SQL schema exists."""
    try:
        setup_financial_tables()
    except Exception as e:
        logger.error(f"SQL table setup failed: {e}")