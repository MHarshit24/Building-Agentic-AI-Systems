"""FastAPI application for Personal Diet Counselling Assistant."""
import logging
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import router, rag_service

# Configure logging
logging.basicConfig(
    level=os.getenv("API_LOG_LEVEL", "info").upper(),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Personal Diet Counselling Assistant API",
    description="RAG-based Personal Diet Counselling Assistant with multi-modal content processing (text, tables, images) using LlamaIndex, Azure OpenAI, and PostgreSQL with PGVector",
    version="1.0.0"
)

# Configure CORS
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:8000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in cors_origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(router, tags=["diet-counselling"])


@app.on_event("startup")
async def startup_event():
    """Initialize services on application startup."""
    logger.info("Application starting up...")
    try:
        # Initialize the RAG service and load existing index from PostgreSQL
        rag_service.initialize()
        if rag_service.is_initialized():
            logger.info("Application startup completed successfully - index loaded")
        else:
            logger.info("Application startup completed - no existing index found (this is normal for first run)")
    except Exception as e:
        logger.warning(f"Error during startup (this is normal if no index exists yet): {e}")
