"""
tests/unit/test_retrieval_embedding_namespace_filter.py

Direct regression test for a real, confirmed bug found during a
codebase-wide LLM-fallback correctness audit: app/retrieval/
vector_search.py used to compare a live query's embedding (whichever
provider is currently active) against EVERY stored embedding row
regardless of which provider actually produced it. After a real
LLM_PROVIDER fallback (Azure -> Groq/Gemini, resolved once at process
startup, app/llm/provider_resolution.py), this meant comparing two
non-comparable embedding spaces via pgvector cosine distance, silently,
with zero error. Fixed by adding Chunk/TableAsset/Image/DiagramGraphRow.
embedding_namespace (app/db/models.py) and filtering vector_search.py's
query on it (BaseLLMClient.embedding_namespace, app/llm/base.py).

Same seed-directly-via-the-disposable-test-DB pattern as
test_retrieval_is_active_filter.py's own is_active regression test —
two otherwise-identical rows, one correctly namespaced for the test
suite's real active provider (LLM_PROVIDER=mock, embedding_namespace=
"mock"), one namespaced as if it had been embedded under a different
real provider, so any difference in what's returned is attributable
only to embedding_namespace, not content or embedding value (both rows
carry the SAME embedding vector, deliberately, to prove this is a real
namespace filter and not an accidental side effect of vector distance).
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy import delete

from app.db.models import Chunk, IngestedAsset
from app.db.session import async_session_maker
from app.retrieval.vector_search import vector_search

_DISTINCTIVE_TEXT = "zzqx_namespace_regression_marker unique phrase for embedding_namespace filtering"


@pytest_asyncio.fixture
async def seeded_mock_and_azure_namespaced_chunks():
    """Same embedding vector, same text, only embedding_namespace differs —
    one matches this suite's real active provider ("mock"), one pretends
    to have been embedded under Azure."""
    same_embedding = [0.02] * 1536
    created_asset_ids: list[int] = []
    created_chunk_ids: list[int] = []

    async with async_session_maker() as session:
        mock_asset = IngestedAsset(
            document_id="regression_doc_mock_namespace",
            asset_type="chunk",
            asset_hash="hash_mock_namespace_regression",
            is_active=True,
        )
        azure_asset = IngestedAsset(
            document_id="regression_doc_azure_namespace",
            asset_type="chunk",
            asset_hash="hash_azure_namespace_regression",
            is_active=True,
        )
        session.add_all([mock_asset, azure_asset])
        await session.flush()

        mock_chunk = Chunk(
            asset_id=mock_asset.asset_id,
            text=_DISTINCTIVE_TEXT,
            embedding=same_embedding,
            embedding_namespace="mock",
            source_document="Mock Namespace Doc",
            category="usage",
        )
        azure_chunk = Chunk(
            asset_id=azure_asset.asset_id,
            text=_DISTINCTIVE_TEXT,
            embedding=same_embedding,
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

    yield {"mock_chunk_id": mock_chunk.chunk_id, "azure_chunk_id": azure_chunk.chunk_id}

    async with async_session_maker() as session:
        await session.execute(delete(Chunk).where(Chunk.chunk_id.in_(created_chunk_ids)))
        await session.execute(delete(IngestedAsset).where(IngestedAsset.asset_id.in_(created_asset_ids)))
        await session.commit()


@pytest.mark.asyncio
async def test_vector_search_only_returns_rows_matching_the_current_provider_namespace(
    seeded_mock_and_azure_namespaced_chunks,
):
    ids = seeded_mock_and_azure_namespaced_chunks
    # LLM_PROVIDER=mock is this suite's real default (conftest.py) — the
    # currently active client's embedding_namespace is genuinely "mock".
    results = await vector_search("namespace regression marker query", top_k=10)

    returned_ids = {r.asset_row_id for r in results if r.asset_type == "chunk"}
    assert ids["mock_chunk_id"] in returned_ids, "the row namespaced for the ACTUAL active provider must be returned"
    assert ids["azure_chunk_id"] not in returned_ids, (
        "a row namespaced for a DIFFERENT provider must never be returned, even with an "
        "identical embedding vector — this is exactly the cross-provider bug this test guards against"
    )
