"""
tests/unit/test_retrieval_is_active_filter.py

Direct regression test for a real, confirmed bug found during the
production-readiness gap analysis (document-deletion investigation):
IngestedAsset.is_active was a bookkeeping-only flag, never consulted by
vector_search.py/keyword_search.py — a soft-retired document (or a
document soft-retired by the new DELETE /ingest/{document_id} endpoint)
would still surface in every search result. Fixed by joining to
IngestedAsset and filtering is_active=True in both files' shared
_search_one_table() (applies identically to all four asset types via
ASSET_TABLES — chunk/table/image/diagram — since both files loop over
the same registry).

Seeds real IngestedAsset/Chunk rows directly via the disposable test DB
(no fixture exists for this shape yet, same "insert directly via the DB
session" pattern as tests/integration/test_rbac_violations.py's
make_customer-adjacent tests) — one active, one inactive, otherwise
identical, so any difference in what's returned is attributable only to
is_active, not content.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy import delete

from app.db.models import Chunk, IngestedAsset
from app.db.session import async_session_maker
from app.retrieval.keyword_search import keyword_search
from app.retrieval.vector_search import vector_search

_DISTINCTIVE_TEXT = "zzqx_regression_marker_unique_phrase for is_active filtering"


@pytest_asyncio.fixture
async def seeded_active_and_inactive_chunks():
    """One active, one inactive IngestedAsset+Chunk pair, identical
    embeddings/text otherwise — only is_active differs."""
    same_embedding = [0.01] * 1536
    created_asset_ids: list[int] = []
    created_chunk_ids: list[int] = []

    async with async_session_maker() as session:
        active_asset = IngestedAsset(
            document_id="regression_doc_active",
            asset_type="chunk",
            asset_hash="hash_active_regression",
            is_active=True,
        )
        inactive_asset = IngestedAsset(
            document_id="regression_doc_inactive",
            asset_type="chunk",
            asset_hash="hash_inactive_regression",
            is_active=False,
        )
        session.add_all([active_asset, inactive_asset])
        await session.flush()

        active_chunk = Chunk(
            asset_id=active_asset.asset_id,
            text=_DISTINCTIVE_TEXT,
            embedding=same_embedding,
            embedding_namespace="mock",  # matches MockLLMClient.embedding_namespace — LLM_PROVIDER=mock is this suite's default
            source_document="Active Doc",
            category="usage",
        )
        inactive_chunk = Chunk(
            asset_id=inactive_asset.asset_id,
            text=_DISTINCTIVE_TEXT,
            embedding=same_embedding,
            embedding_namespace="mock",
            source_document="Inactive Doc",
            category="usage",
        )
        session.add_all([active_chunk, inactive_chunk])
        await session.commit()
        await session.refresh(active_chunk)
        await session.refresh(inactive_chunk)

        created_asset_ids.extend([active_asset.asset_id, inactive_asset.asset_id])
        created_chunk_ids.extend([active_chunk.chunk_id, inactive_chunk.chunk_id])

    yield {"active_chunk_id": active_chunk.chunk_id, "inactive_chunk_id": inactive_chunk.chunk_id}

    async with async_session_maker() as session:
        await session.execute(delete(Chunk).where(Chunk.chunk_id.in_(created_chunk_ids)))
        await session.execute(delete(IngestedAsset).where(IngestedAsset.asset_id.in_(created_asset_ids)))
        await session.commit()


@pytest.mark.asyncio
async def test_vector_search_never_returns_inactive_asset(seeded_active_and_inactive_chunks):
    ids = seeded_active_and_inactive_chunks
    results = await vector_search("regression marker query", top_k=10)

    returned_ids = {r.asset_row_id for r in results if r.asset_type == "chunk"}
    assert ids["active_chunk_id"] in returned_ids
    assert ids["inactive_chunk_id"] not in returned_ids


@pytest.mark.asyncio
async def test_keyword_search_never_returns_inactive_asset(seeded_active_and_inactive_chunks):
    ids = seeded_active_and_inactive_chunks
    results = await keyword_search("zzqx_regression_marker_unique_phrase", top_k=10)

    returned_ids = {r.asset_row_id for r in results if r.asset_type == "chunk"}
    assert ids["active_chunk_id"] in returned_ids
    assert ids["inactive_chunk_id"] not in returned_ids
