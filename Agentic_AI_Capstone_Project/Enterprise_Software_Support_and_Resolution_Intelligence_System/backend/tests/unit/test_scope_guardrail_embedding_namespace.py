"""
tests/unit/test_scope_guardrail_embedding_namespace.py

Regression test for the same real, confirmed cross-provider bug as
test_retrieval_embedding_namespace_filter.py, applied to
app/guardrails/scope_guardrail.py's Layer B centroid check:
compute_corpus_centroid() used to average EVERY embedded chunk/table row
regardless of which provider produced it, then compared that centroid
against a live query's CURRENT-provider embedding — a silently
meaningless comparison after a real LLM_PROVIDER fallback. Fixed by
filtering the centroid computation to only the currently active
provider's embedding_namespace.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy import delete

from app.db.models import Chunk, IngestedAsset
from app.db.session import async_session_maker
from app.guardrails.scope_guardrail import compute_corpus_centroid


@pytest_asyncio.fixture
async def seeded_mixed_namespace_chunks():
    """Two rows with deliberately DIFFERENT, easily-distinguished
    embeddings AND different embedding_namespace values — only the
    "mock"-namespaced one should ever enter the centroid average, since
    this suite's real active provider is LLM_PROVIDER=mock."""
    mock_embedding = [1.0] * 1536
    azure_embedding = [-1.0] * 1536
    created_asset_ids: list[int] = []
    created_chunk_ids: list[int] = []

    async with async_session_maker() as session:
        mock_asset = IngestedAsset(
            document_id="centroid_regression_doc_mock",
            asset_type="chunk",
            asset_hash="hash_centroid_mock_regression",
            is_active=True,
        )
        azure_asset = IngestedAsset(
            document_id="centroid_regression_doc_azure",
            asset_type="chunk",
            asset_hash="hash_centroid_azure_regression",
            is_active=True,
        )
        session.add_all([mock_asset, azure_asset])
        await session.flush()

        mock_chunk = Chunk(
            asset_id=mock_asset.asset_id,
            text="centroid regression marker mock namespace",
            embedding=mock_embedding,
            embedding_namespace="mock",
            source_document="Mock Namespace Doc",
            category="usage",
        )
        azure_chunk = Chunk(
            asset_id=azure_asset.asset_id,
            text="centroid regression marker azure namespace",
            embedding=azure_embedding,
            embedding_namespace="azure:text-embedding-3-small",
            source_document="Azure Namespace Doc",
            category="usage",
        )
        session.add_all([mock_chunk, azure_chunk])
        await session.commit()
        await session.refresh(mock_chunk)
        await session.refresh(azure_chunk)

        created_asset_ids.extend([mock_asset.asset_id, azure_asset.asset_id])
        created_chunk_ids.extend([mock_chunk.chunk_id, azure_chunk.chunk_id])

    yield

    async with async_session_maker() as session:
        await session.execute(delete(Chunk).where(Chunk.chunk_id.in_(created_chunk_ids)))
        await session.execute(delete(IngestedAsset).where(IngestedAsset.asset_id.in_(created_asset_ids)))
        await session.commit()


@pytest.mark.asyncio
async def test_centroid_only_averages_rows_matching_the_current_provider_namespace(
    seeded_mixed_namespace_chunks,
):
    centroid = await compute_corpus_centroid()

    # If the bug were still present, averaging [1.0]*1536 and [-1.0]*1536
    # would pull the centroid toward 0.0 for every dimension. With the
    # fix, only the "mock"-namespaced row (all 1.0s) is real production
    # candidate data for LLM_PROVIDER=mock, so the centroid should be
    # heavily weighted toward 1.0 wherever this pair dominates the real
    # corpus (may not be exactly 1.0 if the real dev corpus also has
    # other real mock-namespaced rows, but must be unambiguously positive,
    # never pulled toward 0 or negative by the excluded Azure row).
    assert all(v > 0.0 for v in centroid), (
        "the centroid must never be pulled toward the excluded, differently-namespaced row's "
        "embedding — this is exactly the cross-provider contamination this test guards against"
    )
