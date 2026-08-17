"""
app/api/routes_documents.py

GET /documents — frontend integration pass (A5). Admin-only, read-only
listing of every currently-active ingested document. §17's original 9
endpoints had no way to answer "what has been ingested" short of already
knowing a document_id (DELETE /ingest/{document_id}) or a job_id
(GET /ingest/{job_id}) — this closes that gap for the frontend's document
library view.

No dedicated schemas/documents.py exists in §18's folder structure, so
the response model is defined inline here — same choice already made in
routes_conversations.py for the same reason.
"""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DocumentStatus, DocumentVersion, IngestedAsset
from app.db.session import get_db
from app.middleware.rate_limit import limiter
from app.middleware.rbac_check import require_admin

router = APIRouter(prefix="/documents", tags=["documents"])


class DocumentSummary(BaseModel):
    document_id: str
    doc_title: str | None = None
    product_version: str | None = None
    category: str | None = None
    ingested_at: str
    content_hash: str
    active_asset_count: int


class DocumentListResponse(BaseModel):
    documents: list[DocumentSummary]


@router.get("", response_model=DocumentListResponse)
@limiter.limit("60/minute")
async def list_documents(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
) -> DocumentListResponse:
    """
    One row per document_id — its current active DocumentVersion (§8.3:
    exactly one active row per document_id at a time by construction),
    left-joined against a live count of its still-active IngestedAsset
    rows so the frontend can show something more useful than just
    "ingested". A document whose every asset was soft-retired via
    DELETE /ingest/{document_id} without superseding it would show 0 —
    itself informative rather than hidden.
    """
    asset_counts_subq = (
        select(
            IngestedAsset.document_id,
            func.count(IngestedAsset.asset_id).label("active_asset_count"),
        )
        .where(IngestedAsset.is_active.is_(True))
        .group_by(IngestedAsset.document_id)
        .subquery()
    )

    stmt = (
        select(DocumentVersion, asset_counts_subq.c.active_asset_count)
        .outerjoin(asset_counts_subq, DocumentVersion.document_id == asset_counts_subq.c.document_id)
        .where(DocumentVersion.status == DocumentStatus.active)
        .order_by(DocumentVersion.ingested_at.desc())
    )
    result = await db.execute(stmt)

    return DocumentListResponse(
        documents=[
            DocumentSummary(
                document_id=doc.document_id,
                doc_title=doc.doc_title,
                product_version=doc.product_version,
                category=doc.category,
                ingested_at=doc.ingested_at.isoformat(),
                content_hash=doc.content_hash,
                active_asset_count=count or 0,
            )
            for doc, count in result.all()
        ]
    )
