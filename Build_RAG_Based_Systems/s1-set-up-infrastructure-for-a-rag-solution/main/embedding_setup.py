"""
RAG infrastructure setup: PostgreSQL/PgVector checks, Azure OpenAI embeddings,
PGVector store initialization, sample CRUD operations, and similarity search.
"""

import sys
import logging
import psycopg2
from pathlib import Path

# Add project root to Python path to allow imports when running script directly
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from langchain_core.documents import Document
from langchain_postgres import PGVector
from langchain_openai import AzureOpenAIEmbeddings

from main.sample_data import SAMPLE_DOCUMENTS
from main.config import setup_logging, load_config
from main.services.vectorstore_service import VectorstoreService

logger = logging.getLogger(__name__)

# --------------------------
# Utilities
# --------------------------

def normalize_db_url(database_url: str) -> str:
    """Convert SQLAlchemy-style DB URL to psycopg2 compatible URL."""
    return (
        database_url.replace("postgresql+psycopg2://", "postgresql://")
        .replace("postgresql+psycopg://", "postgresql://")
    )


# --------------------------
# Step 1: Database and PgVector check
# --------------------------

def check_database_connection(database_url: str):
    """Test DB connection and ensure PgVector extension exists."""
    logger.info("=" * 80)
    logger.info("TESTING DATABASE CONNECTION")
    logger.info("=" * 80)

    try:
        conn = psycopg2.connect(normalize_db_url(database_url))
        with conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT version();")
                logger.info(f"PostgreSQL version: {cursor.fetchone()[0].split(',')[0]}")

                cursor.execute("SELECT * FROM pg_extension WHERE extname = 'vector';")
                if cursor.fetchone():
                    logger.info("PgVector extension already enabled ✅")
                else:
                    logger.warning("PgVector not found, enabling...")
                    cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                    logger.info("PgVector extension enabled successfully ✅")

        return True
    except Exception as e:
        logger.error(f"Database test failed ❌: {e}")
        return False


# --------------------------
# Step 2: Initialize embeddings (standalone function)
# --------------------------

def initialize_embeddings(config: dict):
    """
    Initialize Azure OpenAI embeddings from config.

    Args:
        config: Configuration dictionary containing Azure OpenAI credentials

    Returns:
        AzureOpenAIEmbeddings instance
    """
    logger.info("=" * 80)
    logger.info("INITIALIZING AZURE OPENAI EMBEDDINGS")
    logger.info("=" * 80)

    # Validate required deployment config
    if not config.get("azure_embedding_deployment"):
        raise ValueError("Missing Azure embedding deployment in configuration")

    try:
        embeddings = AzureOpenAIEmbeddings(
            azure_endpoint=config["azure_endpoint"],
            azure_deployment=config["azure_embedding_deployment"],
            api_key=config["azure_api_key"],
            api_version=config["api_version"],
        )
        logger.info("Azure OpenAI embeddings initialized successfully ✅")
        return embeddings
    except Exception as e:
        logger.error(f"Failed to initialize embeddings: {e}")
        raise


# --------------------------
# Step 3: Create vectorstore (standalone function)
# --------------------------

def create_vectorstore(config: dict, embeddings):
    """
    Create a PGVector vectorstore.

    Args:
        config: Configuration dictionary containing database and collection info
        embeddings: Initialized embeddings object

    Returns:
        PGVector instance or None on failure
    """
    logger.info("=" * 80)
    logger.info("CREATING PGVECTOR STORE")
    logger.info("=" * 80)

    try:
        vectorstore = PGVector(
            embeddings=embeddings,
            collection_name=config["collection_name"],
            connection=config["database_url"],
        )
        logger.info("PGVector store created successfully ✅")
        return vectorstore
    except Exception as e:
        logger.error(f"Failed to create vectorstore: {e}")
        return None


# --------------------------
# Step 4a: Insert sample data (standalone function used by tests)
# --------------------------

def insert_sample_data(vectorstore, sample_sentences: list) -> list:
    """
    Convert plain text sentences into LangChain Documents and insert them.

    Args:
        vectorstore: PGVector store instance
        sample_sentences: List of plain text strings

    Returns:
        List of inserted document IDs, or empty list on failure
    """
    logger.info("=" * 80)
    logger.info("INSERTING SAMPLE DATA")
    logger.info("=" * 80)

    try:
        documents = [
            Document(
                page_content=sentence,
                metadata={
                    "document": "Sample Data",
                    "section": "General",
                    "page": 1,
                    "id": f"doc_{i + 1}",
                }
            )
            for i, sentence in enumerate(sample_sentences)
        ]

        document_ids = vectorstore.add_documents(documents)
        logger.info(f"Successfully inserted {len(document_ids)} documents ✅")
        return document_ids
    except Exception as e:
        logger.error(f"Failed to insert sample data: {e}")
        return []


# --------------------------
# Step 4b: CRUD — create (uses pre-built Document objects)
# --------------------------

def insert_sample_documents(service, documents):
    """
    Insert pre-created LangChain Document objects into the vectorstore.
    
    Args:
        service: The VectorstoreService instance
        documents: List of Document objects to insert
        
    Returns:
        List of inserted document IDs
    """
    logger.info("=" * 80)
    logger.info("INSERTING SAMPLE DOCUMENTS")
    logger.info("=" * 80)

    # TODO: Check if documents list is empty
    # If empty, log a warning and return empty list
    if not documents:
        logger.warning("No documents provided to insert")
        return []

    try:
        # TODO: Call service.add_documents() method with the documents list
        result = service.add_documents(documents)
        
        # TODO: Get the list of document IDs from the result
        document_ids = result
        
        # TODO: Log success message with number of documents inserted
        logger.info(f"Successfully inserted {len(document_ids)} documents ✅")
        
        # TODO: Log each document with its ID and document name from metadata
        for doc_id, doc in zip(document_ids, documents):
            logger.info(f"  ID: {doc_id} | Document: {doc.metadata.get('document', 'N/A')}")
        
        # TODO: Return the list of document IDs
        return document_ids
    except Exception as e:
        # TODO: Add exception handling here
        # Log error appropriately
        # Return empty list on failure
        logger.error(f"Failed to insert sample documents: {e}")
        return []


# --------------------------
# Step 5a: Read all embeddings from DB
# --------------------------

def read_all_embeddings(config: dict) -> list:
    """
    Read all stored embeddings from the database.

    Args:
        config: Configuration dictionary containing database info

    Returns:
        List of tuples (id, document, cmetadata) or empty list on failure
    """
    logger.info("=" * 80)
    logger.info("READING ALL EMBEDDINGS FROM DATABASE")
    logger.info("=" * 80)

    try:
        conn = psycopg2.connect(normalize_db_url(config["database_url"]))
        with conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT e.id, e.document, e.cmetadata
                    FROM langchain_pg_embedding e
                    JOIN langchain_pg_collection c ON e.collection_id = c.uuid
                    WHERE c.name = %s
                    """,
                    (config["collection_name"],),
                )
                rows = cursor.fetchall()
                logger.info(f"Retrieved {len(rows)} embeddings from database ✅")
                return rows
    except Exception as e:
        logger.error(f"Failed to read embeddings: {e}")
        return []


# --------------------------
# Step 5b: Similarity search
# --------------------------

def perform_similarity_search(vectorstore, query_text: str, top_k: int = 3, return_result: bool = False):
    """
    Perform similarity search with scores for detailed logging.
    Can optionally return the best result.
    
    Args:
        vectorstore: The vectorstore instance
        query_text: The search query
        top_k: Number of results to return
        return_result: If True, returns the best result as a dict. If False, only logs results.
        
    Returns:
        dict or None: If return_result=True, returns the best matching document with content and metadata.
                     Otherwise returns None (only logs results).
    """
    logger.info("=" * 80)
    logger.info(f"SIMILARITY SEARCH FOR: {query_text}")
    logger.info("=" * 80)

    try:
        # TODO: Perform similarity search with scores using service.vectorstore.similarity_search_with_score()
        # Pass query_text and top_k (k parameter)
        results = vectorstore.similarity_search_with_score(query_text, k=top_k)

        # TODO: Check if results are empty
        # If empty, log a warning and return None
        if not results:
            logger.warning("No results found for the query")
            return None

        # TODO: Iterate through results and log each result
        # For each result, calculate similarity score (1 / (1 + distance))
        # Log rank, distance, similarity, content, and metadata
        for rank, (doc, distance) in enumerate(results, start=1):
            similarity = 1 / (1 + distance)
            logger.info(f"Rank {rank}: distance={distance:.4f}, similarity={similarity:.4f}")
            logger.info(f"  Content: {doc.page_content[:100]}...")
            logger.info(f"  Metadata: {doc.metadata}")

        # TODO: If return_result is True and results exist, return the best result
        # Extract the best document (first result) and return as dict with "content" and "metadata" keys
        # Log that you're returning the best result
        if return_result and results:
            best_doc, _ = results[0]
            logger.info("Returning best result")
            return {"content": best_doc.page_content, "metadata": best_doc.metadata}

        # TODO: Return None if return_result is False
        return None

    except Exception as e:
        # TODO: Add exception handling here
        # Log error appropriately
        # Return None on failure
        logger.error(f"Similarity search failed: {e}")
        return None


# --------------------------
# Step 2-3: Initialize vectorstore service (using VectorstoreService)
# --------------------------

def initialize_vectorstore_service():
    """Initialize the vectorstore service."""
    logger.info("=" * 80)
    logger.info("INITIALIZING VECTORSTORE SERVICE")
    logger.info("=" * 80)
    
    try:
        # TODO: Create an instance of VectorstoreService
        service = VectorstoreService()
        
        # TODO: Return the service instance
        return service
    except Exception as e:
        # TODO: Add exception handling here
        # Log error appropriately
        # Re-raise the exception
        logger.error(f"Failed to initialize vectorstore service: {e}")
        raise


# --------------------------
# Main execution flow
# --------------------------

def main():
    setup_logging()
    config = load_config()

    if not check_database_connection(config["database_url"]):
        return

    # Initialize vectorstore service (handles embeddings and vectorstore initialization)
    service = initialize_vectorstore_service()

    # Insert pre-created LangChain Document objects related to Smart Auto Advisor
    insert_sample_documents(service, SAMPLE_DOCUMENTS)
    
    # Test similarity search
    perform_similarity_search(service.vectorstore, "What are the features and pricing of the EcoSport Hybrid?")


if __name__ == "__main__":
    main()