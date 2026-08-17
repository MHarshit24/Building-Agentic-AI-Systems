"""
Main Entry Point
Starts the FastAPI application server for Personal Diet Counselling Assistant.
"""

import os
import uvicorn
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Start the FastAPI application server."""
    # Get configuration from environment variables
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))
    reload = os.getenv("API_RELOAD", "false").lower() == "true"
    log_level = os.getenv("API_LOG_LEVEL", "info")
    
    logger.info("Starting Personal Diet Counselling Assistant API server...")
    logger.info(f"Configuration: host={host}, port={port}, reload={reload}")
    
    uvicorn.run(
        "main.app:app",
        host=host,
        port=port,
        reload=reload,
        log_level=log_level
    )


if __name__ == "__main__":
    main()

