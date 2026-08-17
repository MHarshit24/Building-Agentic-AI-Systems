"""
tests/unit/test_router.py

router.py's two pure functions — route_by_category() and decide_action()
— have zero LLM involvement (§6.1: "deterministic, auditable, no LLM call
needed"), so these are exhaustive unit tests against every documented
input combination, not L2 component tests.
"""

from __future__ import annotations

import pytest

from app.orchestration.graph import _route_after_classify
from app.orchestration.nodes.router import (
    decide_action,
    resolve_effective_severity,
    route_by_category,
    should_escalate_for_explicit_request,
)


class TestRouteByCategory:
    def test_out_of_scope_returns_none(self):
        assert route_by_category("out_of_scope", "Low") is None

    def test_critical_severity_overrides_category(self):
        assert route_by_category("usage", "Critical") == "Critical"
        assert route_by_category("billing", "Critical") == "Critical"

    def test_billing_routes_to_sql(self):
        assert route_by_category("billing", "Medium") == "SQL"

    @pytest.mark.parametrize("category", ["incident", "security"])
    def test_incident_and_security_route_to_hybrid(self, category):
        assert route_by_category(category, "High") == "Hybrid"

    @pytest.mark.parametrize("category", ["usage", "integration"])
    def test_usage_and_integration_route_to_rag(self, category):
        assert route_by_category(category, "Low") == "RAG"


class TestShouldEscalateForExplicitRequest:
    def test_true_when_explicitly_requested(self):
        assert should_escalate_for_explicit_request(True) is True

    def test_false_when_not_requested(self):
        assert should_escalate_for_explicit_request(False) is False


class TestRouteAfterClassifyExplicitHumanRequestOverride:
    """README §5's 'explicit request for human support' trigger must
    short-circuit straight to escalate_node — bypassing doc_retrieval/
    reflect entirely — regardless of what category/severity classify_node
    also produced, the same way out_of_scope already bypasses to the
    fixed refusal. These test _route_after_classify (graph.py) directly,
    not just the standalone predicate above, since the predicate alone
    doesn't prove the override actually wins over the graph's normal
    routing decision."""

    def test_explicit_request_overrides_what_would_otherwise_be_a_clean_rag_route(self):
        # category="usage" + severity_initial="Low" would normally route to
        # router_node -> RAG (a clean, unescalated documentation answer) —
        # proving the short-circuit actually overrides normal routing, not
        # just adds an alternative path alongside it.
        state = {
            "escalation_flag": False,
            "explicit_human_request": True,
            "category": "usage",
            "severity_initial": "Low",
        }
        assert _route_after_classify(state) == "escalate_node"

    def test_explicit_request_overrides_out_of_scope_too(self):
        state = {
            "escalation_flag": False,
            "explicit_human_request": True,
            "category": "out_of_scope",
            "severity_initial": "Low",
        }
        assert _route_after_classify(state) == "escalate_node"

    def test_no_explicit_request_falls_through_to_normal_out_of_scope_check(self):
        state = {
            "escalation_flag": False,
            "explicit_human_request": False,
            "category": "out_of_scope",
            "severity_initial": "Low",
        }
        assert _route_after_classify(state) == "out_of_scope_refusal_node"

    def test_no_explicit_request_falls_through_to_router_node(self):
        state = {
            "escalation_flag": False,
            "explicit_human_request": False,
            "category": "usage",
            "severity_initial": "Low",
        }
        assert _route_after_classify(state) == "router_node"

    def test_structured_output_error_guard_still_takes_priority(self):
        # escalation_flag=True (set by graph.py's StructuredOutputError
        # guard) must win even if explicit_human_request also happens to
        # be True — the failure path isn't a judgment call to override.
        state = {
            "escalation_flag": True,
            "explicit_human_request": True,
            "category": "usage",
            "severity_initial": "Low",
        }
        assert _route_after_classify(state) == "escalate_node"


class TestResolveEffectiveSeverity:
    def test_prefers_severity_final_when_set(self):
        assert resolve_effective_severity("Critical", "Low") == "Critical"

    def test_falls_back_to_severity_initial_when_final_is_none(self):
        assert resolve_effective_severity(None, "High") == "High"

    def test_both_none(self):
        assert resolve_effective_severity(None, None) is None


class TestDecideAction:
    def test_critical_severity_always_escalates(self):
        assert decide_action("Critical", "High") == ("escalate", False)
        assert decide_action("Critical", "Low") == ("escalate", False)

    def test_low_confidence_always_escalates(self):
        assert decide_action("Low", "Low") == ("escalate", False)
        assert decide_action(None, "Low") == ("escalate", False)

    def test_medium_confidence_responds_flagged(self):
        assert decide_action("Low", "Medium") == ("respond", True)

    def test_high_severity_responds_flagged_even_at_high_confidence(self):
        assert decide_action("High", "High") == ("respond", True)

    def test_low_severity_high_confidence_responds_unflagged(self):
        assert decide_action("Low", "High") == ("respond", False)

    def test_severity_fallback_regression_high_high(self):
        """Regression case named explicitly in the Stage 5 plan: if graph.py
        ever passed raw severity_final (always None in Stage 5, since
        incident_severity_node doesn't exist yet) instead of resolving it
        through resolve_effective_severity() first, a
        severity_initial="High" + confidence_tier="High" query would
        silently fall through to ("respond", False) instead of the correct
        ("respond", True) — dropping a flagged_for_review case the QA
        sampling mechanism depends on."""
        severity_final = None
        severity_initial = "High"
        confidence_tier = "High"

        effective_severity = resolve_effective_severity(severity_final, severity_initial)
        assert effective_severity == "High"

        assert decide_action(effective_severity, confidence_tier) == ("respond", True)
