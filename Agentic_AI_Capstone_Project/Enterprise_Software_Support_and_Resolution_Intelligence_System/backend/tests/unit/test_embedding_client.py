"""
tests/unit/test_embedding_client.py

L1/L2 tests (§19) for app/ingestion/embedding_client.py's Redis
embedding-cache integration — no real Redis, no real LLM call.

Regression coverage for a real, confirmed bug: the embedding cache used
to be keyed by content hash ALONE, with no provider/model dimension, so
after a real LLM_PROVIDER fallback (Azure -> Groq/Gemini) any text
already cached from the Azure era silently returned Azure's stale,
non-comparable embedding-space vector instead of a fresh Gemini one —
confirmed via a real, live reproduction (embed under Azure, flip the
provider, re-embed the same text, get back a byte-identical vector).
Fixed by namespacing every cache key with
BaseLLMClient.embedding_namespace (app/llm/base.py). These tests assert
the fix's actual behavior: two different namespaces never share a cache
entry for the same text, even though embedding_client.py never touches
Redis directly here (get_cached_embedding/set_cached_embedding are
monkeypatched onto an in-memory fake, same style as
test_scope_guardrail.py's monkeypatched compute_corpus_centroid()).
"""

from __future__ import annotations

import pytest

import app.ingestion.embedding_client as embedding_client_module
from app.ingestion.embedding_client import embed_batch, embed_text


class _FakeStore:
    """Stands in for Redis: a plain dict keyed by (namespace, text_hash),
    exactly mirroring redis_cache.py's own real key shape post-fix."""

    def __init__(self) -> None:
        self.data: dict[tuple[str, str], list[float]] = {}

    async def get(self, namespace: str, text_hash: str) -> list[float] | None:
        return self.data.get((namespace, text_hash))

    async def set(self, namespace: str, text_hash: str, embedding: list[float]) -> None:
        self.data[(namespace, text_hash)] = embedding


class _FakeClient:
    """Deterministic per-instance fake — same text always yields the same
    vector for a GIVEN client instance, but different instances (standing
    in for different real providers) yield different vectors for the SAME
    text, so a namespace mix-up is directly observable in the test."""

    def __init__(self, namespace: str, tag: float) -> None:
        self.embedding_namespace = namespace
        self._tag = tag
        self.embed_call_count = 0
        self.embed_batch_call_count = 0

    async def embed(self, text: str) -> list[float]:
        self.embed_call_count += 1
        return [self._tag, float(len(text))]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        self.embed_batch_call_count += 1
        return [[self._tag, float(len(t))] for t in texts]


@pytest.fixture
def fake_store(monkeypatch):
    store = _FakeStore()

    async def _get(namespace: str, text_hash: str):
        return await store.get(namespace, text_hash)

    async def _set(namespace: str, text_hash: str, embedding: list[float]) -> None:
        await store.set(namespace, text_hash, embedding)

    monkeypatch.setattr(embedding_client_module, "get_cached_embedding", _get)
    monkeypatch.setattr(embedding_client_module, "set_cached_embedding", _set)
    return store


class TestEmbedTextCaching:
    @pytest.mark.asyncio
    async def test_second_call_same_client_is_a_real_cache_hit(self, fake_store, monkeypatch):
        client = _FakeClient(namespace="azure:text-embedding-3-small", tag=1.0)
        monkeypatch.setattr(embedding_client_module, "get_llm_client", lambda: client)

        first = await embed_text("hello world")
        second = await embed_text("hello world")

        assert first == second
        assert client.embed_call_count == 1, "second call should hit the cache, not call embed() again"

    @pytest.mark.asyncio
    async def test_different_text_is_a_real_cache_miss(self, fake_store, monkeypatch):
        client = _FakeClient(namespace="azure:text-embedding-3-small", tag=1.0)
        monkeypatch.setattr(embedding_client_module, "get_llm_client", lambda: client)

        await embed_text("hello world")
        await embed_text("goodbye world")

        assert client.embed_call_count == 2


class TestCrossProviderNamespaceIsolation:
    """The actual regression test for the confirmed bug."""

    @pytest.mark.asyncio
    async def test_switching_provider_never_returns_the_other_providers_stale_vector(self, fake_store, monkeypatch):
        text = "How do I reset my password?"

        azure_client = _FakeClient(namespace="azure:text-embedding-3-small", tag=1.0)
        monkeypatch.setattr(embedding_client_module, "get_llm_client", lambda: azure_client)
        azure_vector = await embed_text(text)

        # Simulate a real provider fallback: llm_provider flips, a
        # differently-namespaced client is now what get_llm_client() returns.
        gemini_client = _FakeClient(namespace="gemini:gemini-embedding-001", tag=2.0)
        monkeypatch.setattr(embedding_client_module, "get_llm_client", lambda: gemini_client)
        gemini_vector = await embed_text(text)

        # Pre-fix behavior would have made this assertion fail: the second
        # call would have returned azure_vector unchanged (a stale cache
        # hit under the OTHER provider's identity), never calling embed()
        # on gemini_client at all.
        assert gemini_client.embed_call_count == 1, "must compute a fresh embedding under the new provider's namespace"
        assert azure_vector != gemini_vector, "different providers' vectors for the same text must not be conflated"

        # Both real entries genuinely exist side by side, correctly namespaced.
        assert len(fake_store.data) == 2
        assert {key[0] for key in fake_store.data} == {"azure:text-embedding-3-small", "gemini:gemini-embedding-001"}

        # Flipping back to Azure for the SAME text should hit Azure's own
        # cache entry again (not recompute, and not read Gemini's).
        monkeypatch.setattr(embedding_client_module, "get_llm_client", lambda: azure_client)
        azure_vector_again = await embed_text(text)
        assert azure_vector_again == azure_vector
        assert azure_client.embed_call_count == 1, "flipping back to Azure should be a real cache hit, not a recompute"

    @pytest.mark.asyncio
    async def test_embed_batch_also_isolates_by_namespace(self, fake_store, monkeypatch):
        texts = ["first chunk", "second chunk"]

        azure_client = _FakeClient(namespace="azure:text-embedding-3-small", tag=1.0)
        monkeypatch.setattr(embedding_client_module, "get_llm_client", lambda: azure_client)
        azure_vectors = await embed_batch(texts)

        gemini_client = _FakeClient(namespace="gemini:gemini-embedding-001", tag=2.0)
        monkeypatch.setattr(embedding_client_module, "get_llm_client", lambda: gemini_client)
        gemini_vectors = await embed_batch(texts)

        assert gemini_client.embed_batch_call_count == 1, "must not silently reuse Azure's cached batch results"
        assert azure_vectors != gemini_vectors
        assert len(fake_store.data) == 4  # 2 texts x 2 namespaces, each a distinct key
