"""
RAG Service Module
Provides shared services for API and CLI usage.

This module:
- Initializes Azure OpenAI configuration
- Manages vector index and query engine instances
- Provides singleton access to RAG components
"""

import os
import logging
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from urllib.parse import quote_plus
from llama_index.core import Settings, VectorStoreIndex, StorageContext
from llama_index.llms.azure_openai import AzureOpenAI
from llama_index.embeddings.azure_openai import AzureOpenAIEmbedding
from llama_index.vector_stores.postgres import PGVectorStore
from main.service.query_engine import create_query_engine as create_qe
from main.service.semantic_chunking import create_semantic_splitter, generate_nodes_from_documents

logger = logging.getLogger(__name__)

# Global instances
_index: Optional[VectorStoreIndex] = None
_llm = None
_embed_model = None


def initialize_services():
    """Initialize all services (LLM, embeddings, index)."""
    global _index, _llm, _embed_model

    if _index is not None:
        logger.info("Services already initialized, reusing existing instances")
        return

    # Load root .env first (contains DB_PASSWORD, AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT)
    # Walk up from this file's location to find the root .env
    # File is at: <project>/main/service/rag_service.py — root is 4 levels up
    base_dir = Path(__file__).resolve().parents[4]
    base_env_path = base_dir / ".env"

    if base_env_path.exists():
        load_dotenv(dotenv_path=base_env_path)
        logger.debug(f"Loaded root .env from {base_env_path}")
    else:
        load_dotenv()
        logger.warning(f"Root .env not found at {base_env_path}")

    # Preserve secret values before loading project .env
    db_password = os.getenv("DB_PASSWORD")
    azure_api_key = os.getenv("AZURE_OPENAI_API_KEY")
    azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")

    # Load project .env (contains DB_USER, DB_HOST, DB_PORT, DB_NAME, DB_TABLE_NAME,
    # AZURE_OPENAI_EMBEDDING_DEPLOYMENT, AZURE_OPENAI_LLM_DEPLOYMENT, AZURE_OPENAI_API_VERSION)
    # Project root is 2 levels up from this file: <project>/
    proj_dir = Path(__file__).resolve().parents[2]
    proj_env_path = proj_dir / ".env"

    if proj_env_path.exists():
        load_dotenv(dotenv_path=proj_env_path, override=True)
        logger.debug(f"Loaded project .env from {proj_env_path}")
    else:
        load_dotenv()
        logger.warning(f"Project .env not found at {proj_env_path}")

    # Restore preserved secrets
    if db_password:
        os.environ["DB_PASSWORD"] = db_password

    if azure_api_key:
        os.environ["AZURE_OPENAI_API_KEY"] = azure_api_key

    if azure_endpoint:
        os.environ["AZURE_OPENAI_ENDPOINT"] = azure_endpoint

    # Remove conflicting PostgreSQL variables from shared root .env
    conflicting_pg_vars = [
        "DATABASE_URL",
        "POSTGRES_URL",
        "PGHOST",
        "PGPORT",
        "PGUSER",
        "PGPASSWORD",
        "PGDATABASE"
    ]

    for var in conflicting_pg_vars:
        os.environ.pop(var, None)

    # Validate required environment variables
    required_vars = [
        'AZURE_OPENAI_ENDPOINT',
        'AZURE_OPENAI_API_KEY',
        'AZURE_OPENAI_LLM_DEPLOYMENT',
        'AZURE_OPENAI_EMBEDDING_DEPLOYMENT',
        'DB_USER',
        'DB_PASSWORD',
        'DB_HOST',
        'DB_PORT',
        'DB_NAME',
        'DB_TABLE_NAME'
    ]

    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        error_msg = (
            f"Missing required environment variables: "
            f"{', '.join(missing_vars)}"
        )
        logger.error(error_msg)
        raise ValueError(error_msg)

    logger.info("✓ Environment variables validated")

    # Configure Azure OpenAI
    logger.info("Initializing Azure OpenAI services...")

    try:

        # Get environment variables with validation
        llm_deployment = os.getenv(
            'AZURE_OPENAI_LLM_DEPLOYMENT'
        )

        llm_api_key = os.getenv(
            'AZURE_OPENAI_API_KEY'
        )

        llm_endpoint = os.getenv(
            'AZURE_OPENAI_ENDPOINT'
        )

        if not all([
            llm_deployment,
            llm_api_key,
            llm_endpoint
        ]):
            raise ValueError(
                "Missing required Azure OpenAI LLM configuration"
            )

        # TODO: Initialize Azure OpenAI LLM
        # HINT: Create an AzureOpenAI instance and assign it to _llm
        # HINT: Required parameters:
        #   - model: Get from 'AZURE_OPENAI_LLM_MODEL' env var (default: 'gpt-4o-mini')
        #   - deployment_name: Use llm_deployment variable
        #   - api_key: Use llm_api_key variable
        #   - azure_endpoint: Use llm_endpoint variable
        #   - api_version: Get from 'AZURE_OPENAI_API_VERSION' env var (default: '2024-02-15-preview')
        # Your code here:

        _llm = AzureOpenAI(
            model=os.getenv(
                'AZURE_OPENAI_LLM_MODEL',
                'gpt-4o-mini'
            ),
            deployment_name=llm_deployment,
            api_key=llm_api_key,
            azure_endpoint=llm_endpoint,
            api_version=os.getenv(
                'AZURE_OPENAI_API_VERSION',
                '2024-02-15-preview'
            )
        )

        # TODO: Get embedding deployment name from environment variable
        # HINT: Use os.getenv('AZURE_OPENAI_EMBEDDING_DEPLOYMENT')
        # Your code here:

        embed_deployment = os.getenv(
            'AZURE_OPENAI_EMBEDDING_DEPLOYMENT'
        )

        # TODO: Validate embedding configuration
        # HINT: Check if embed_deployment, llm_api_key, and llm_endpoint are all present
        # HINT: Raise ValueError if any are missing with message "Missing required Azure OpenAI Embedding configuration"
        # Your code here:

        if not all([
            embed_deployment,
            llm_api_key,
            llm_endpoint
        ]):
            raise ValueError(
                "Missing required Azure OpenAI Embedding configuration"
            )

        # TODO: Initialize Azure OpenAI Embedding model
        # HINT: Create an AzureOpenAIEmbedding instance and assign it to _embed_model
        # HINT: Required parameters:
        #   - model: Get from 'AZURE_OPENAI_EMBEDDING_MODEL' env var (default: 'text-embedding-3-small')
        #   - deployment_name: Use embed_deployment variable
        #   - api_key: Use llm_api_key variable
        #   - azure_endpoint: Use llm_endpoint variable
        #   - api_version: Get from 'AZURE_OPENAI_API_VERSION' env var (default: '2024-02-15-preview')
        # Your code here:

        _embed_model = AzureOpenAIEmbedding(
            model=os.getenv(
                'AZURE_OPENAI_EMBEDDING_MODEL',
                'text-embedding-3-small'
            ),
            deployment_name=embed_deployment,
            api_key=llm_api_key,
            azure_endpoint=llm_endpoint,
            api_version=os.getenv(
                'AZURE_OPENAI_API_VERSION',
                '2024-02-15-preview'
            )
        )

        # Verify objects were created successfully
        if _llm is None:
            raise ValueError(
                "Failed to create LLM instance - AzureOpenAI returned None"
            )

        if _embed_model is None:
            raise ValueError(
                "Failed to create Embedding instance - AzureOpenAIEmbedding returned None"
            )

        logger.debug(
            f"Created LLM instance: {type(_llm).__name__}"
        )

        logger.debug(
            f"Created Embedding instance: {type(_embed_model).__name__}"
        )

        # TODO: Assign LLM and Embedding models to LlamaIndex Settings
        # HINT: Use Settings.llm and Settings.embed_model to assign the models globally
        # HINT: Wrap in try-except to handle any potential errors gracefully
        # HINT: If assignment fails, it's non-critical - log a warning and continue
        # Your code here:

        try:
            Settings.llm = _llm
            Settings.embed_model = _embed_model

        except Exception as settings_err:
            logger.warning(
                f"Could not assign models to Settings "
                f"(non-critical): {settings_err}"
            )

        logger.info(
            f"✓ LLM configured: "
            f"{os.getenv('AZURE_OPENAI_LLM_MODEL','gpt-4o-mini')}"
        )

        logger.info(
            f"✓ Embedding model configured: "
            f"{os.getenv('AZURE_OPENAI_EMBEDDING_MODEL','text-embedding-3-small')}"
        )

    except ValueError as ve:
        logger.error(f"Configuration error: {ve}")
        raise

    except Exception as e:
        logger.error(
            f"Failed to initialize Azure OpenAI services: {e}",
            exc_info=True
        )

        raise ValueError(
            f"Azure OpenAI initialization failed: {e}"
        ) from e

    # Load or create index
    _index = load_or_create_index(_embed_model)

    logger.info("✓ All services initialized successfully")


def load_or_create_index(embed_model) -> VectorStoreIndex:
    """Load existing index from PostgreSQL or create a new one."""
    logger.info("Loading or creating vector index...")

    # TODO: Initialize PGVector store
    # HINT: Use PGVectorStore.from_params() to create the vector store
    # HINT: Required parameters from environment variables:
    #   - database: DB_NAME
    #   - host: DB_HOST
    #   - password: DB_PASSWORD
    #   - port: DB_PORT
    #   - user: DB_USER
    #   - table_name: DB_TABLE_NAME
    #   - embed_dim: 1536 (dimension for text-embedding-3-small)
    # Your code here:

    vector_store = PGVectorStore.from_params(
        database=os.getenv('DB_NAME'),
        host=os.getenv('DB_HOST'),
        password=quote_plus(os.getenv('DB_PASSWORD', '')),
        port=os.getenv('DB_PORT'),
        user=os.getenv('DB_USER'),
        table_name=os.getenv('DB_TABLE_NAME'),
        embed_dim=1536
    )

    # TODO: Create StorageContext from the vector store
    # HINT: Use StorageContext.from_defaults() and pass the vector_store
    # Your code here:

    storage_context = StorageContext.from_defaults(
        vector_store=vector_store
    )

    # TODO: Try to load existing index from PostgreSQL, or create a new empty one
    # HINT: Use try-except block
    # HINT: In try block: Use VectorStoreIndex.from_vector_store() with vector_store and embed_model
    # HINT: In except block: Create new VectorStoreIndex with empty nodes=[], storage_context, and embed_model
    # Your code here:

    try:

        index = VectorStoreIndex.from_vector_store(
            vector_store=vector_store,
            embed_model=embed_model
        )

        logger.info(
            "✓ Loaded existing index from PostgreSQL"
        )

    except Exception as e:

        logger.info(
            f"No existing index found ({e}), "
            f"creating new empty index..."
        )

        index = VectorStoreIndex(
            nodes=[],
            storage_context=storage_context,
            embed_model=embed_model
        )

        logger.info(
            "✓ Created new empty index"
        )

    return index


def get_index() -> VectorStoreIndex:
    """Get the vector index instance."""
    if _index is None:
        initialize_services()

    return _index


def get_query_engine(similarity_top_k: int = 2, filters=None):

    """
    Get a fresh query engine instance with specified similarity_top_k.

    Always creates a new query engine to ensure it uses the most up-to-date index.

    Args:
        similarity_top_k: Number of top similar nodes to retrieve
        filters: Optional MetadataFilters object for diet-specific filtering

    Returns:
        QueryEngine instance (freshly created)
    """

    if _index is None:
        initialize_services()

    # Always create fresh query engine - no caching
    return create_qe(
        _index,
        _llm,
        similarity_top_k=similarity_top_k,
        filters=filters
    )


def get_embed_model():
    """Get the embedding model instance."""
    if _embed_model is None:
        initialize_services()

    return _embed_model


def get_llm():
    """Get the LLM instance."""
    if _llm is None:
        initialize_services()

    return _llm


def add_documents_to_index(documents):

    """
    Add new documents to the existing index using semantic chunking.

    Args:
        documents: List of Document objects to add

    Returns:
        dict: Result message with number of documents indexed
    """

    global _index

    if _index is None:
        initialize_services()

    logger.info(
        f"Adding {len(documents)} document(s) "
        f"to index with semantic chunking..."
    )

    # TODO: Implement document indexing with semantic chunking
    # HINT: Steps to complete:
    #   1. Get embedding model using get_embed_model()
    #   2. Create semantic splitter using create_semantic_splitter(embed_model)
    #   3. Generate nodes using generate_nodes_from_documents(semantic_splitter, documents)
    #   4. Loop through nodes and insert each one using _index.insert(node)
    # HINT: Use try-except to handle insertion errors
    # HINT: Return a dictionary with success message: {"message": "Successfully indexed X document(s)"}
    # Your code here:

    embed_model = get_embed_model()

    semantic_splitter = create_semantic_splitter(
        embed_model
    )

    nodes = generate_nodes_from_documents(
        semantic_splitter,
        documents
    )

    logger.info(
        f"Generated {len(nodes)} node(s) "
        f"from {len(documents)} document(s)"
    )

    inserted_nodes = 0

    for node in nodes:

        try:

            _index.insert(node)
            inserted_nodes += 1

        except Exception as e:

            logger.error(
                f"Error inserting node: {e}",
                exc_info=True
            )

    if inserted_nodes == 0:

        raise RuntimeError(
            "Failed to insert any nodes into PostgreSQL"
        )

    return {
        "message":
        f"Successfully indexed {len(documents)} document(s)"
    }