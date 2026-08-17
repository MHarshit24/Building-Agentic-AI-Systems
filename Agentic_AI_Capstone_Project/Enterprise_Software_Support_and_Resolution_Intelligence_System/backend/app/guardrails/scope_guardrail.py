"""
app/guardrails/scope_guardrail.py

§31's SECOND, independent scope-guardrail layer (Layer B) — a non-LLM
"topic centroid" sanity check. Layer A (classify_node's own out_of_scope
enum output, routed by router.py to a fixed refusal) is a completely
separate mechanism; this module doesn't know about or depend on it, and
is meant to catch exactly the case where Layer A's classifier judgment
alone might be wrong (§14's "don't trust one signal alone" principle,
applied here to scope instead of hallucination).

The centroid is the mean embedding of every currently-active chunk/table
in the ingested corpus. It's a whole-corpus aggregate, meant to be
computed once (e.g. at startup, or refreshed on a schedule) and reused —
never recomputed per request, which would be pure waste for a value that
only changes when the corpus itself changes.

Real, confirmed bug fixed here, same root cause as app/retrieval/
vector_search.py's own analogous fix: compute_corpus_centroid() used to
average EVERY embedded chunk/table row regardless of which provider
embedded it, then is_in_scope() compared that centroid against a live
query embedding from whichever provider is CURRENTLY active — after a
real LLM_PROVIDER fallback (Azure -> Groq/Gemini), this cosine-similarity
comparison would be between two non-comparable embedding spaces, with
zero error, silently making Layer B's out-of-scope judgment meaningless
for the rest of that process's life. Fixed by only averaging rows whose
embedding_namespace matches the current client's — see Chunk.
embedding_namespace's own model comment for the full bug history.
"""

from __future__ import annotations

import math

from sqlalchemy import select

from app.db.models import Chunk, TableAsset
from app.db.session import async_session_maker
from app.llm.azure_client import get_llm_client

# Deliberately loose for now, not asserted as a proven constant — same
# framing as §6's confidence threshold: a reasonable starting point,
# to be recalibrated once real golden-eval data exists to check it
# against (Stage 8), not a number derived from real measurement yet.
SCOPE_SIMILARITY_THRESHOLD = 0.15


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


async def compute_corpus_centroid() -> list[float]:
    """Mean embedding across every embedded chunk + table row in the
    corpus THAT MATCHES THE CURRENTLY ACTIVE PROVIDER's embedding
    namespace (see this module's own docstring for the real, confirmed
    bug this guards against). `list(embedding)` normalizes pgvector's
    returned value (which may come back as a numpy array or a plain list
    depending on what's installed) to a plain list before summing, so the
    arithmetic below never has to care which one it got.
    """
    embedding_namespace = get_llm_client().embedding_namespace
    async with async_session_maker() as db:
        chunk_embeddings = (
            await db.execute(
                select(Chunk.embedding).where(
                    Chunk.embedding.isnot(None), Chunk.embedding_namespace == embedding_namespace
                )
            )
        ).scalars().all()
        table_embeddings = (
            await db.execute(
                select(TableAsset.embedding).where(
                    TableAsset.embedding.isnot(None), TableAsset.embedding_namespace == embedding_namespace
                )
            )
        ).scalars().all()

    all_embeddings = [list(e) for e in (*chunk_embeddings, *table_embeddings)]
    if not all_embeddings:
        raise ValueError(
            "Cannot compute a corpus centroid: no embedded chunks/tables found for the current "
            f"embedding_namespace ({embedding_namespace!r}) — either ingestion hasn't run yet, or "
            "the corpus was embedded entirely under a different LLM provider (e.g. after a real "
            "LLM_PROVIDER fallback) than the one currently active."
        )

    dimensions = len(all_embeddings[0])
    sums = [0.0] * dimensions
    for embedding in all_embeddings:
        for i, value in enumerate(embedding):
            sums[i] += value
    return [total / len(all_embeddings) for total in sums]


def is_in_scope(
    query_embedding: list[float], centroid: list[float], threshold: float = SCOPE_SIMILARITY_THRESHOLD
) -> bool:
    """Layer B's actual check — plain cosine similarity between a query's
    embedding and the corpus topic centroid, no LLM call involved."""
    return _cosine_similarity(query_embedding, centroid) >= threshold


_cached_centroid: list[float] | None = None


async def get_cached_centroid() -> list[float]:
    """Lazy, process-wide cache — computed once per process on first use,
    not per request (Stage 8's calibration work may replace this with a
    scheduled refresh; a plain module-level cache is enough for now,
    consistent with not building infrastructure ahead of an actual need)."""
    global _cached_centroid
    if _cached_centroid is None:
        _cached_centroid = await compute_corpus_centroid()
    return _cached_centroid
