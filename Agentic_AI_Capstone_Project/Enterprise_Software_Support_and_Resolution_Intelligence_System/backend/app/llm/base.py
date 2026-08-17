import abc
from typing import Any

# Every vector(1536) column in §21's schema (chunks, tables, images,
# diagram_graphs) assumes this dimension. Shared here rather than
# hardcoded separately in azure_client.py and mock_client.py, so the two
# can't silently drift apart on this number.
EMBEDDING_DIMENSIONS = 1536


class BaseLLMClient(abc.ABC):
    """Abstract base class for LLM clients."""

    @abc.abstractmethod
    async def generate(self, prompt: str, **kwargs: Any) -> Any:
        """Generate a response given a prompt."""
        pass

    @abc.abstractmethod
    async def generate_vision(self, image_bytes: bytes, prompt: str, **kwargs: Any) -> str:
        """Generate a text response (e.g. an image caption, §8.2) given raw
        image bytes plus a text prompt. Separate from generate() — not a
        replacement — since it's a distinct, multimodal call shape."""
        pass

    @abc.abstractmethod
    async def embed(self, text: str, **kwargs: Any) -> list[float]:
        """Embed a single string into a vector (EMBEDDING_DIMENSIONS long)."""
        pass

    @abc.abstractmethod
    async def embed_batch(self, texts: list[str], **kwargs: Any) -> list[list[float]]:
        """Embed multiple strings in one call, order preserved. One
        document can produce dozens of chunks/tables/images/diagrams in a
        single ingestion run, and Azure OpenAI's embeddings endpoint
        accepts multiple inputs per call — batching is real efficiency
        here (fewer round-trips for a whole document's worth of assets),
        not just a nice-to-have API convenience."""
        pass

    @property
    @abc.abstractmethod
    def embedding_namespace(self) -> str:
        """A short, stable string identifying which real embedding model
        this client's embed()/embed_batch() calls actually use (e.g.
        "azure:text-embedding-3-small", "gemini:gemini-embedding-001",
        "mock"). Real, confirmed bug this exists to fix: app/cache/
        redis_cache.py's embedding cache used to be keyed purely by
        content hash, with no provider/model dimension at all — so after
        a real LLM_PROVIDER fallback (Azure -> Groq/Gemini,
        app/llm/provider_resolution.py, resolved once at startup), any
        text already cached from the Azure era silently returned Azure's
        stale, non-comparable embedding-space vector instead of a fresh
        Gemini one, with zero error and zero log line — confirmed by a
        real, live reproduction (embed under Azure, flip the provider,
        re-embed the same text, get back a byte-identical vector). Both
        real providers happen to produce EMBEDDING_DIMENSIONS-length
        vectors, so no dimension check could ever have caught this.
        embedding_client.py's embed_text()/embed_batch() namespace every
        cache key with this value, so switching providers naturally
        starts a fresh cache namespace instead of silently reading
        another provider's incompatible vectors."""
        pass
