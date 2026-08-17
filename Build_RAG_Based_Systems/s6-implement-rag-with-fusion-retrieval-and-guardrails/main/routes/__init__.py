from .ingestion_routes import router as ingestion_router
from .query_routes import router as query_router

__all__ = ["ingestion_router", "query_router"]
