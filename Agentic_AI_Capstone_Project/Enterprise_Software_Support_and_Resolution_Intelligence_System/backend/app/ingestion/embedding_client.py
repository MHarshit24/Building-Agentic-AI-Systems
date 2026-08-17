"""
app/ingestion/embedding_client.py

Thin ingestion-layer entry point for embeddings — no logic beyond
delegating to the configured LLM client, matching how parse_diagram()
(extract_diagrams.py) wraps call_llm_structured_vision(). Batched by
default via embed_batch(): one document can produce dozens of
chunks/tables/images/diagrams in a single ingestion run, and the
embeddings endpoint accepts multiple inputs per call, so pipeline.py
should reach for embed_batch() over repeated embed_text() calls whenever
it has more than one text ready at once.

Redis embedding cache (Stage 8's app/cache/redis_cache.py, closing a real
Stage 1 gap — see that module's own docstring): keyed by
(client.embedding_namespace, hashing.hash_text() of the exact input
text), independent of document_id or asset type. This is a DIFFERENT
optimization from app/ingestion/dedup_engine.py's own per-document
idempotency (§8.3) — dedup_engine skips re-embedding an asset unchanged
across re-ingestions of the SAME document; this cache skips re-embedding
identical text (e.g. shared boilerplate/headers) the first time it
appears in a DIFFERENT document, which dedup_engine's per-document scope
cannot catch. No TTL: a given exact (namespace, text) pair's embedding is
permanently valid unless that specific embedding deployment/model
changes — see redis_cache.py's own docstring for why this differs from
routes_metrics.py's TTL'd cache.

The namespace segment is a real, confirmed bug fix, not defensive
boilerplate: keying purely by text_hash meant that after a real
LLM_PROVIDER fallback (Azure -> Groq/Gemini,
app/llm/provider_resolution.py, resolved once at startup) any text
already cached from the Azure era silently returned Azure's stale,
non-comparable embedding-space vector on the next call instead of a
fresh Gemini one — confirmed by a real, live reproduction, not a
hypothetical (embed under Azure, flip llm_provider to "groq", re-embed
the identical text, get back a byte-identical vector). Both real
providers happen to produce EMBEDDING_DIMENSIONS-length vectors, so no
dimension check could ever have caught this silently wrong result.
get_llm_client() is called exactly once per function below (not once for
the namespace and again for the embed call) specifically so the
namespace and the embedding that gets cached under it always come from
the SAME resolved client, even if settings.llm_provider were somehow to
change between two lines of this function.

A cache miss and a Redis outage are indistinguishable here by design
(redis_cache.py's own contract) — both simply fall through to a real
embed call, never a hard failure.
"""

from app.cache.redis_cache import get_cached_embedding, set_cached_embedding
from app.ingestion.hashing import hash_text
from app.llm.azure_client import get_llm_client


async def embed_text(text: str) -> list[float]:
    client = get_llm_client()
    namespace = client.embedding_namespace
    text_hash = hash_text(text)
    cached = await get_cached_embedding(namespace, text_hash)
    if cached is not None:
        return cached

    embedding = await client.embed(text)
    await set_cached_embedding(namespace, text_hash, embedding)
    return embedding


async def embed_batch(texts: list[str]) -> list[list[float]]:
    """Partial-cache-hit batching: looks up every text's hash first, calls
    the real embed_batch() only for the texts that missed, then
    reassembles the full result in the caller's original order — so a
    batch that's mostly cache hits (e.g. re-ingesting a document that
    shares most of its boilerplate with others already ingested) doesn't
    pay for a full-size embedding call just because a few texts are new."""
    client = get_llm_client()
    namespace = client.embedding_namespace
    hashes = [hash_text(text) for text in texts]
    cached_results: list[list[float] | None] = [await get_cached_embedding(namespace, h) for h in hashes]

    miss_indices = [i for i, cached in enumerate(cached_results) if cached is None]
    if miss_indices:
        miss_texts = [texts[i] for i in miss_indices]
        miss_embeddings = await client.embed_batch(miss_texts)
        for i, embedding in zip(miss_indices, miss_embeddings):
            cached_results[i] = embedding
            await set_cached_embedding(namespace, hashes[i], embedding)

    return cached_results
