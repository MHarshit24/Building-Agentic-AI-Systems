"""
FastAPI application setup for Smart Auto Advisor RAG query pipeline.

Smart Auto Advisor is an AI-powered conversational assistant for car manufacturers
that helps customers get instant answers about vehicle models, features, pricing, and availability.
"""

import os
import logging
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .config import setup_logging, logger, load_config
from .services import (
    initialize_embeddings,
    initialize_llm,
    setup_vectorstore,
    build_rag_chain,
)

# Setup logging
setup_logging()


# ============================================================================
# Application State
# ============================================================================

class AppState:
    """Global application state"""
    config: Optional[Dict[str, Any]] = None
    embeddings: Optional[Any] = None
    llm: Optional[Any] = None
    vectorstore: Optional[Any] = None
    rag_chain: Optional[Any] = None
    retriever: Optional[Any] = None
    
    # Metrics
    total_queries: int = 0
    successful_queries: int = 0
    failed_queries: int = 0
    total_chunks_retrieved: int = 0
    start_time: datetime = datetime.now()


# Global application state instance
app_state = AppState()


# ============================================================================
# Error Response Model
# ============================================================================

class ErrorResponse(BaseModel):
    """Standard error response model"""
    error: str = Field(description="Error message")
    detail: Optional[str] = Field(default=None, description="Detailed error information")
    timestamp: str = Field(description="Error timestamp")


# ============================================================================
# Lifecycle Management
# ============================================================================

async def initialize_components():
    """Initialize all RAG pipeline components"""
    logger.info("="*80)
    logger.info("Starting RAG API component initialization")
    logger.info("="*80)
    try:
        # Load configuration
        logger.info("Step 1: Loading configuration")
        app_state.config = load_config()
        logger.info(f"Configuration loaded: {app_state.config['azure_llm_deployment']}")
        
        # Initialize components
        logger.info("Step 2: Initializing embedding model")
        app_state.embeddings = initialize_embeddings(app_state.config)
        
        logger.info("Step 3: Initializing LLM")
        app_state.llm = initialize_llm(app_state.config)
        
        logger.info("Step 4: Setting up vectorstore")
        app_state.vectorstore = setup_vectorstore(app_state.config, app_state.embeddings)
        
        logger.info("Step 5: Building RAG chain")
        app_state.rag_chain, app_state.retriever = build_rag_chain(
            app_state.vectorstore, 
            app_state.llm, 
            app_state.config
        )
        
        logger.info("="*80)
        logger.info("All components initialized successfully")
        logger.info("="*80)
        
    except Exception as e:
        logger.error(f"Failed to initialize components: {e}", exc_info=True)
        raise


async def shutdown_components():
    """Cleanup on shutdown"""
    logger.info("="*80)
    logger.info("Shutting down RAG pipeline...")
    logger.info("="*80)
    # Add cleanup logic if needed


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    # Startup
    logger.info("Starting AutoMind RAG API...")
    await initialize_components()
    app_state.start_time = datetime.now()
    
    yield
    # Shutdown
    await shutdown_components()


# Create FastAPI application
app = FastAPI(
    title="AutoMind RAG Query API",
    description="REST API for querying Smart Auto Advisor knowledge base using Retrieval-Augmented Generation",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
# CORS origins are configurable via CORS_ORIGINS environment variable
# Format: comma-separated list (e.g., "https://example.com,https://app.example.com")
# Default: ["*"] for development, but should be restricted in production
# Note: For production, set CORS_ORIGINS in environment variables before starting
cors_origins_env = os.getenv('CORS_ORIGINS', '*')
cors_origins = cors_origins_env.split(',') if cors_origins_env != '*' else ['*']

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Import and include routers after app_state is defined to avoid circular import
from .routes import query_router
app.include_router(query_router)


# Error handlers
@app.exception_handler(Exception)
async def general_exception_handler(request, exc: Exception):
    """
    General exception handler for unhandled exceptions.
    
    Note: In production, avoid exposing internal error details to clients.
    Log full details server-side but return generic error messages.
    """
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    # In production, don't expose internal error details
    # Return generic error message to prevent information leakage
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="Internal server error",
            detail=None,  # Don't expose internal error details in production
            timestamp=datetime.now().isoformat()
        ).model_dump()
    )

