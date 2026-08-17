"""
FastAPI Application
Main FastAPI app initialization and configuration.
"""

import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from main.routes.routes import router
from main.service.rag_service import initialize_services

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Evaluated RAG Pipeline with Langfuse and Human Handoff",
    description="Evaluated RAG Pipeline with Langfuse and Human Handoff",
    version="1.0.0"
)

# CORS configuration
cors_origins = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:3000,http://localhost:8000"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in cors_origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(router)


# Initialize services on startup
@app.on_event("startup")
async def startup_event():
    """Initialize services when API starts."""
    logger.info("Starting API server...")
    try:
        initialize_services()
        logger.info("✓ API server started successfully")
    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        raise

