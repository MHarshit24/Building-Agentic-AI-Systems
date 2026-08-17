import base64
from typing import Any
import httpx
from langfuse.openai import AsyncAzureOpenAI  # drop-in wrapper — auto-emits a
# Langfuse "generation" observation (with real token usage/cost) for every
# chat.completions/embeddings call, nested under whatever span is
# OTel-active at call time (app/observability/tracing.py's traced() sets
# that up per node — §15's "Cost/latency: auto-captured per span").

from app.config import get_settings
from app.llm.base import EMBEDDING_DIMENSIONS, BaseLLMClient
from app.llm.mock_client import MockLLMClient


class EmbeddingDimensionError(Exception):
    """Raised when Azure's embeddings endpoint returns a vector whose
    length doesn't match EMBEDDING_DIMENSIONS. Failed loudly here on
    purpose — a silent mismatch wouldn't error until a much more
    confusing failure downstream (a pgvector insert/index rejecting the
    row, or worse, silently truncating/padding it), far from the actual
    cause. Almost certainly means azure_openai_embedding_deployment is
    pointed at the wrong model."""


def _detect_image_mime_type(image_bytes: bytes) -> str:
    """
    generate_vision()'s signature (fixed by design, see extract_images.py)
    takes raw bytes with no accompanying mime-type/extension argument, so
    the format has to be sniffed from the bytes themselves for the
    data-URI the vision API call needs. Magic-byte check, not a new
    dependency (Python 3.13+ dropped stdlib `imghdr`, and there's no
    reason to add Pillow just for a 4-way format sniff). Defaults to PNG
    for anything unrecognized — a soft fallback, not a guarantee.
    """
    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if image_bytes.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if image_bytes.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if image_bytes.startswith(b"RIFF") and image_bytes[8:12] == b"WEBP":
        return "image/webp"
    return "image/png"


class AzureLLMClient(BaseLLMClient):
    """Real Azure OpenAI client implementation."""

    def __init__(self) -> None:
        settings = get_settings()
        self.client = AsyncAzureOpenAI(
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
            azure_endpoint=settings.azure_openai_endpoint,
            http_client=httpx.AsyncClient(timeout=30.0),
        )
        self.deployment = settings.azure_openai_llm_deployment
        # Deliberately separate from self.deployment — a chat-completions
        # deployment name and an embeddings deployment name are different
        # config fields (and typically different underlying models).
        self.embedding_deployment = settings.azure_openai_embedding_deployment

    async def generate(self, prompt: str, **kwargs: Any) -> Any:
        response = await self.client.chat.completions.create(
            model=self.deployment,
            messages=[{"role": "user", "content": prompt}],
            **kwargs
        )
        return response

    async def generate_vision(self, image_bytes: bytes, prompt: str, **kwargs: Any) -> str:
        """Real vision call — image + text in one multimodal message, per
        the same gpt-5-mini deployment generate() already uses (§8.2's
        image-captioning row). Returns just the text of the response,
        unlike generate() which returns the raw completion object — callers
        of an image caption want the caption string directly."""
        mime_type = _detect_image_mime_type(image_bytes)
        encoded = base64.b64encode(image_bytes).decode("ascii")
        response = await self.client.chat.completions.create(
            model=self.deployment,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime_type};base64,{encoded}"},
                        },
                    ],
                }
            ],
            **kwargs,
        )
        return response.choices[0].message.content

    async def embed(self, text: str, **kwargs: Any) -> list[float]:
        response = await self.client.embeddings.create(
            model=self.embedding_deployment,
            input=text,
            **kwargs,
        )
        vector = response.data[0].embedding
        _check_dimension(vector)
        return vector

    async def embed_batch(self, texts: list[str], **kwargs: Any) -> list[list[float]]:
        if not texts:
            return []
        response = await self.client.embeddings.create(
            model=self.embedding_deployment,
            input=texts,
            **kwargs,
        )
        # The API is documented to preserve input order, but each item
        # also carries its own `index` — sorting by it explicitly costs
        # nothing and removes any doubt that vectors[i] really does
        # correspond to texts[i].
        ordered = sorted(response.data, key=lambda item: item.index)
        vectors = [item.embedding for item in ordered]
        for vector in vectors:
            _check_dimension(vector)
        return vectors

    @property
    def embedding_namespace(self) -> str:
        return f"azure:{self.embedding_deployment}"


def _check_dimension(vector: list[float]) -> None:
    if len(vector) != EMBEDDING_DIMENSIONS:
        raise EmbeddingDimensionError(
            f"Azure embeddings endpoint returned a {len(vector)}-dimensional "
            f"vector, expected {EMBEDDING_DIMENSIONS} (every vector(1536) "
            "column in §21's schema assumes this) — check "
            "azure_openai_embedding_deployment's configured model."
        )


def get_llm_client() -> BaseLLMClient:
    """Factory function to get the configured LLM client. settings.llm_provider
    is set to "groq" by app.llm.provider_resolution.resolve_llm_provider() at
    startup (app/main.py's lifespan) when Azure isn't reachable but the
    Groq+Gemini fallback tier is — never picked directly from a static
    default the way "azure"/"mock" are."""
    settings = get_settings()
    if settings.llm_provider == "mock":
        return MockLLMClient()
    if settings.llm_provider == "groq":
        from app.llm.groq_gemini_client import GroqGeminiClient

        return GroqGeminiClient()
    return AzureLLMClient()
