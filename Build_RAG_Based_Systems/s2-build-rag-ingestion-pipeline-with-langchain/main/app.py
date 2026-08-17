"""
FastAPI application for Smart Auto Advisor RAG Ingestion Pipeline.

Smart Auto Advisor is an AI-powered conversational assistant for car manufacturers
that helps customers get instant answers about vehicle models, features, pricing, and availability.
"""

import sys
import logging
from pathlib import Path

# Add project root to Python path to allow imports when running script directly
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from main.config import setup_logging
from main.routes.ingestion_routes import router

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Smart Auto Advisor - RAG Ingestion API",
    description="API for uploading documents and triggering RAG ingestion pipeline. "
                "Smart Auto Advisor is an AI-powered conversational assistant for car manufacturers "
                "that helps customers get instant answers about vehicle models, features, pricing, and availability.",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Set explicit origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Smart Auto Advisor - RAG Ingestion API",
        "description": "AI-powered conversational assistant for car manufacturers",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

