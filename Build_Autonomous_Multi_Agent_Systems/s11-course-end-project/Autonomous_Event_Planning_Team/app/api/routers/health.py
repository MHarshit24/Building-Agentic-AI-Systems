"""Responsible for health check API endpoints."""

from fastapi import APIRouter, Request

from app.api.schemas.responses import APIResponse, HealthResponse
from app.config import get_settings
from app.llm.model_router import available_providers

router = APIRouter()


@router.get("/health", response_model=APIResponse[HealthResponse])
def health(request: Request) -> APIResponse[HealthResponse]:
    providers = available_providers()
    data = HealthResponse(
        status="ok",
        llm_configured=bool(providers),
        available_providers=providers,
        default_quality_gate_threshold=get_settings().quality_gate_threshold,
    )
    return APIResponse[HealthResponse].ok(data, request_id=request.state.request_id)
