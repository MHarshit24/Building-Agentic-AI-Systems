"""Responsible for plan-related API router endpoints.

POST /plans and POST /plans/{id}/refine both return immediately and run the
graph as a background task, since a full run can take well over a minute
against real LLM providers. GET /plans/{id} is the poll target: the LangGraph
checkpointer (app/orchestrator/checkpointer.py) already persists
EventPlanState after every node, so polling it surfaces real progress.
"""

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request

from app.api.dependencies import get_orchestrator
from app.api.schemas.requests import CreatePlanRequest, RefinePlanRequest
from app.api.schemas.responses import APIResponse, PlanResponse, PlanSummary
from app.config import get_settings
from app.llm.model_router import available_providers
from app.orchestrator.graph_builder import PlanningOrchestrator
from app.schemas.domain import EventBrief
from app.security.pii_validator import sanitize_brief
from app.store import plan_store

router = APIRouter(prefix="/plans", tags=["plans"])


async def _execute_new_plan(
    orchestrator: PlanningOrchestrator,
    plan_id: str,
    brief: EventBrief,
    provider: str | None,
    quality_gate_threshold: float | None,
) -> None:
    try:
        final_state = await orchestrator.run_new_plan(
            plan_id, brief, provider=provider, quality_gate_threshold=quality_gate_threshold
        )
        plan_store.save_plan(
            plan_id=plan_id,
            status=final_state["status"],
            blueprint=final_state.get("draft_blueprint"),
            critique_history=final_state.get("critique_history", []),
        )
    except Exception as exc:  # noqa: BLE001 - this is the terminal error boundary for a background job
        plan_store.save_plan(
            plan_id=plan_id,
            status="failed",
            blueprint=None,
            critique_history=[],
            error_message=str(exc),
        )


async def _execute_refine(
    orchestrator: PlanningOrchestrator,
    plan_id: str,
    instruction: str,
    target_agents: list[str] | None,
) -> None:
    try:
        final_state = await orchestrator.refine_plan(plan_id, instruction, target_agents)
        plan_store.save_plan(
            plan_id=plan_id,
            status=final_state["status"],
            blueprint=final_state.get("draft_blueprint"),
            critique_history=final_state.get("critique_history", []),
        )
    except Exception as exc:  # noqa: BLE001 - terminal error boundary for a background job
        plan_store.save_plan(
            plan_id=plan_id,
            status="failed",
            blueprint=None,
            critique_history=[],
            error_message=str(exc),
        )


def _in_progress_response(
    plan_id: str,
    request: Request,
    provider: str | None = None,
    quality_gate_threshold: float | None = None,
) -> APIResponse[PlanResponse]:
    data = PlanResponse(
        plan_id=plan_id,
        status="in_progress",
        iteration_count=0,
        max_iterations=get_settings().max_iterations,
        quality_gate_threshold=quality_gate_threshold or get_settings().quality_gate_threshold,
        provider=provider,
    )
    return APIResponse[PlanResponse].ok(data, request_id=request.state.request_id)


@router.post("", response_model=APIResponse[PlanResponse])
async def create_plan(
    request: Request,
    body: CreatePlanRequest,
    background_tasks: BackgroundTasks,
    orchestrator: PlanningOrchestrator = Depends(get_orchestrator),
) -> APIResponse[PlanResponse]:
    if body.provider is not None and body.provider not in available_providers():
        raise HTTPException(
            status_code=400,
            detail=f"Provider {body.provider!r} is not configured on this server.",
        )

    brief = sanitize_brief(body)
    plan_id = str(uuid.uuid4())
    plan_store.register_plan(
        plan_id,
        brief.event_type,
        brief.objective,
        provider=body.provider,
        quality_gate_threshold=body.quality_gate_threshold,
    )

    background_tasks.add_task(
        _execute_new_plan, orchestrator, plan_id, brief, body.provider, body.quality_gate_threshold
    )

    return _in_progress_response(
        plan_id, request, provider=body.provider, quality_gate_threshold=body.quality_gate_threshold
    )


@router.get("", response_model=APIResponse[list[PlanSummary]])
async def list_plans(request: Request) -> APIResponse[list[PlanSummary]]:
    summaries = [PlanSummary.from_store(stored) for stored in plan_store.list_plans()]
    return APIResponse[list[PlanSummary]].ok(summaries, request_id=request.state.request_id)


@router.get("/{plan_id}", response_model=APIResponse[PlanResponse])
async def get_plan(
    plan_id: str,
    request: Request,
    orchestrator: PlanningOrchestrator = Depends(get_orchestrator),
) -> APIResponse[PlanResponse]:
    stored = plan_store.get_plan(plan_id)
    if stored is not None and stored["status"] != "in_progress":
        # Terminal (completed/needs_review/failed) — plan_store is
        # authoritative here, since a background failure never touches the
        # checkpointer and wouldn't otherwise be visible.
        return APIResponse[PlanResponse].ok(PlanResponse.from_store(plan_id, stored), request_id=request.state.request_id)

    state = await orchestrator.get_plan_state(plan_id)
    if state is not None:
        return APIResponse[PlanResponse].ok(PlanResponse.from_state(plan_id, state), request_id=request.state.request_id)

    if stored is not None:
        return APIResponse[PlanResponse].ok(PlanResponse.from_store(plan_id, stored), request_id=request.state.request_id)

    raise HTTPException(status_code=404, detail=f"Plan {plan_id} was not found")


@router.post("/{plan_id}/refine", response_model=APIResponse[PlanResponse])
async def refine_plan(
    plan_id: str,
    body: RefinePlanRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    orchestrator: PlanningOrchestrator = Depends(get_orchestrator),
) -> APIResponse[PlanResponse]:
    state = await orchestrator.get_plan_state(plan_id)
    stored = plan_store.get_plan(plan_id)
    if state is None and stored is None:
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} was not found")

    # A prior run of this plan may have already left a terminal record in
    # plan_store (e.g. "completed"). get_plan() prefers a terminal
    # plan_store record over live checkpointer state, so without clearing
    # it here, polling would keep showing the *old* result throughout this
    # entire refine instead of live progress, only updating once the refine
    # itself finishes.
    if stored is not None and stored["status"] != "in_progress":
        plan_store.save_plan(plan_id=plan_id, status="in_progress", blueprint=None, critique_history=[])

    background_tasks.add_task(_execute_refine, orchestrator, plan_id, body.instruction, body.target_agents)

    return _in_progress_response(plan_id, request)
