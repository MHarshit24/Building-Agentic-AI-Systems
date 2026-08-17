"""
FastAPI application for RAG vectorstore operations.
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
from main.routes.routes import router

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Smart Auto Advisor - RAG API",
    description="API for uploading data and querying the vectorstore",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
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
        "message": "Smart Auto Advisor RAG API",
        "version": "1.0.0",
        "endpoints": {
            "upload": "/api/v1/upload",
            "query": "/api/v1/query",
            "docs": "/docs"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

