"""Entry point for Personal Diet Counselling Assistant API server."""
import uvicorn
from dotenv import load_dotenv
import logging
import os

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=os.getenv("API_LOG_LEVEL", "info").upper(),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def main():
    """Entry point for running the application."""
    logger.info("Starting Personal Diet Counselling Assistant API server...")
    
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))
    reload = os.getenv("API_RELOAD", "false").lower() == "true"
    
    logger.info(f"Server configuration: host={host}, port={port}, reload={reload}")
    
    uvicorn.run(
        "main.app:app",
        host=host,
        port=port,
        reload=reload,
        log_level=os.getenv("API_LOG_LEVEL", "info").lower()
    )


if __name__ == "__main__":
    main()
