"""
AutoMind Motors 

Centralized configuration and logging setup for the RAG ingestion pipeline.
"""

import os
import logging
import sys
from typing import Dict, Any
from pathlib import Path
from dotenv import load_dotenv
from urllib.parse import quote_plus


def setup_logging(level: int = logging.INFO):
    """
    Configure logging for the application (console only)
    
    Args:
        level: Logging level (default: INFO)
    """
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ],
        force=True  # Override any existing configuration
    )
    
    # Suppress noisy loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("watchfiles").setLevel(logging.WARNING)
    logging.getLogger("watchfiles.main").setLevel(logging.WARNING)


# Initialize logging and create logger instance
setup_logging()
logger = logging.getLogger(__name__)


def load_config() -> Dict[str, Any]:
    """Load configuration from environment variables"""
    logger = logging.getLogger(__name__)
    
    # TODO: Log that configuration loading is starting
    logger.info("Loading application configuration...")
    
    # TODO: Load environment variables from .env file using load_dotenv()
    BASE_DIR = Path(__file__).resolve().parents[3]

    base_env_path = BASE_DIR / ".env"

    if base_env_path.exists():
        load_dotenv(dotenv_path=base_env_path)
    else:
        load_dotenv()
    
    # TODO: Get database configuration from environment variables
    # Get DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME
    db_password = os.getenv("DB_PASSWORD")
    PROJ_DIR = Path(__file__).resolve().parents[1]
    proj_env_path = PROJ_DIR / ".env"

    if proj_env_path.exists():
        load_dotenv(dotenv_path=proj_env_path, override=True)
    else:
        load_dotenv()
    db_user = os.getenv("DB_USER")
    db_host = os.getenv("DB_HOST")
    db_port = os.getenv("DB_PORT")
    db_name = os.getenv("DB_NAME")
    
    # Handle special characters in password
    encoded_password = quote_plus(db_password) if db_password else ""
    
    # TODO: Build database_url string in format: postgresql+psycopg://{user}:{password}@{host}:{port}/{db_name}
    database_url = (
        f"postgresql+psycopg://{db_user}:{encoded_password}@{db_host}:{db_port}/{db_name}"
    )
    
    # TODO: Get Azure OpenAI configuration from environment variables
    # Get AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, AZURE_OPENAI_DEPLOYMENT, AZURE_OPENAI_API_VERSION, COLLECTION_NAME
    azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    azure_api_key = os.getenv("AZURE_OPENAI_API_KEY")
    azure_embedding_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")
    api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01")
    collection_name = os.getenv("COLLECTION_NAME", "automind_embedding")
    
    # TODO: Build config dictionary with the following keys:
    # - database_url
    # - azure_endpoint
    # - azure_api_key
    # - azure_embedding_deployment
    # - api_version (with default value '2024-02-01')
    # - collection_name (with default value 'automind_embedding')
    
    config = {
        "database_url": database_url,
        "azure_endpoint": azure_endpoint,
        "azure_api_key": azure_api_key,
        "azure_embedding_deployment": azure_embedding_deployment,
        "api_version": api_version,
        "collection_name": collection_name,
    }
    
    # TODO: Validate required configuration variables
    # Check that azure_api_key, azure_endpoint, and azure_embedding_deployment are not None/empty
    # If any are missing, log an error and raise ValueError with appropriate message
    
    required_vars = {
        "AZURE_OPENAI_API_KEY": azure_api_key,
        "AZURE_OPENAI_ENDPOINT": azure_endpoint,
        "AZURE_OPENAI_DEPLOYMENT": azure_embedding_deployment,
    }
    
    missing_vars = [key for key, value in required_vars.items() if not value]
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {missing_vars}")
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing_vars)}"
        )
    
    # TODO: Log successful configuration load with key details
    # Log embedding deployment, endpoint, database info, and collection name
    
    logger.info("Configuration loaded successfully")
    logger.info(f"Embedding deployment: {azure_embedding_deployment}")
    logger.info(f"Azure endpoint: {azure_endpoint}")
    logger.info(f"Database: {db_name} on {db_host}:{db_port}")
    logger.info(f"Collection name: {collection_name}")
    
    # TODO: Return the config dictionary
    return config