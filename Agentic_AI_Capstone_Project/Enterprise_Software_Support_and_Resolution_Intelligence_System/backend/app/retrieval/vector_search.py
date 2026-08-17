"""
app/retrieval/vector_search.py

Vector leg of hybrid retrieval (§9): pgvector cosine similarity across all
four asset tables (chunks, tables, images, diagram_graphs) — HNSW indexes
already exist on each table's `embedding` column (app/db/models.py). Tables
and diagrams are searchable identically to chunks, per §9's explicit
requirement — none of the four asset types gets special-cased out of the
vector leg.

Metadata filtering (§27): `filters` is applied as a pre-filter WHERE clause
combined with the ANN search itself — a plain `.where(...)` before
`.order_by(distance)` — not a post-hoc filter after the top-K comes back.
Postgres/pgvector still uses the HNSW index for the ANN ordering; the filter
just narrows which rows are eligible to appear in that ordering at all, so
the top-K budget is never spent on rows that get discarded afterward.

`category` filtering support stays here (still a real, working filter for
any caller that passes one) but is no longer POPULATED BY DEFAULT from
classify_node's category — see app/orchestration/nodes/doc_retrieval.py's
own `_run_one_attempt()` comment for the real, evidence-based reasoning
(a query's own topic and its correct answer document's topic are
independent axes that only sometimes align; hard-excluding on a mismatch
threw away the right answer 42% of the time it mattered, in a full-golden-
set measurement). `product_version` only exists on Chunk and TableAsset
(Image and DiagramGraphRow carry no version metadata at all, §21) —
silently skipped for those two rather than raising, since "this asset
type has no version info" is a real, valid state, not a filter failure.

embedding_namespace filtering — a real, confirmed bug fix, not defensive
boilerplate: every WHERE clause below also requires
model.embedding_namespace == the CURRENT active client's
BaseLLMClient.embedding_namespace (app/llm/base.py). Without this, a live
query embedded under a DIFFERENT provider than whatever embedded the
stored corpus (e.g. after a real LLM_PROVIDER fallback, Azure ->
Groq/Gemini, resolved once at process startup) would be compared via
pgvector cosine distance against a non-comparable embedding space, with
zero error — confirmed by a real, live reproduction against this exact
codebase (see app/cache/redis_cache.py's own analogous fix for the
embedding-cache side of the same root cause). A provider mismatch now
degrades to an empty vector leg for the affected asset table(s) rather
than silently returning meaningless "matches" — hybrid_search's keyword
leg is provider-independent and keeps contributing regardless.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Chunk, DiagramGraphRow, Image, IngestedAsset, TableAsset
from app.db.session import async_session_maker
from app.ingestion.embedding_client import embed_text
from app.llm.azure_client import get_llm_client
from app.logging.structured_logger import log_event

logger = logging.getLogger(__name__)

DEFAULT_TOP_K = 20

# One entry per searchable asset table — (model, text_column, id_column,
# has_section_header). Table/chunk both have real section_header text;
# images/diagrams don't (§21's schema), so callers that want a citation
# label fall back to source_document + page_number for those two.
ASSET_TABLES: list[tuple[str, type, str]] = [
    ("chunk", Chunk, "text"),
    ("table", TableAsset, "text_serialization"),
    ("image", Image, "caption"),
    ("diagram", DiagramGraphRow, "caption"),
]


@dataclass
class SearchResult:
    """Shared result shape both retrieval legs (vector_search,
    keyword_search) produce, so fusion.py/rerank.py can consume either
    identically without caring which leg a hit came from."""

    asset_type: str  # "chunk" | "table" | "image" | "diagram"
    asset_row_id: int  # chunk_id / table_id / image_id / diagram_id
    text: str  # the retrievable text — Chunk.text / TableAsset.text_serialization / Image|DiagramGraphRow.caption
    source_document: str | None
    section_header: str | None
    page_number: int | None
    product_version: str | None
    category: str | None
    score: float  # leg-specific: cosine similarity (vector) or ts_rank_cd (keyword) — NOT comparable across legs, see fusion.py


def id_column_for(model: type):
    return {
        Chunk: Chunk.chunk_id,
        TableAsset: TableAsset.table_id,
        Image: Image.image_id,
        DiagramGraphRow: DiagramGraphRow.diagram_id,
    }[model]


async def _search_one_table(
    db: AsyncSession, asset_type: str, model: type, text_attr: str, query_embedding: list[float],
    filters: dict | None, top_k: int, embedding_namespace: str,
) -> list[SearchResult]:
    text_col = getattr(model, text_attr)
    id_col = id_column_for(model)
    distance = model.embedding.cosine_distance(query_embedding)

    # section_header/product_version only exist on Chunk/TableAsset (§21) —
    # selected conditionally so Image/DiagramGraphRow queries don't
    # reference a column they don't have; missing ones just come back None.
    columns = [
        id_col.label("id"), text_col.label("text"), model.source_document.label("source_document"),
        model.page_number.label("page_number"), model.category.label("category"), distance.label("distance"),
    ]
    if hasattr(model, "section_header"):
        columns.append(model.section_header.label("section_header"))
    if hasattr(model, "product_version"):
        columns.append(model.product_version.label("product_version"))

    # Joins to IngestedAsset.is_active on every asset type via this shared
    # function (ASSET_TABLES covers chunk/table/image/diagram identically,
    # see module docstring) — closes a real, confirmed gap: is_active was
    # previously a bookkeeping-only flag on IngestedAsset, never consulted
    # by retrieval, so a soft-retired document still surfaced in every
    # search result (production-readiness gap analysis, deletion item 1).
    #
    # model.embedding_namespace == embedding_namespace — closes the real,
    # confirmed cross-provider bug described in this module's own
    # docstring: without this, rows embedded under a DIFFERENT provider
    # than the one currently active would still be compared via cosine
    # distance against the live query's embedding, a non-comparable space.
    stmt = (
        select(*columns)
        .join(IngestedAsset, model.asset_id == IngestedAsset.asset_id)
        .where(
            model.embedding.isnot(None),
            IngestedAsset.is_active.is_(True),
            model.embedding_namespace == embedding_namespace,
        )
    )

    if filters:
        category = filters.get("category")
        if category:
            stmt = stmt.where(model.category == category)
        product_version = filters.get("product_version")
        if product_version and hasattr(model, "product_version"):
            stmt = stmt.where(model.product_version == product_version)

    stmt = stmt.order_by(distance).limit(top_k)
    rows = (await db.execute(stmt)).mappings().all()

    return [
        SearchResult(
            asset_type=asset_type,
            asset_row_id=row["id"],
            text=row["text"],
            source_document=row["source_document"],
            section_header=row.get("section_header"),
            page_number=row["page_number"],
            product_version=row.get("product_version"),
            category=row["category"],
            score=1.0 - float(row["distance"]),  # pgvector's <=> is cosine DISTANCE; similarity = 1 - distance
        )
        for row in rows
    ]


async def vector_search(query: str, filters: dict | None = None, top_k: int = DEFAULT_TOP_K) -> list[SearchResult]:
    """
    Embeds `query`, searches all four asset tables via pgvector cosine
    similarity, merges, and returns the overall top_k by similarity score.
    Each table is queried for its own top_k first (so no table gets
    starved by another table dominating the merge), then the combined
    pool is re-sorted and truncated to the requested top_k.

    Only compares against rows sharing the CURRENTLY active client's
    embedding_namespace — see this module's own docstring and
    _search_one_table()'s comment for the real cross-provider bug this
    guards against.
    """
    embedding_namespace = get_llm_client().embedding_namespace
    query_embedding = await embed_text(query)

    async with async_session_maker() as db:
        per_table_results = []
        for asset_type, model, text_attr in ASSET_TABLES:
            per_table_results.append(
                await _search_one_table(
                    db, asset_type, model, text_attr, query_embedding, filters, top_k, embedding_namespace
                )
            )

    merged = [r for table_results in per_table_results for r in table_results]
    merged.sort(key=lambda r: r.score, reverse=True)

    if not merged:
        # A real, meaningful signal worth a log line, per this whole
        # project's own established "no confirmation logging" gap fix
        # (§32 code-comment history) — an empty vector leg with a
        # non-empty keyword leg is exactly what a provider mismatch looks
        # like, and this project's own real corpus is never actually
        # empty, so this line firing is worth noticing during debugging.
        log_event(
            logger, "WARNING", "vector_search_empty_result",
            embedding_namespace=embedding_namespace,
            note="No rows matched the current embedding_namespace — possible LLM provider fallback with a corpus embedded under a different provider, or a genuinely empty/filtered-out corpus.",
        )

    return merged[:top_k]
