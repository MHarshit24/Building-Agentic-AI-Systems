"""Responsible for tests covering the plans API endpoint."""

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_orchestrator
from app.config import get_settings
from app.main import app
from app.orchestrator.graph_builder import PlanNotFoundError
from app.schemas.domain import (
    BudgetPlan,
    CritiqueNote,
    EventBlueprint,
    EventOverview,
    LogisticsPlan,
    MarketingPlan,
    RiskRegister,
    ScheduleTimeline,
)

def _sample_blueprint() -> EventBlueprint:
    return EventBlueprint(
        overview=EventOverview(
            event_type="AI Workshop",
            objective="Educate 200 students",
            audience_size=200,
            date=date(2030, 12, 1),
            summary="A one-day AI workshop for 200 students.",
        ),
        logistics=LogisticsPlan(
            venue="Downtown Conference Center",
            capacity=200,
            layout_notes="theater seating",
            catering="Buffet lunch",
            vendors=["AV vendor"],
            equipment=["Projector"],
        ),
        budget=BudgetPlan(
            total_estimated_cost=148500.0,
            currency="INR",
            category_breakdown={"venue": 33000.0},
            within_budget=True,
        ),
        marketing=MarketingPlan(
            channels=["email"],
            content_calendar=["launch"],
            outreach_start_date=date(2030, 11, 1),
        ),
        schedule=ScheduleTimeline(milestones=[{"name": "Event day", "date": "2030-12-01"}]),
        risks=RiskRegister(risks=[], contingency_notes=""),
    )


class FakeOrchestrator:
    """Stands in for PlanningOrchestrator so these tests never touch the
    real LangGraph graph or an LLM."""

    def __init__(self):
        self.plans = {}

    async def run_new_plan(self, plan_id, brief, **kwargs):
        state = {
            "status": "completed",
            "iteration_count": 1,
            "max_iterations": 3,
            "provider": kwargs.get("provider"),
            "active_revision_targets": [],
            "specialist_outputs": {"logistics": None, "budget": None, "marketing": None, "schedule": None, "risk": None},
            "draft_blueprint": _sample_blueprint(),
            "critique_history": [
                CritiqueNote(iteration=1, score=0.9, passed=True, revision_targets=[], notes={})
            ],
        }
        self.plans[plan_id] = state
        return state

    async def get_plan_state(self, plan_id):
        return self.plans.get(plan_id)

    async def refine_plan(self, plan_id, instruction, target_agents=None, **kwargs):
        if plan_id not in self.plans:
            raise PlanNotFoundError(f"Plan {plan_id} was not found")
        return self.plans[plan_id]


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("PRESIDIO_ENABLED", "false")
    # plan_store (app/store/plan_store.py) is SQLite-backed; point it at a
    # throwaway per-test file so tests never see another test's rows.
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test_plans.db'}")
    get_settings.cache_clear()

    fake_orchestrator = FakeOrchestrator()
    app.dependency_overrides[get_orchestrator] = lambda: fake_orchestrator
    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    get_settings.cache_clear()


def test_create_plan_returns_in_progress_immediately(client, sample_event_brief):
    response = client.post("/plans", json=sample_event_brief.model_dump(mode="json"))

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["error"] is None
    assert body["request_id"]
    assert body["data"]["status"] == "in_progress"
    assert body["data"]["max_iterations"] == 3
    assert body["data"]["blueprint"] is None


def test_create_plan_then_get_shows_completed_blueprint(client, sample_event_brief):
    # TestClient runs FastAPI BackgroundTasks to completion synchronously as
    # part of the POST call, so the background job has already finished by
    # the time this GET runs — no sleep/poll loop needed here.
    create_response = client.post("/plans", json=sample_event_brief.model_dump(mode="json"))
    plan_id = create_response.json()["data"]["plan_id"]

    get_response = client.get(f"/plans/{plan_id}")

    assert get_response.status_code == 200
    body = get_response.json()
    assert body["success"] is True
    assert body["data"]["status"] == "completed"
    assert body["data"]["blueprint"]["overview"]["event_type"] == "AI Workshop"


def test_get_plan_shows_live_progress_while_in_flight(client):
    # Simulates what polling sees mid-run: the checkpointer already has a
    # partial state (some specialists done, others still active) before the
    # graph has finished — this is the whole point of the polling design.
    orchestrator = app.dependency_overrides[get_orchestrator]()
    orchestrator.plans["mid-flight"] = {
        "status": "in_progress",
        "iteration_count": 1,
        "max_iterations": 3,
        "active_revision_targets": ["schedule", "risk"],
        "specialist_outputs": {"logistics": None, "budget": None, "marketing": None},
        "draft_blueprint": None,
        "critique_history": [],
    }

    response = client.get("/plans/mid-flight")

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["status"] == "in_progress"
    assert set(body["data"]["specialist_outputs_ready"]) == {"logistics", "budget", "marketing"}
    assert body["data"]["active_revision_targets"] == ["schedule", "risk"]
    assert body["data"]["blueprint"] is None


def test_get_unknown_plan_returns_404(client):
    response = client.get("/plans/does-not-exist")

    assert response.status_code == 404
    body = response.json()
    assert body["success"] is False
    assert body["data"] is None
    assert body["error"]["code"] == "NOT_FOUND"
    assert body["request_id"]


def test_create_plan_records_failure_from_background_task(client, sample_event_brief):
    orchestrator = app.dependency_overrides[get_orchestrator]()

    async def _raise(plan_id, brief, **kwargs):
        raise RuntimeError("simulated graph failure")

    orchestrator.run_new_plan = _raise

    create_response = client.post("/plans", json=sample_event_brief.model_dump(mode="json"))
    plan_id = create_response.json()["data"]["plan_id"]

    get_response = client.get(f"/plans/{plan_id}")
    body = get_response.json()

    assert body["data"]["status"] == "failed"
    assert "simulated graph failure" in body["data"]["error_message"]


def test_create_then_refine_plan_succeeds(client, sample_event_brief):
    create_response = client.post("/plans", json=sample_event_brief.model_dump(mode="json"))
    plan_id = create_response.json()["data"]["plan_id"]
    client.get(f"/plans/{plan_id}")  # ensure the create background task has run

    refine_response = client.post(f"/plans/{plan_id}/refine", json={"instruction": "reduce catering budget"})
    assert refine_response.status_code == 200
    assert refine_response.json()["data"]["status"] == "in_progress"

    get_response = client.get(f"/plans/{plan_id}")
    body = get_response.json()
    assert body["success"] is True
    assert body["data"]["plan_id"] == plan_id
    assert body["data"]["status"] == "completed"


def test_refine_clears_stale_terminal_plan_store_record(client, sample_event_brief, monkeypatch):
    # Without this, get_plan() would keep serving the *previous* completed
    # result throughout the entire refine run (it prefers a terminal
    # plan_store record over live checkpointer state), instead of showing
    # live progress until the refine itself finishes.
    import app.api.routers.plans as plans_module
    from app.store import plan_store as plan_store_module

    create_response = client.post("/plans", json=sample_event_brief.model_dump(mode="json"))
    plan_id = create_response.json()["data"]["plan_id"]
    client.get(f"/plans/{plan_id}")
    assert plan_store_module.get_plan(plan_id)["status"] == "completed"

    async def _noop(*args, **kwargs):
        return None

    # Neutralize the background job itself so only the synchronous
    # stale-record-clearing effect (which runs before backgrounding) shows.
    monkeypatch.setattr(plans_module, "_execute_refine", _noop)

    client.post(f"/plans/{plan_id}/refine", json={"instruction": "add more detail"})

    assert plan_store_module.get_plan(plan_id)["status"] == "in_progress"


def test_refine_unknown_plan_returns_404(client):
    response = client.post("/plans/does-not-exist/refine", json={"instruction": "add more risk detail"})

    assert response.status_code == 404
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "NOT_FOUND"
