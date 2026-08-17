"""
app/retrieval/keyword_search.py

Keyword leg of hybrid retrieval (§9): Postgres full-text search via
`ts_rank_cd` (BM25-style ranking) against the `tsv` generated column now
present on all four asset tables (chunks, tables, images, diagram_graphs —
Task 0's migration). Covers exact tokens the vector leg's embeddings tend to
under-rank: error codes ("429"), config names ("DB_PASSWORD"), endpoint
paths ("/v3/tickets") — §9's own stated examples.

Same shared SearchResult shape as vector_search.py (imported from there,
which owns the shared asset-table registry and result dataclass), and the
same §27 pre-filter-not-post-hoc-filter treatment for category/
product_version: the `tsv @@ tsquery` match condition AND the metadata
filters are combined in one WHERE clause before ranking/limiting, not
applied after the top-K comes back.

category filtering support stays here unchanged, but as of this project's
own full-golden-set investigation is no longer populated by default from
classify_node's category — see vector_search.py's module docstring / doc_
retrieval.py's `_run_one_attempt()` for the real evidence.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import IngestedAsset
from app.db.session import async_session_maker
from app.retrieval.vector_search import ASSET_TABLES, DEFAULT_TOP_K, SearchResult, id_column_for


async def _search_one_table(
    db: AsyncSession, asset_type: str, model: type, text_attr: str, query: str,
    filters: dict | None, top_k: int,
) -> list[SearchResult]:
    text_col = getattr(model, text_attr)
    id_col = id_column_for(model)
    tsquery = func.plainto_tsquery("english", query)
    rank = func.ts_rank_cd(model.tsv, tsquery)

    # section_header/product_version only exist on Chunk/TableAsset (§21) —
    # same conditional-column approach as vector_search.py, for the same reason.
    columns = [
        id_col.label("id"), text_col.label("text"), model.source_document.label("source_document"),
        model.page_number.label("page_number"), model.category.label("category"), rank.label("rank"),
    ]
    if hasattr(model, "section_header"):
        columns.append(model.section_header.label("section_header"))
    if hasattr(model, "product_version"):
        columns.append(model.product_version.label("product_version"))

    # Same is_active join as vector_search.py's _search_one_table — see
    # that file's comment for the full reasoning. Applies identically to
    # all four asset types via this shared function.
    stmt = (
        select(*columns)
        .join(IngestedAsset, model.asset_id == IngestedAsset.asset_id)
        .where(model.tsv.op("@@")(tsquery), IngestedAsset.is_active.is_(True))
    )

    if filters:
        category = filters.get("category")
        if category:
            stmt = stmt.where(model.category == category)
        product_version = filters.get("product_version")
        if product_version and hasattr(model, "product_version"):
            stmt = stmt.where(model.product_version == product_version)

    stmt = stmt.order_by(rank.desc()).limit(top_k)
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
            score=float(row["rank"]),  # ts_rank_cd's own scale — not comparable to cosine similarity, see fusion.py
        )
        for row in rows
    ]


async def keyword_search(query: str, filters: dict | None = None, top_k: int = DEFAULT_TOP_K) -> list[SearchResult]:
    """
    Full-text searches all four asset tables via ts_rank_cd, merges, and
    returns the overall top_k by rank. Same per-table-then-merge shape as
    vector_search() so neither leg starves the other in the merge.

    Rows with no tsv match at all are excluded by the `tsv @@ tsquery`
    WHERE condition (rather than merely ranking to the bottom), matching
    §27's pre-filter principle — no point spending a query's top_k slots
    on a zero-relevance keyword match.
    """
    async with async_session_maker() as db:
        per_table_results = []
        for asset_type, model, text_attr in ASSET_TABLES:
            per_table_results.append(
                await _search_one_table(db, asset_type, model, text_attr, query, filters, top_k)
            )

    merged = [r for table_results in per_table_results for r in table_results]
    merged.sort(key=lambda r: r.score, reverse=True)
    return merged[:top_k]
