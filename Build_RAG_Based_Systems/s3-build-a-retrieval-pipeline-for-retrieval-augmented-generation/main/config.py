"""
Configuration and logging setup for the RAG query pipeline.
"""

import os
import logging
import sys
from typing import Dict, Any
from dotenv import load_dotenv
from pathlib import Path
from urllib.parse import quote_plus


def setup_logging(level: int = logging.INFO):
    """
    Configure application logging to stdout.

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


# Initialize logging and create module logger
setup_logging()
logger = logging.getLogger(__name__)


def load_config() -> Dict[str, Any]:
    """Load configuration from environment variables."""
    logger.debug("Loading configuration from environment variables")

    # Load root .env first (contains DB_PASSWORD,
    # AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY)
    BASE_DIR = Path(__file__).resolve().parents[3]
    base_env_path = BASE_DIR / ".env"

    if base_env_path.exists():
        load_dotenv(dotenv_path=base_env_path)
        logger.debug(f"Loaded root .env from {base_env_path}")
    else:
        load_dotenv()
        logger.debug(".env loaded (if present)")

    # Read secrets from root .env
    db_password = os.getenv('DB_PASSWORD')
    azure_endpoint = os.getenv('AZURE_OPENAI_ENDPOINT')
    azure_api_key = os.getenv('AZURE_OPENAI_API_KEY')

    # Load project .env (contains DB_USER, DB_HOST,
    # DB_PORT, DB_NAME, deployment, collection, etc.)
    PROJ_DIR = Path(__file__).resolve().parents[1]
    proj_env_path = PROJ_DIR / ".env"

    if proj_env_path.exists():
        load_dotenv(
            dotenv_path=proj_env_path,
            override=True
        )
        logger.debug(
            f"Loaded project .env from {proj_env_path}"
        )
    else:
        load_dotenv()

    # Build DATABASE_URL from separate variables
    db_user = os.getenv('DB_USER')
    db_host = os.getenv('DB_HOST')
    db_port = os.getenv('DB_PORT')
    db_name = os.getenv('DB_NAME')

    # Validate database connection parameters
    if not all([
        db_user,
        db_password,
        db_host,
        db_port,
        db_name
    ]):
        missing = [
            k for k, v in {
                'DB_USER': db_user,
                'DB_PASSWORD': db_password,
                'DB_HOST': db_host,
                'DB_PORT': db_port,
                'DB_NAME': db_name
            }.items() if not v
        ]

        logger.error(
            f"Missing required database configuration: "
            f"{', '.join(missing)}"
        )

        raise ValueError(
            f"Missing required database configuration: "
            f"{', '.join(missing)}"
        )

    # Handle special characters in password
    encoded_password = (
        quote_plus(db_password)
        if db_password
        else ""
    )

    database_url = (
        f"postgresql+psycopg://"
        f"{db_user}:"
        f"{encoded_password}@"
        f"{db_host}:"
        f"{db_port}/"
        f"{db_name}"
    )

    config = {
        'database_url': database_url,

        'azure_endpoint': azure_endpoint,

        'azure_api_key': azure_api_key,

        'azure_embedding_deployment':
            os.getenv(
                'AZURE_OPENAI_EMBEDDING_DEPLOYMENT'
            )
            or
            os.getenv(
                'AZURE_OPENAI_DEPLOYMENT'
            ),

        'azure_llm_deployment':
            os.getenv(
                'AZURE_OPENAI_LLM_DEPLOYMENT'
            ),

        'api_version':
            os.getenv(
                'AZURE_OPENAI_API_VERSION',
                '2024-02-01'
            ),

        'collection_name':
            os.getenv(
                'COLLECTION_NAME',
                'smart_auto_rag_query'
            ),

        'top_k':
            int(
                os.getenv(
                    'TOP_K',
                    '5'
                )
            ),

        'chunk_size':
            int(
                os.getenv(
                    'CHUNK_SIZE',
                    '1000'
                )
            ),

        'chunk_overlap':
            int(
                os.getenv(
                    'CHUNK_OVERLAP',
                    '200'
                )
            ),

        'cors_origins':
            os.getenv(
                'CORS_ORIGINS',
                '*'
            ).split(',')
            if os.getenv(
                'CORS_ORIGINS'
            )
            else ['*']
    }

    # Validate required configs
    if not config['azure_api_key']:
        logger.error(
            "Missing AZURE_OPENAI_API_KEY"
        )

        raise ValueError(
            "AZURE_OPENAI_API_KEY "
            "not found in environment variables"
        )

    if not config['azure_endpoint']:
        logger.error(
            "Missing AZURE_OPENAI_ENDPOINT"
        )

        raise ValueError(
            "AZURE_OPENAI_ENDPOINT "
            "not found in environment variables"
        )

    if not config['azure_llm_deployment']:
        logger.error(
            "Missing AZURE_OPENAI_LLM_DEPLOYMENT"
        )

        raise ValueError(
            "AZURE_OPENAI_LLM_DEPLOYMENT "
            "not found in environment variables"
        )

    if not config[
        'azure_embedding_deployment'
    ]:
        logger.error(
            "Missing "
            "AZURE_OPENAI_EMBEDDING_DEPLOYMENT"
        )

        raise ValueError(
            "AZURE_OPENAI_EMBEDDING_DEPLOYMENT "
            "not found in environment variables"
        )

    # Validate numeric configs
    if (
        config['top_k'] < 1
        or
        config['top_k'] > 50
    ):
        logger.warning(
            f"top_k={config['top_k']} "
            "outside recommended range"
        )

        config['top_k'] = 5

    if config['chunk_size'] < 100:
        logger.warning(
            f"chunk_size="
            f"{config['chunk_size']} "
            "too small"
        )

        config['chunk_size'] = 100

    logger.info("Configuration loaded")

    logger.debug(
        f"Embedding deployment: "
        f"{config['azure_embedding_deployment']}"
    )

    logger.debug(
        f"LLM deployment: "
        f"{config['azure_llm_deployment']}"
    )

    logger.debug(
        f"Collection: "
        f"{config['collection_name']}"
    )

    logger.debug(
        f"Top-K: "
        f"{config['top_k']}"
    )

    logger.debug(
        f"Chunking: "
        f"size={config['chunk_size']}, "
        f"overlap={config['chunk_overlap']}"
    )

    return config