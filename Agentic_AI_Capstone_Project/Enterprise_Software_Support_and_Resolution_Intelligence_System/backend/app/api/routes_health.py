from typing import Any
from fastapi import APIRouter, Depends, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as redis
import httpx

from app.db.session import get_db
from app.config import get_settings
from app.middleware.rate_limit import limiter

router = APIRouter()

@router.get("/health")
@limiter.limit("60/minute")
async def health_check(request: Request, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Health check endpoint checking Postgres, Redis, and Azure OpenAI reachability."""
    settings = get_settings()
    health_status: dict[str, Any] = {"status": "ok"}
    
    # 1. Check Postgres
    try:
        await db.execute(text("SELECT 1"))
        health_status["postgres"] = "ok"
    except Exception as e:
        health_status["postgres"] = f"error: {str(e)}"
        health_status["status"] = "degraded"
        
    # 2. Check Redis
    if settings.redis_url:
        try:
            redis_client = redis.from_url(settings.redis_url)
            async with redis_client:
                await redis_client.ping()
            health_status["redis"] = "ok"
        except Exception as e:
            health_status["redis"] = f"error: {str(e)}"
            health_status["status"] = "degraded"
    else:
        health_status["redis"] = "not_configured"
        
    # 3. Check Azure OpenAI
    if settings.llm_provider != "mock":
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # Attempt to reach the base endpoint to verify network path
                url = f"{settings.azure_openai_endpoint.rstrip('/')}/openai/deployments?api-version={settings.azure_openai_api_version}"
                headers = {"api-key": settings.azure_openai_api_key}
                response = await client.get(url, headers=headers)
                # 401/404/200 are all fine for reachability, meaning the service is up.
                health_status["azure_openai"] = "ok"
        except Exception as e:
            health_status["azure_openai"] = f"error: {str(e)}"
            health_status["status"] = "degraded"
    else:
        health_status["azure_openai"] = "skipped (mock provider)"
        
    return health_status
