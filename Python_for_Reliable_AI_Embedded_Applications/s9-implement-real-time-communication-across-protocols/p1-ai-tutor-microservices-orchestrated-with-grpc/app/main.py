"""
AI Tutor API - Personalized Learning with Cloud & Local Models

This project demonstrates a REST API that transforms the console-based AI tutor into a web service.
Combines Gemini (cloud) and Llama 3.1 (local) for explanations with rate limiting protection.
"""

# 1. Import dependencies: FastAPI, Request, HTTPException, CORS middleware, OpenAI, APIError, os, dotenv, rate limiting tools, logging
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI, APIError
import os
import logging
from pathlib import Path
from dotenv import load_dotenv
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Import schemas from schemas module
from .schemas import ConceptRequest, DualExplanationResponse

# Import Orchestrator Agent
from .orchestrator_agent import OrchestratorAgent

# Setup logging configuration
# Configures logging to display timestamp, log level, and message
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 2. Load environment variables from .env file api key, base url, and model name
BASE_DIR = Path(__file__).resolve().parents[4]

env_path = BASE_DIR / ".env"

load_dotenv(dotenv_path=env_path)

api_key = os.getenv("GEMINI_API_KEY")
# Support both naming conventions (GEMINI_BASE_URL is preferred, but older templates use GEMINI_OPENAI_ENDPOINT)
base_url = os.getenv("GEMINI_BASE_URL") or os.getenv("GEMINI_OPENAI_ENDPOINT")
model = os.getenv("GEMINI_MODEL")

if not api_key:
    raise ValueError("GEMINI_API_KEY not found in .env file!")

# 3. Initialize OpenAI client for Gemini API
CLOUD_CLIENT = OpenAI(api_key=api_key, base_url=base_url)
CLOUD_MODEL = model

# 3b. Initialize Orchestrator Agent (Central Coordinator)
orchestrator = OrchestratorAgent(
    prompt_manager_address="localhost:50051",
    ollama_service_address="localhost:50052",
    gemini_client=CLOUD_CLIENT,
    gemini_model=CLOUD_MODEL,
    ollama_model="phi3:mini"
)

logger.info("Orchestrator Agent initialized and ready")

# 4. Setup rate limiter
# Tracks requests per IP address
limiter = Limiter(key_func=get_remote_address)

# 5. Initialize FastAPI application with metadata
app = FastAPI(
    title="AI Tutor API",
    description="AI Tutor with Cloud & Local Models",
    version="3.0.0"
)

# 6. Register rate limiter with app
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# 7. Configure CORS middleware
# This allows browser-based clients from any origin ("*") to access the API
# WARNING: For production, replace ["*"] with specific origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


# 8a. Define Dual-Model Endpoint (Gemini + Ollama)
@app.post(
    "/explain/dual",
    response_model=DualExplanationResponse,
    tags=["Explanations"],
    summary="Get Explanations from Both Gemini and Ollama",
    responses={
        200: {"description": "Successful dual explanation"},
        429: {"description": "Rate limit exceeded"},
        500: {"description": "Internal server error"}
    }
)
@limiter.limit("5/minute")
def get_dual_explanation(request: Request, concept_request: ConceptRequest):
    """
    Get explanations from BOTH Gemini (cloud) and Ollama (local) models.
    
    This endpoint demonstrates hybrid AI architecture:
    - Gemini: Powerful cloud model (paid, high quality)
    - Ollama: Local model (free, privacy-friendly)
    
    Rate Limit: 5 requests per minute per IP address
    
    Args:
        request: FastAPI request object
        concept_request: Request body containing the concept to explain
        
    Returns:
        DualExplanationResponse: Explanations from both models
    """
    logger.info(f"Processing DUAL explanation request for concept: {concept_request.concept}")

    try:
        result = orchestrator.orchestrate_dual_explanation(concept_request.concept)

        # Create response models from dict results
        return DualExplanationResponse(
            concept=concept_request.concept,
            gemini_response=result.get("gemini_response", {}),
            ollama_response=result.get("ollama_response", {}),
        )

    except Exception as e:
        logger.exception("Error processing dual explanation")
        raise HTTPException(status_code=500, detail=str(e))