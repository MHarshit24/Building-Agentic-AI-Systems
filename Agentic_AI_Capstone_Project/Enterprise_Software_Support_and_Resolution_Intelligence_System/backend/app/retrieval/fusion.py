"""
app/retrieval/fusion.py

Reciprocal Rank Fusion (§9): RRF(d) = Σ 1/(k+rank_i(d)), k=60 exactly.
Fuses by RANK POSITION within each leg's result list, not by raw score —
cosine similarity (vector_search) and ts_rank_cd (keyword_search) live on
incompatible scales (§9's own stated reasoning: one is bounded [-1,1], the
other is an unbounded BM25-style weight), so summing or averaging the raw
scores directly would silently let whichever leg happens to produce larger
numbers dominate the fusion. Rank position sidesteps that entirely — 1st
place is 1st place regardless of which leg's score scale it came from.

The two legs are dispatched concurrently via asyncio.gather (§9's diagram
shows them running in parallel, not sequentially) — vector_search's own
Azure embedding call and keyword_search's Postgres round-trip have no
dependency on each other, so there's no reason to pay their latencies
serially.
"""

from __future__ import annotations

import asyncio
from dataclasses import replace

from app.retrieval.keyword_search import keyword_search
from app.retrieval.vector_search import DEFAULT_TOP_K, SearchResult, vector_search

RRF_K = 60


def reciprocal_rank_fusion(result_lists: list[list[SearchResult]], k: int = RRF_K) -> list[SearchResult]:
    """
    Pure fusion logic — no I/O, easily unit-tested on its own. A document
    is identified across lists by (asset_type, asset_row_id), since the
    same underlying DB row comes back as a separately-constructed
    SearchResult instance from each leg. A document appearing in only one
    list still gets scored from that one list's rank alone.
    """
    rrf_scores: dict[tuple[str, int], float] = {}
    first_seen: dict[tuple[str, int], SearchResult] = {}

    for results in result_lists:
        for rank, result in enumerate(results, start=1):
            key = (result.asset_type, result.asset_row_id)
            rrf_scores[key] = rrf_scores.get(key, 0.0) + 1.0 / (k + rank)
            first_seen.setdefault(key, result)

    fused = [replace(first_seen[key], score=score) for key, score in rrf_scores.items()]
    fused.sort(key=lambda r: r.score, reverse=True)
    return fused


async def fuse(query: str, filters: dict | None = None, top_k: int = DEFAULT_TOP_K) -> list[SearchResult]:
    """Dispatches vector_search and keyword_search concurrently, then
    fuses their results via Reciprocal Rank Fusion."""
    vector_results, keyword_results = await asyncio.gather(
        vector_search(query, filters=filters, top_k=top_k),
        keyword_search(query, filters=filters, top_k=top_k),
    )
    return reciprocal_rank_fusion([vector_results, keyword_results])
