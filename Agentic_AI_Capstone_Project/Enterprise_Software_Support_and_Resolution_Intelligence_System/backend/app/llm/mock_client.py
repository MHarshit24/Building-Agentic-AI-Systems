import hashlib
import random
from typing import Any

from app.llm.base import EMBEDDING_DIMENSIONS, BaseLLMClient


def _deterministic_vector(text: str) -> list[float]:
    """Same input text always produces the same output vector — seeded
    from a hash of the text, not the real embedding model — so tests
    that assert "these two embeddings are equal/different" behave
    meaningfully under LLM_PROVIDER=mock instead of just getting random
    noise on every call. Different texts hashing to different seeds is
    what makes "different" assertions meaningful too."""
    seed = int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16) % (2**32)
    rng = random.Random(seed)
    return [rng.uniform(-1.0, 1.0) for _ in range(EMBEDDING_DIMENSIONS)]


class MockLLMClient(BaseLLMClient):
    """Mock LLM client that returns canned, deterministic responses."""

    async def generate(self, prompt: str, **kwargs: Any) -> Any:
        # Routed on schema-specific field-name markers, not generic topic
        # words — "incident"/"security" are literal category enum values
        # baked into classify_v1.py's own static OUTPUT_SCHEMA/FEW_SHOT
        # text (§39.3's ClassificationOutput), so they appear in every
        # single classify_node prompt regardless of the actual query.
        # Matching on those generic words previously meant classify_node
        # always hit the severity-checking branch below instead of its own
        # default, and doc_retrieval_node (no matching branch at all)
        # always fell through to the wrong shape too. Marker strings here
        # are each a field name unique to exactly one real §39.3 schema, so
        # each real Stage 5+ prompt hits its own matching canned shape.
        lowered = prompt.lower()
        if "cited_source_ids" in lowered:
            # DocRetrievalOutput (doc_retrieval_v1.py) — grounded refusal by
            # default (no real evidence to safely cite in a generic canned
            # response); tests that need a specific evidence_sufficient/
            # cited_source_ids combination already use their own fake
            # client, same reasoning as test_graph_e2e.py's own docstring.
            return (
                '{"draft_answer": "I don\'t have enough information to answer that.", '
                '"cited_source_ids": [], "evidence_sufficient": false, "rewritten_query": null}'
            )
        elif "groundedness_flag" in lowered:
            # ReflectionOutput (reflect_v1.py)
            return '{"confidence_score": 0.9, "groundedness_flag": true, "confidence_tier": "High"}'
        elif "severity_initial" in lowered:
            # ClassificationOutput (classify_v1.py) — checked after the two
            # more specific markers above since this is the most common/
            # generic-looking prompt shape, minimizing accidental overlap.
            return '{"category": "usage", "severity_initial": "Low"}'
        elif "severity_reasoning" in lowered or "severity_final" in lowered:
            # IncidentSeverityOutput — not yet a real schema (Stage 6), kept
            # for forward compatibility once that prompt file exists.
            return '{"severity_final": "High", "severity_reasoning": "Mock reasoning"}'
        elif "human_handoff_summary" in lowered:
            # EscalationOutput — not yet a real schema (Stage 7); Stage 5's
            # own escalate_node makes no LLM call at all (see escalate.py).
            return '{"escalation_reason": "Mock reason", "human_handoff_summary": "Mock summary"}'

        # Default response — matches ClassificationOutput's shape, the most
        # common caller if a future prompt doesn't match any marker above.
        return '{"category": "usage", "severity_initial": "Low"}'

    async def generate_vision(self, image_bytes: bytes, prompt: str, **kwargs: Any) -> str:
        # Canned, deterministic caption — ignores the image bytes entirely
        # and makes no network call, same reasoning as generate()'s canned
        # responses (needed for L2 component tests, §19).
        return "Mock image caption: a screenshot or diagram from a support document."

    async def embed(self, text: str, **kwargs: Any) -> list[float]:
        return _deterministic_vector(text)

    async def embed_batch(self, texts: list[str], **kwargs: Any) -> list[list[float]]:
        return [_deterministic_vector(t) for t in texts]

    @property
    def embedding_namespace(self) -> str:
        return "mock"
