import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI
from main.routes.routes import router, set_agent_service
from main.services.agent_service import AgentService


def _load_env():
    """
    Load environment variables using the same secret-preservation pattern
    used across this project.

    - Root .env (4 levels up from this file) is loaded first for secrets:
      AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, HF_TOKEN, HF_MCP_URL
    - Project .env (1 level up from this file) is loaded second with
      override=True for deployment names, API server settings, etc.
    - Secrets preserved across the second load so they are never overwritten.
    """
    if "pytest" in sys.modules:
        return

    # Locate root .env (Building_Agentic_AI_Systems/.env)
    # This file: <project>/main/app.py -> parents[3] = root
    base_dir = Path(__file__).resolve().parents[3]
    base_env_path = base_dir / ".env"

    if base_env_path.exists():
        load_dotenv(dotenv_path=base_env_path)
        logging.debug(f"Loaded root .env from {base_env_path}")
    else:
        load_dotenv()
        logging.warning(f"Root .env not found at {base_env_path}, falling back to default load_dotenv()")

    # Preserve secrets before loading project .env
    azure_api_key = os.getenv("AZURE_OPENAI_API_KEY")
    azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    hf_token = os.getenv("HF_TOKEN")
    hf_mcp_url = os.getenv("HF_MCP_URL")

    # Locate project .env (s8 project root/.env)
    # This file: <project>/main/app.py -> parents[1] = project root
    proj_dir = Path(__file__).resolve().parents[1]
    proj_env_path = proj_dir / ".env"

    if proj_env_path.exists():
        load_dotenv(dotenv_path=proj_env_path, override=True)
        logging.debug(f"Loaded project .env from {proj_env_path}")
    else:
        load_dotenv()
        logging.warning(f"Project .env not found at {proj_env_path}, falling back to default load_dotenv()")

    # Restore preserved secrets so project .env cannot overwrite them
    if azure_api_key:
        os.environ["AZURE_OPENAI_API_KEY"] = azure_api_key
    if azure_endpoint:
        os.environ["AZURE_OPENAI_ENDPOINT"] = azure_endpoint
    if hf_token:
        os.environ["HF_TOKEN"] = hf_token
    if hf_mcp_url:
        os.environ["HF_MCP_URL"] = hf_mcp_url


# Load environment variables from .env file
_load_env()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

agent_service = AgentService()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize agent on startup"""
    logger.info("Initializing Product Review Sentiment Analysis Agent...")
    try:
        await agent_service.initialize()
        set_agent_service(agent_service)
        logger.info("✓ Agent ready for product review analysis")
    except Exception as e:
        logger.error(f"✗ Agent init failed: {e}")
    yield
    logger.info("Shutting down...")


app = FastAPI(
    title="Product Review Sentiment Analysis API",
    description="MCP-powered sentiment analysis for product reviews using Hugging Face models",
    version="1.0.0",
    lifespan=lifespan
)

app.include_router(router)


@app.get("/")
async def root():
    return {
        "service": "Product Review Sentiment Analysis",
        "status": "running",
        "endpoints": {
            "analyze": "/api/reviews/analyze",
            "docs": "/docs"
        }
    }