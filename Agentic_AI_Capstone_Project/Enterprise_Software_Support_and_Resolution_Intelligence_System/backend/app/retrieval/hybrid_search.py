"""
app/retrieval/hybrid_search.py

hybrid_search(query, filters) — the single tool call §9 and §27 specify for
the Documentation Retrieval Agent (Stage 5). The agent reasons over what
comes back; it never calls vector_search/keyword_search/fusion/rerank
individually, and Stage 5's code shouldn't either — this is the one
supported entry point into the whole retrieval layer.

Pipeline: vector_search + keyword_search (concurrent, top-20 each) →
Reciprocal Rank Fusion → LLM rerank (fused top-10 → top-5). See fusion.py
and rerank.py for why each stage works the way it does.
"""

from __future__ import annotations

from app.retrieval.fusion import fuse
from app.retrieval.rerank import rerank
from app.retrieval.vector_search import DEFAULT_TOP_K, SearchResult


async def hybrid_search(query: str, filters: dict | None = None) -> list[SearchResult]:
    fused = await fuse(query, filters=filters, top_k=DEFAULT_TOP_K)
    return await rerank(query, fused)
