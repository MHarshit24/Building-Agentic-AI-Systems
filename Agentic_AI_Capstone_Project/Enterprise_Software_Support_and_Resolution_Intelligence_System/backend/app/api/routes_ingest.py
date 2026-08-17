"""
app/api/routes_ingest.py

POST /ingest, GET /ingest/{job_id} — §8.1, §17. Admin-only (§16),
POST rate-limited 5/minute per-user (§16.1's explicit table entry for
this endpoint); GET isn't listed in §16.1's table, so it gets the same
looser 60/minute bucket already used for the other admin/support GET
endpoints (routes_conversations.py) — read-heavy, low-cost, no reason to
constrain polling for job status.

Extraction/embedding work is dispatched via FastAPI BackgroundTasks —
the same "do the slow/costed part after the response is already on its
way back" pattern §7 describes for notify_human()'s Mailtrap dispatch —
so the request returns 202 immediately and never blocks on however long
extraction+embedding takes for a given document.
"""

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import IngestedAsset, IngestionJob, IngestionJobStatus
from app.db.session import get_db
from app.ingestion.pipeline import run_ingestion, slugify_document_id
from app.middleware.rate_limit import limiter
from app.middleware.rbac_check import require_admin
from app.schemas.ingest import IngestDeleteResponse, IngestResponse, IngestStats, IngestStatusResponse

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("", response_model=IngestResponse, status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("5/minute")
async def ingest_document(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    doc_title: str | None = Form(default=None),
    product_version: str | None = Form(default=None),
    category: str | None = Form(default=None),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
) -> IngestResponse:
    """
    §8.1: multipart upload only — URL-reference ingestion is out of
    scope for this endpoint. document_id is derived from the uploaded
    file's own filename (schemas/ingest.py documents the full design
    decision), never supplied by the caller.

    The job row is created and committed *before* the background task is
    dispatched (the FastAPI response — and therefore the client ever
    seeing it — can't happen until after that commit either way), so a
    client polling GET /ingest/{job_id} immediately after receiving this
    response can already find it.
    """
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File must have a filename")

    file_bytes = await file.read()
    document_id = slugify_document_id(file.filename)
    job_id = str(uuid.uuid4())

    db.add(IngestionJob(job_id=job_id, document_id=document_id, status=IngestionJobStatus.pending))

    background_tasks.add_task(
        run_ingestion,
        job_id=job_id,
        document_id=document_id,
        file_bytes=file_bytes,
        doc_title=doc_title or file.filename,
        product_version=product_version,
        category=category,
    )

    await db.commit()

    return IngestResponse(job_id=job_id, status="pending")


@router.get("/{job_id}", response_model=IngestStatusResponse)
@limiter.limit("60/minute")
async def get_ingest_status(
    request: Request,
    job_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
) -> IngestStatusResponse:
    result = await db.execute(select(IngestionJob).where(IngestionJob.job_id == job_id))
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ingestion job not found")

    return IngestStatusResponse(
        job_id=job.job_id,
        document_id=job.document_id,
        status=job.status.value,
        stats=IngestStats(**job.stats_json) if job.stats_json else None,
    )


@router.delete("/{document_id}", response_model=IngestDeleteResponse)
@limiter.limit("5/minute")
async def delete_document(
    request: Request,
    document_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
) -> IngestDeleteResponse:
    """
    Soft-retires every active IngestedAsset row for this document_id —
    never a hard delete, matching this project's own soft-retire
    convention (§21/§22, same shape as is_active on users). Relies on
    vector_search.py/keyword_search.py's is_active join (production-
    readiness gap analysis, deletion item 1) to actually stop this
    content from surfacing in retrieval — without that join this
    endpoint would report success while changing nothing observable.

    404 if document_id never existed, or every asset for it is already
    inactive (idempotent — a second delete of the same document reads as
    "nothing to delete," not an error).
    """
    result = await db.execute(
        update(IngestedAsset)
        .where(IngestedAsset.document_id == document_id, IngestedAsset.is_active.is_(True))
        .values(is_active=False)
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found or already inactive")

    await db.commit()
    return IngestDeleteResponse(document_id=document_id, assets_retired=result.rowcount)
