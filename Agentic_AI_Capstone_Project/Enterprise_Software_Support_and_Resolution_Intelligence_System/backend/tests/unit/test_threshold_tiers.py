"""
tests/unit/test_threshold_tiers.py

Unit coverage for confidence-tier boundary logic across both places it
lives: app/orchestration/nodes/reflect.py's _tier_for() (used live, at
request time) and evaluation/calibrate_thresholds.py's
_tier_for_threshold()/search_thresholds() (used offline, during
calibration). Genuine coverage gap confirmed before writing this: no
existing test (test_router.py's TestDecideAction included) exercises the
threshold-BOUNDARY behavior of either function — test_router.py takes an
already-computed confidence_tier string as input; it never tests what
raw score maps to which tier in the first place. Not tied to a specific
§25 roadmap line (checked the full stage-by-stage roadmap text; this
filename isn't named anywhere in it) — written now because it's the most
direct, deterministic way to guard Stage 8's threshold-calibration work
(a bad calibrated_thresholds.json, or a future edit to either tiering
function, would otherwise have zero test coverage catching a boundary
regression).
"""

from __future__ import annotations

import evaluation.calibrate_thresholds as calibrate_thresholds_module
from app.orchestration.nodes import reflect
from evaluation.calibrate_thresholds import _tier_for_threshold, search_thresholds


class _FakeSettings:
    def __init__(self, high: float, medium: float) -> None:
        self.confidence_high_threshold = high
        self.confidence_medium_threshold = medium


class TestReflectTierFor:
    """reflect.py's _tier_for() reads thresholds fresh via get_settings()
    on every call (not module constants — deliberately, per Stage 8's own
    calibration-override design), so every test here monkeypatches
    get_settings() to a fixed, known pair rather than depending on
    whatever project .env / calibrated_thresholds.json happens to be on
    disk — deterministic regardless of ambient calibration state."""

    def test_exactly_at_high_threshold_is_high(self, monkeypatch):
        monkeypatch.setattr(reflect, "get_settings", lambda: _FakeSettings(high=0.85, medium=0.70))
        assert reflect._tier_for(0.85) == "High"

    def test_just_below_high_threshold_is_medium(self, monkeypatch):
        monkeypatch.setattr(reflect, "get_settings", lambda: _FakeSettings(high=0.85, medium=0.70))
        assert reflect._tier_for(0.849999) == "Medium"

    def test_above_high_threshold_is_high(self, monkeypatch):
        monkeypatch.setattr(reflect, "get_settings", lambda: _FakeSettings(high=0.85, medium=0.70))
        assert reflect._tier_for(0.95) == "High"

    def test_exactly_at_medium_threshold_is_medium(self, monkeypatch):
        monkeypatch.setattr(reflect, "get_settings", lambda: _FakeSettings(high=0.85, medium=0.70))
        assert reflect._tier_for(0.70) == "Medium"

    def test_just_below_medium_threshold_is_low(self, monkeypatch):
        monkeypatch.setattr(reflect, "get_settings", lambda: _FakeSettings(high=0.85, medium=0.70))
        assert reflect._tier_for(0.699999) == "Low"

    def test_zero_is_low(self, monkeypatch):
        monkeypatch.setattr(reflect, "get_settings", lambda: _FakeSettings(high=0.85, medium=0.70))
        assert reflect._tier_for(0.0) == "Low"

    def test_reads_updated_thresholds_on_next_call(self, monkeypatch):
        # Proves _tier_for() genuinely re-reads get_settings() each call
        # (the whole point of Stage 8's design: a recalibration takes
        # effect on the next process start with no source-code edit)
        # rather than having cached/memoized a value at module-import time.
        monkeypatch.setattr(reflect, "get_settings", lambda: _FakeSettings(high=0.50, medium=0.30))
        assert reflect._tier_for(0.60) == "High"


class TestTierForThreshold:
    """calibrate_thresholds.py's own tier-bucketing helper — pure
    function, candidate (high, medium) pair passed directly, no
    get_settings() involved at all."""

    def test_at_high_boundary(self):
        assert _tier_for_threshold(0.90, high=0.90, medium=0.70) == "High"

    def test_at_medium_boundary(self):
        assert _tier_for_threshold(0.70, high=0.90, medium=0.70) == "Medium"

    def test_below_medium_boundary(self):
        assert _tier_for_threshold(0.69, high=0.90, medium=0.70) == "Low"


class TestSearchThresholds:
    """search_thresholds()'s grid search — the actual Stage 8 calibration
    logic being guarded here. Verified against small, hand-computable
    scenarios where the correct winning (high, medium) pair is knowable
    by inspection, not just "the search ran without crashing.\""""

    def test_all_correct_prefers_highest_threshold_pair_on_tie(self):
        # Every record is correct, so every candidate pair ties at
        # tsr=1.0 (Low is always safe; High/Medium succeed since
        # correct=True everywhere) -- the tie-break rule (favor higher
        # `high`, per §6's "without over-escalating" framing) must pick
        # the maximum candidate, 0.95.
        records = [
            {"confidence_score": 0.95, "correct": True, "is_critical_severity": False},
            {"confidence_score": 0.80, "correct": True, "is_critical_severity": False},
            {"confidence_score": 0.60, "correct": True, "is_critical_severity": False},
        ]
        result = search_thresholds(records)
        assert result["high"] == 0.95
        assert result["tsr"] == 1.0

    def test_wrong_answer_gets_pushed_into_low_tier_by_a_high_enough_medium_cutoff(self):
        # A single wrong, moderate-confidence (0.72) answer: at
        # medium<=0.72 it buckets Medium (wrong -> failure); only
        # medium=0.75 (the one candidate above 0.72) buckets it Low
        # (always safe -> success). The search must find that pair,
        # proving it actually explores raising thresholds to catch a
        # wrong answer that would otherwise auto-respond incorrectly.
        records = [
            {"confidence_score": 0.72, "correct": False, "is_critical_severity": False},
        ]
        result = search_thresholds(records)
        assert result["medium"] == 0.75
        assert result["tsr"] == 1.0
        # Any high > 0.75 works equally (tsr=1.0 either way); tie-break
        # picks the largest, 0.95.
        assert result["high"] == 0.95

    def test_critical_severity_always_counts_as_success_regardless_of_threshold(self):
        records = [
            {"confidence_score": 0.10, "correct": False, "is_critical_severity": True},
        ]
        result = search_thresholds(records)
        assert result["tsr"] == 1.0

    def test_empty_records_still_returns_a_computed_pair_not_the_settings_fallback(self):
        # Real behavior, confirmed by reading the code, not assumed: the
        # outer loop iterates over the FIXED candidate grids regardless
        # of whether `records` is empty, so `best` is always set on the
        # very first (high, medium) pair tried. The get_settings()-based
        # fallback branch (reached only if `best` were still None after
        # the loop) is therefore unreachable given today's non-empty
        # _HIGH_CANDIDATES/_MEDIUM_CANDIDATES grids -- a real, if
        # low-stakes, piece of dead code worth knowing about rather than
        # silently assuming it's live. This test documents the actual
        # behavior rather than the apparent intent of that fallback.
        result = search_thresholds([])
        assert result == {"high": 0.95, "medium": 0.55, "tsr": 0.0}

    def test_settings_fallback_would_apply_if_best_were_ever_none(self, monkeypatch):
        # Directly exercises the fallback branch's own logic in isolation
        # (can't reach it through search_thresholds() itself today, per
        # the test above) so the fallback's behavior is still guarded
        # even though it's currently dead code.
        monkeypatch.setattr(
            calibrate_thresholds_module, "get_settings", lambda: _FakeSettings(high=0.85, medium=0.70)
        )
        monkeypatch.setattr(calibrate_thresholds_module, "_HIGH_CANDIDATES", [])
        result = search_thresholds([{"confidence_score": 0.9, "correct": True, "is_critical_severity": False}])
        assert result == {"high": 0.85, "medium": 0.70, "tsr": 0.0}
