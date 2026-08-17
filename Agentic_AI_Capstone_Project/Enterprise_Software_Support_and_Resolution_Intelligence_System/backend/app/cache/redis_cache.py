"""
app/cache/redis_cache.py

Stage 1 deliverable (§25: "cache/redis_cache.py"), left as an empty stub
until now — confirmed against §13/architecture diagram, not assumed: this
is a GENERAL-PURPOSE caching utility, not a single-feature helper. The
blueprint names exactly two concrete uses (architecture diagram legend:
"Redis (embed+query cache, JWT blacklist)"; §21's index note: "Redis (not
Postgres): embedding cache, query-result cache, JWT blacklist"):
  1. Embedding cache, keyed by (embedding_namespace, content_hash) — NOT
     content hash alone (§8's ingestion pipeline line: "Redis embedding
     cache keyed by asset_hash — dedupes even across different documents
     sharing boilerplate"; the namespace segment is a real, later fix,
     see _embedding_key()'s own docstring below for the bug it closes).
     Real gap this closes: app/ingestion/dedup_engine.py already skips
     re-embedding an asset whose hash is unchanged WITHIN one document's
     re-ingestion (§8.3 idempotency), but that dedup is scoped per-document
     — it does nothing for identical text (e.g. shared legal boilerplate,
     standard headers) appearing for the first time in a DIFFERENT
     document. A hash-keyed embedding cache, independent of document_id,
     is what actually "dedupes across different documents" — a distinct
     optimization from ingestion's own idempotency, not a duplicate of it.
  2. Query-result cache for near-duplicate questions (§13 design list,
     item 7: "Redis query-result cache for near-duplicate questions" —
     also referenced from §13's own latency-mitigation discussion: "lean
     harder on the Redis query-result cache so repeat/near-duplicate
     questions skip the graph entirely"). This module provides the
     generic primitive; wiring it into a live retrieval path (which
     production query would be cached, cache-key normalization, TTL vs.
     re-ingestion staleness) is a separate design decision belonging to
     whichever node consumes it, not decided here — no call site wires
     this yet (see this stage's own investigation notes for why: it's a
     live-retrieval-path behavior change, not just building the module).

JWT blacklist (app/auth/jwt_handler.py) deliberately stays OUT of this
module's scope despite also using Redis: it's a revocation ledger
(existence check with natural TTL-based expiry), not a cache of a
recomputed value — different semantics, and jwt_handler.py's own
existing implementation is correct and self-contained as-is. Refactoring
it to route through this module would gain nothing (no shared logic to
deduplicate) while adding an indirection.

Every cache read/write is safely wrapped, per §21's own explicit
requirement: "Cache is an optimization, not a dependency — every cache
read/write is wrapped so a Redis outage silently falls back to the
uncached path (slower, not broken), same philosophy as tracing.py's own
safe_* wrappers." A cache miss and a Redis outage are therefore
indistinguishable to callers by design — both simply mean "compute it
fresh" — so every function here returns None (get) or does nothing (set)
on any failure, never raises.

Real, empirically-confirmed findings from this stage's own build, not
hypotheticals — two, layered:
  1. A fresh `redis.from_url(...)` connection in this dev environment
     took ~2.1s to establish (measured directly), while every subsequent
     command on that SAME client took ~0.3ms — a ~7000x difference. The
     first version of this module opened (and, via `async with client:`,
     immediately closed) a brand-new connection on every single call,
     which went unnoticed while the only caller was routes_metrics.py's
     own 30s-TTL snapshot cache (infrequent), but broke a real,
     timing-sensitive test (test_graph_parallel_fanout.py's concurrency-
     overlap check) the moment this module gained a second caller
     (embedding_client.py's embed_text(), called on every doc_retrieval_
     node invocation via §31 Layer B's scope check) — injecting ~2s of
     previously-nonexistent latency onto a request path that used to
     have zero Redis involvement.
  2. Naively fixing (1) with one module-level client reused for the
     process's lifetime broke in a DIFFERENT, worse way across tests:
     confirmed directly that reusing a redis.asyncio client across two
     different asyncio event loops doesn't just reconnect slowly, it
     raises `RuntimeError: Event loop is closed` outright — the exact
     same asyncpg-across-event-loops hazard this project already
     documents elsewhere (test_hybrid_search.py's `_use_real_dev_database`
     pattern), now hitting a Redis client instead of a DB engine. In
     production there's one long-lived event loop for the server
     process's life, so this never surfaces there — but pytest-asyncio
     gives each test its own fresh loop, so a naive process-lifetime
     singleton would silently fail (caught by this module's own safe
     wrapper, so no crash, but caching effectively disabled) on every
     test after the first.

Fixed by tracking which running loop the cached client was created
under and transparently recreating it if the current loop differs — a
real connection pool within a single event loop's lifetime (fixing (1)),
correct across independent event loops too (fixing (2)), rather than a
one-size-fits-all module singleton. jwt_handler.py's existing blacklist
checks have the same fresh-connection-per-call pattern (1) describes and
would benefit from an identical fix, but that module is out of this
task's scope (see above) and wasn't regressed by anything built here, so
it's left alone.
"""

from __future__ import annotations

import asyncio
import json
import logging

import redis.asyncio as redis

from app.config import get_settings
from app.logging.structured_logger import log_event

logger = logging.getLogger(__name__)

_EMBEDDING_KEY_PREFIX = "cache:embedding:"

_client: redis.Redis | None = None
_client_redis_url: str | None = None
_client_loop: asyncio.AbstractEventLoop | None = None


def _get_client(redis_url: str) -> redis.Redis:
    """Lazily creates a client, reused across calls WITHIN one event
    loop's lifetime (a real connection pool, the way redis-py is meant
    to be used — see module docstring for the measured ~2s cost of not
    doing this), but transparently recreated if the currently-running
    loop differs from the one the cached client was created under (the
    module docstring's second finding: reusing a client across event
    loops doesn't just reconnect slowly, it raises `RuntimeError: Event
    loop is closed` outright). The stale client is deliberately not
    closed here — it belongs to a loop that's already gone (or is about
    to be), so closing it would itself need that dead loop; letting it
    be garbage-collected is correct, not a leak."""
    global _client, _client_redis_url, _client_loop
    current_loop = asyncio.get_running_loop()
    if _client is None or _client_redis_url != redis_url or _client_loop is not current_loop:
        _client = redis.from_url(redis_url, decode_responses=True)
        _client_redis_url = redis_url
        _client_loop = current_loop
    return _client


async def cache_get(key: str) -> str | None:
    """Generic safe read. Returns None on a cache miss OR a Redis outage —
    callers should not, and generally cannot, tell the difference."""
    settings = get_settings()
    if not settings.redis_url:
        return None
    try:
        client = _get_client(settings.redis_url)
        return await client.get(key)
    except Exception as exc:
        log_event(logger, "WARNING", "cache_read_failed", key=key, error=str(exc))
        return None


async def cache_set(key: str, value: str, *, ttl_seconds: int | None = None) -> None:
    """Generic safe write. `ttl_seconds=None` means no expiry (appropriate
    for content-addressed values like embeddings, where the same key can
    never legitimately map to a different value — see get_cached_embedding
    below); a real TTL is appropriate for values that go stale over time
    (e.g. routes_metrics.py's snapshot cache)."""
    settings = get_settings()
    if not settings.redis_url:
        return
    try:
        client = _get_client(settings.redis_url)
        if ttl_seconds is not None:
            await client.setex(key, ttl_seconds, value)
        else:
            await client.set(key, value)
    except Exception as exc:
        log_event(logger, "WARNING", "cache_write_failed", key=key, error=str(exc))


def _embedding_key(namespace: str, text_hash: str) -> str:
    """`namespace` identifies which real embedding model produced (or
    would produce) this vector — e.g. "azure:text-embedding-3-small",
    "gemini:gemini-embedding-001", "mock" (BaseLLMClient.embedding_namespace,
    app/llm/base.py). Real, confirmed bug this fixes: this key used to be
    built from text_hash ALONE, with no provider/model dimension at all,
    so after a real LLM_PROVIDER fallback (Azure -> Groq/Gemini,
    app/llm/provider_resolution.py, resolved once at process startup) any
    text already cached from the Azure era silently returned Azure's
    stale, non-comparable embedding-space vector instead of a fresh
    Gemini one — confirmed by a real, live reproduction (embed under
    Azure, flip the provider, re-embed the same text, get back a
    byte-identical vector, cosine similarity 1.0). Both real providers
    happen to produce EMBEDDING_DIMENSIONS-length vectors, so no
    dimension check could ever have caught this; namespacing the key
    itself is the fix. Old, pre-fix keys (bare `cache:embedding:{hash}`,
    no namespace segment) are simply never read again under this scheme
    — harmless, orphaned entries that age out naturally if a TTL is ever
    added, not a migration this fix needs to perform."""
    return f"{_EMBEDDING_KEY_PREFIX}{namespace}:{text_hash}"


async def get_cached_embedding(namespace: str, text_hash: str) -> list[float] | None:
    """text_hash: app/ingestion/hashing.py's hash_text()/hash_bytes() —
    same hashing utility ingestion already uses for asset_hash, reused
    here rather than a second hashing scheme. No TTL: an embedding for a
    given exact (namespace, text) pair is permanently valid for as long
    as that embedding deployment/model is unchanged — unlike query-result
    caching, there's no staleness clock to run out, and switching
    providers now starts a fresh namespace rather than reading stale
    data (see _embedding_key's own docstring)."""
    raw = await cache_get(_embedding_key(namespace, text_hash))
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        log_event(logger, "WARNING", "cache_embedding_corrupt", namespace=namespace, text_hash=text_hash)
        return None


async def set_cached_embedding(namespace: str, text_hash: str, embedding: list[float]) -> None:
    await cache_set(_embedding_key(namespace, text_hash), json.dumps(embedding))
