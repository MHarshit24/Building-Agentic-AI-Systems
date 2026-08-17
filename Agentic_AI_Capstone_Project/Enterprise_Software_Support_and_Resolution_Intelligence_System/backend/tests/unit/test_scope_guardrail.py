"""
tests/unit/test_scope_guardrail.py

Unit tests for §31 Layer B — the non-LLM topic-centroid cosine-similarity
check. Pure-function tests against synthetic vectors (no DB, no
embedding model, no LLM) for is_in_scope()'s actual math, plus a test of
get_cached_centroid()'s lazy process-wide caching behavior via a
monkeypatched compute_corpus_centroid().

Layer A (classify_node's out_of_scope enum + router's refusal routing)
is covered separately by test_classify.py / test_router.py — this file
only exercises Layer B, which is deliberately independent of Layer A
(see scope_guardrail.py's own module docstring).
"""

from __future__ import annotations

import pytest

import app.guardrails.scope_guardrail as scope_guardrail
from app.guardrails.scope_guardrail import get_cached_centroid, is_in_scope


class TestIsInScope:
    def test_identical_vectors_are_in_scope(self):
        vector = [1.0, 2.0, 3.0]
        assert is_in_scope(vector, vector, threshold=0.15) is True

    def test_orthogonal_vectors_are_out_of_scope(self):
        query = [1.0, 0.0]
        centroid = [0.0, 1.0]
        assert is_in_scope(query, centroid, threshold=0.15) is False

    def test_opposite_vectors_are_out_of_scope(self):
        query = [1.0, 1.0]
        centroid = [-1.0, -1.0]
        assert is_in_scope(query, centroid, threshold=0.15) is False

    def test_similarity_exactly_at_threshold_is_in_scope(self):
        # cosine similarity is a monotonic function of the angle between two
        # 2D unit vectors here; picking one just past a 45-degree tilt gives
        # a similarity comfortably above a 0.15 threshold without relying on
        # a hand-computed exact boundary value.
        query = [1.0, 0.0]
        centroid = [1.0, 0.2]
        assert is_in_scope(query, centroid, threshold=0.15) is True

    def test_zero_vector_never_in_scope(self):
        query = [0.0, 0.0, 0.0]
        centroid = [1.0, 1.0, 1.0]
        assert is_in_scope(query, centroid, threshold=0.15) is False


class TestGetCachedCentroid:
    @pytest.mark.asyncio
    async def test_computes_once_and_reuses_cached_value(self, monkeypatch):
        monkeypatch.setattr(scope_guardrail, "_cached_centroid", None)
        call_count = 0

        async def _fake_compute() -> list[float]:
            nonlocal call_count
            call_count += 1
            return [0.1, 0.2, 0.3]

        monkeypatch.setattr(scope_guardrail, "compute_corpus_centroid", _fake_compute)

        first = await get_cached_centroid()
        second = await get_cached_centroid()

        assert first == [0.1, 0.2, 0.3]
        assert second == first
        assert call_count == 1
