"""Responsible for tests covering specialist agent behavior."""

import json
import sys
from datetime import date

from app.agents.budget_agent import BudgetAgent
from app.agents.logistics_agent import LogisticsAgent
from app.agents.marketing_agent import MarketingAgent
from app.agents.risk_agent import RiskAgent
from app.agents.schedule_agent import ScheduleAgent
from app.schemas.domain import (
    BudgetConstraint,
    BudgetPlan,
    CritiqueNote,
    EventBrief,
    LogisticsPlan,
    MarketingPlan,
    RiskRegister,
    ScheduleTimeline,
    TimelinePreference,
)


def _set_llm_response(monkeypatch, response: str):
    """Point app.llm.client.complete (as seen through BaseAgent._think's
    runtime import) at a fixed response, overriding the mock_llm_complete
    fixture's default "MOCKED_LLM_RESPONSE"."""
    monkeypatch.setattr(sys.modules["app.llm.client"], "complete", lambda prompt, **kwargs: response)


def _state_for(brief):
    return {"plan_id": "test-plan-1", "brief": brief, "constraints": brief.constraints, "specialist_outputs": {}}


# ---- LogisticsAgent ---------------------------------------------------------

def test_logistics_agent_falls_back_when_llm_output_is_unparseable(mock_llm_complete, sample_event_brief):
    result = LogisticsAgent().run(_state_for(sample_event_brief))

    assert set(result.keys()) == {"logistics"}
    plan = result["logistics"]
    assert isinstance(plan, LogisticsPlan)
    assert plan.capacity >= sample_event_brief.audience_size
    assert plan.catering == "Standard catering package sized for the expected audience."
    assert plan.vendors == ["AV vendor", "Catering vendor"]


def test_logistics_agent_uses_parsed_llm_json(monkeypatch, mock_llm_complete, sample_event_brief):
    _set_llm_response(
        monkeypatch,
        json.dumps({"catering": "Buffet lunch", "vendors": ["Vendor A"], "equipment": ["Mic"]}),
    )

    result = LogisticsAgent().run(_state_for(sample_event_brief))

    plan = result["logistics"]
    assert plan.catering == "Buffet lunch"
    assert plan.vendors == ["Vendor A"]
    assert plan.equipment == ["Mic"]


# ---- BudgetAgent -------------------------------------------------------------

def test_budget_agent_falls_back_to_default_contingency(mock_llm_complete, sample_event_brief):
    result = BudgetAgent().run(_state_for(sample_event_brief))

    assert set(result.keys()) == {"budget"}
    plan = result["budget"]
    assert isinstance(plan, BudgetPlan)
    assert plan.currency == "INR"
    assert plan.within_budget is True
    assert plan.total_estimated_cost == 148500.0


def test_budget_agent_uses_parsed_cost_adjustment_factor(monkeypatch, mock_llm_complete, sample_event_brief):
    _set_llm_response(monkeypatch, json.dumps({"cost_adjustment_factor": 1.2}))

    result = BudgetAgent().run(_state_for(sample_event_brief))

    assert result["budget"].total_estimated_cost == 162000.0


def test_budget_agent_ignores_out_of_range_cost_adjustment_factor(monkeypatch, mock_llm_complete, sample_event_brief):
    _set_llm_response(monkeypatch, json.dumps({"cost_adjustment_factor": 5.0}))

    result = BudgetAgent().run(_state_for(sample_event_brief))

    assert result["budget"].total_estimated_cost == 148500.0


def test_budget_agent_can_cut_cost_below_baseline_to_fit_budget(monkeypatch, mock_llm_complete, sample_event_brief):
    # A one-way contingency (previous design) could only ever inflate the
    # baseline — this proves the agent can now actually bring an over-budget
    # plan down, which is the whole point of responding to critique feedback.
    _set_llm_response(monkeypatch, json.dumps({"cost_adjustment_factor": 0.6}))

    result = BudgetAgent().run(_state_for(sample_event_brief))

    assert result["budget"].total_estimated_cost == 81000.0


def test_budget_agent_includes_prior_feedback_in_prompt(monkeypatch, mock_llm_complete, sample_event_brief):
    captured_prompts = []
    monkeypatch.setattr(
        sys.modules["app.llm.client"],
        "complete",
        lambda prompt, **kwargs: captured_prompts.append(prompt) or "not json",
    )

    state = _state_for(sample_event_brief)
    state["critique_history"] = [
        CritiqueNote(
            iteration=1,
            score=0.4,
            passed=False,
            revision_targets=["budget"],
            notes={
                "feasibility": "ok",
                "budget_fit": "Way over budget — cut catering costs.",
                "risk_coverage": "ok",
                "coherence": "ok",
            },
        )
    ]

    BudgetAgent().run(state)

    assert any("cut catering costs" in prompt for prompt in captured_prompts)


def _over_budget_brief():
    return EventBrief(
        event_type="Product Launch",
        objective="Launch a new SaaS product",
        audience_size=150,
        budget=BudgetConstraint(currency="USD", max_amount=80000.0),
        timeline=TimelinePreference(preferred_date=date(2030, 5, 20), duration_days=1),
        constraints=[],
    )


def test_budget_agent_forces_compliance_when_llm_ignores_budget_revision_feedback(monkeypatch, mock_llm_complete):
    # The LLM defiantly picks the max contingency despite prior feedback
    # saying the plan is over budget — the deterministic safety net must
    # still bring it back under the cap rather than trusting the model.
    _set_llm_response(monkeypatch, json.dumps({"cost_adjustment_factor": 1.5}))

    state = _state_for(_over_budget_brief())
    state["critique_history"] = [
        CritiqueNote(
            iteration=1,
            score=0.3,
            passed=False,
            revision_targets=["budget"],
            notes={
                "feasibility": "ok",
                "budget_fit": "Over budget, cut costs.",
                "risk_coverage": "ok",
                "coherence": "ok",
            },
        )
    ]

    result = BudgetAgent().run(state)

    assert result["budget"].total_estimated_cost <= 80000.0
    assert result["budget"].within_budget is True


def test_budget_agent_does_not_force_compliance_on_first_draft(monkeypatch, mock_llm_complete):
    # No critique yet — a first draft is allowed to genuinely come in over
    # budget so the reflection loop has something real to catch and revise.
    _set_llm_response(monkeypatch, json.dumps({"cost_adjustment_factor": 1.5}))

    result = BudgetAgent().run(_state_for(_over_budget_brief()))

    assert result["budget"].total_estimated_cost == 153750.0
    assert result["budget"].within_budget is False


# ---- MarketingAgent -----------------------------------------------------------

def test_marketing_agent_falls_back_when_llm_output_is_unparseable(mock_llm_complete, sample_event_brief):
    result = MarketingAgent().run(_state_for(sample_event_brief))

    assert set(result.keys()) == {"marketing"}
    plan = result["marketing"]
    assert isinstance(plan, MarketingPlan)
    assert plan.channels == ["email", "social media"]
    assert plan.outreach_start_date == date(2030, 11, 1)


def test_marketing_agent_uses_parsed_llm_json(monkeypatch, mock_llm_complete, sample_event_brief):
    _set_llm_response(
        monkeypatch,
        json.dumps({"channels": ["newsletter"], "content_calendar": ["teaser"]}),
    )

    result = MarketingAgent().run(_state_for(sample_event_brief))

    assert result["marketing"].channels == ["newsletter"]
    assert result["marketing"].content_calendar == ["teaser"]


# ---- ScheduleAgent -------------------------------------------------------------

def test_schedule_agent_falls_back_to_baseline_milestones(mock_llm_complete, sample_event_brief):
    result = ScheduleAgent().run(_state_for(sample_event_brief))

    assert set(result.keys()) == {"schedule"}
    plan = result["schedule"]
    assert isinstance(plan, ScheduleTimeline)
    assert len(plan.milestones) == 5
    assert plan.milestones[-2]["name"] == "Event day"
    assert plan.milestones[-2]["date"] == "2030-12-01"
    assert plan.conflicts_detected == []


def test_schedule_agent_appends_llm_suggested_milestones(monkeypatch, mock_llm_complete, sample_event_brief):
    _set_llm_response(monkeypatch, json.dumps({"additional_milestones": ["Vendor tasting"]}))

    result = ScheduleAgent().run(_state_for(sample_event_brief))

    names = [m["name"] for m in result["schedule"].milestones]
    assert "Vendor tasting" in names
    assert len(result["schedule"].milestones) == 6


# ---- RiskAgent -----------------------------------------------------------------

def test_risk_agent_falls_back_when_llm_output_is_unparseable(mock_llm_complete, sample_event_brief):
    result = RiskAgent().run(_state_for(sample_event_brief))

    assert set(result.keys()) == {"risk"}
    plan = result["risk"]
    assert isinstance(plan, RiskRegister)
    assert len(plan.risks) == 3
    assert plan.contingency_notes


def test_risk_agent_uses_parsed_llm_json(monkeypatch, mock_llm_complete, sample_event_brief):
    _set_llm_response(
        monkeypatch,
        json.dumps(
            {
                "risks": [
                    {"name": "Weather", "likelihood": "low", "impact": "low", "mitigation": "Indoor venue"},
                ],
                "contingency_notes": "Minimal risk exposure.",
            }
        ),
    )

    result = RiskAgent().run(_state_for(sample_event_brief))

    assert result["risk"].risks == [
        {"name": "Weather", "likelihood": "low", "impact": "low", "mitigation": "Indoor venue"}
    ]
    assert result["risk"].contingency_notes == "Minimal risk exposure."


# ---- build_feedback_context ----------------------------------------------------

def test_build_feedback_context_first_draft_message():
    from app.agents.prompts.specialist_prompts import build_feedback_context

    assert build_feedback_context({"critique_history": []}) == "None — this is the first draft."
    assert build_feedback_context({}) == "None — this is the first draft."


def test_build_feedback_context_uses_latest_critique_only():
    from app.agents.prompts.specialist_prompts import build_feedback_context

    state = {
        "critique_history": [
            {"notes": {"budget_fit": "OLDNOTE"}},
            {"notes": {"budget_fit": "NEWNOTE"}},
        ]
    }

    context = build_feedback_context(state)

    assert "NEWNOTE" in context
    assert "OLDNOTE" not in context


# ---- Tools (deterministic, no LLM involved) -----------------------------------

def test_find_venue_picks_smallest_fitting_venue():
    from app.tools.venue_tool import find_venue

    result = find_venue(audience_size=200, venue_preference=None)

    assert result["venue"] == "Downtown Conference Center"
    assert result["capacity"] == 200


def test_find_venue_falls_back_to_largest_when_oversized():
    from app.tools.venue_tool import find_venue

    result = find_venue(audience_size=10_000, venue_preference=None)

    assert result["capacity"] == 3000
    assert "over capacity" in result["layout_notes"]


def test_estimate_costs_is_deterministic_for_same_inputs():
    from app.tools.pricing_tool import estimate_costs

    first = estimate_costs(audience_size=200, event_type="AI Workshop", currency="INR")
    second = estimate_costs(audience_size=200, event_type="AI Workshop", currency="INR")

    assert first == second
    assert first["total_estimated_cost"] == 135000.0


def test_estimate_costs_applies_event_type_multiplier():
    from app.tools.pricing_tool import estimate_costs

    workshop = estimate_costs(audience_size=200, event_type="AI Workshop", currency="INR")
    conference = estimate_costs(audience_size=200, event_type="conference", currency="INR")

    assert conference["total_estimated_cost"] > workshop["total_estimated_cost"]


def test_check_conflicts_detects_blackout_date():
    from app.tools.calendar_tool import build_milestones, check_conflicts

    preferred_date = date(2030, 12, 25)
    milestones = build_milestones(preferred_date, duration_days=1)

    conflicts = check_conflicts(preferred_date, milestones)

    assert any("Christmas" in c for c in conflicts)


def test_check_conflicts_detects_duplicate_milestone_dates():
    from app.tools.calendar_tool import check_conflicts

    preferred_date = date(2030, 12, 1)
    milestones = [
        {"name": "Kickoff", "date": "2030-11-01"},
        {"name": "Vendor tasting", "date": "2030-11-01"},
    ]

    conflicts = check_conflicts(preferred_date, milestones)

    assert len(conflicts) == 1
    assert "Kickoff" in conflicts[0] and "Vendor tasting" in conflicts[0]
