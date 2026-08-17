"""Responsible for tests covering the manager agent behavior."""

from app.agents.manager_agent import ManagerAgent
from app.schemas.domain import (
    BudgetPlan,
    LogisticsPlan,
    MarketingPlan,
    RiskRegister,
    ScheduleTimeline,
)


def test_decompose_initial_iteration(mock_llm_complete, sample_event_brief):
    state = {
        "brief": sample_event_brief,
        "iteration_count": 0,
        "active_revision_targets": [],
    }

    result = ManagerAgent().decompose(state)

    assert result["iteration_count"] == 1
    assert result["active_revision_targets"] == [
        "logistics",
        "budget",
        "marketing",
        "schedule",
        "risk",
    ]


def test_synthesize_returns_blueprint(mock_llm_complete, sample_event_brief):
    state = {
        "plan_id": "test-plan-1",
        "brief": sample_event_brief,
        "specialist_outputs": {
            "logistics": LogisticsPlan(
                venue="auditorium",
                capacity=200,
                layout_notes="rows",
                catering="coffee",
                vendors=["vendor-a"],
                equipment=["projector"],
            ),
            "budget": BudgetPlan(
                total_estimated_cost=400000.0,
                currency="INR",
                category_breakdown={"venue": 200000.0},
                within_budget=True,
            ),
            "marketing": MarketingPlan(
                channels=["email"],
                content_calendar=["launch"],
                outreach_start_date=sample_event_brief.timeline.preferred_date,
            ),
            "schedule": ScheduleTimeline(
                milestones=[{"name": "launch", "date": "2030-12-01"}],
                conflicts_detected=[],
            ),
            "risk": RiskRegister(risks=[], contingency_notes=""),
        },
    }

    result = ManagerAgent().synthesize(state)

    assert "draft_blueprint" in result
    assert result["draft_blueprint"] is not None
