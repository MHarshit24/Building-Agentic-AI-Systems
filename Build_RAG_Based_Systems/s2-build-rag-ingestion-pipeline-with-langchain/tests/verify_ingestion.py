"""
Verification script to test the RAG ingestion pipeline.
Performs a test query to ensure embeddings are stored and retrievable.
"""

import os
import sys
import logging
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from langchain_openai import AzureOpenAIEmbeddings
from langchain_postgres import PGVector
import psycopg2
from psycopg2.extras import RealDictCursor

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database configuration from separate environment variables
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME")

# Build DATABASE_URL for PGVector
DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Azure OpenAI configuration
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2023-05-15")

# Collection name (same as S1 and S2 ingestion)
COLLECTION_NAME = "automind_embedding"


def connect_to_database():
    """Establish connection to PostgreSQL database."""
    try:
        # Validate required environment variables
        if not all([DB_USER, DB_PASSWORD, DB_HOST, DB_NAME]):
            missing = []
            if not DB_USER:
                missing.append("DB_USER")
            if not DB_PASSWORD:
                missing.append("DB_PASSWORD")
            if not DB_HOST:
                missing.append("DB_HOST")
            if not DB_NAME:
                missing.append("DB_NAME")
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
        
        connection = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        return connection
        
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        raise


def get_database_stats(connection):
    """Get statistics about stored embeddings."""
    cursor = connection.cursor(cursor_factory=RealDictCursor)
    
    # Count total embeddings from LangChain PGVector tables
    cursor.execute("""
        SELECT COUNT(*) as total 
        FROM langchain_pg_embedding
        WHERE collection_id = (
            SELECT uuid FROM langchain_pg_collection 
            WHERE name = %s
        )
    """, (COLLECTION_NAME,))
    total = cursor.fetchone()['total']
    
    # Get unique sources from metadata
    cursor.execute("""
        SELECT cmetadata->>'source' as source, COUNT(*) as count
        FROM langchain_pg_embedding
        WHERE collection_id = (
            SELECT uuid FROM langchain_pg_collection 
            WHERE name = %s
        )
        GROUP BY cmetadata->>'source'
    """, (COLLECTION_NAME,))
    sources = cursor.fetchall()
    
    cursor.close()
    
    return total, sources


def similarity_search_using_vectorstore(query: str, top_k: int = 5):
    """Perform similarity search using PGVector vectorstore."""
    logger.info(f"Query: '{query}'")
    logger.info("-" * 60)
    
    try:
        missing = []
        if not AZURE_OPENAI_ENDPOINT:
            missing.append("AZURE_OPENAI_ENDPOINT")
        if not AZURE_OPENAI_API_KEY:
            missing.append("AZURE_OPENAI_API_KEY")
        if not AZURE_OPENAI_DEPLOYMENT:
            missing.append("AZURE_OPENAI_DEPLOYMENT")

        if missing:
            raise ValueError(
                "Missing required Azure OpenAI environment variables: "
                + ", ".join(missing)
            )

        # Initialize embeddings
        embeddings = AzureOpenAIEmbeddings(
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            azure_deployment=AZURE_OPENAI_DEPLOYMENT,
            api_key=AZURE_OPENAI_API_KEY,
            api_version=AZURE_OPENAI_API_VERSION,
        )
        
        # Initialize vectorstore
        vectorstore = PGVector(
            embeddings=embeddings,
            collection_name=COLLECTION_NAME,
            connection=DATABASE_URL,
        )
        
        # Perform similarity search with scores
        results = vectorstore.similarity_search_with_score(query, k=top_k)
        
        # Format results
        formatted_results = []
        for doc, score in results:
            formatted_results.append({
                'document': doc.page_content,
                'metadata': doc.metadata,
                'similarity': 1 / (1 + score)  # Convert distance to similarity
            })
        
        return formatted_results
    except Exception as e:
        logger.error(f"Search failed: {e}")
        return []


def display_results(results):
    """Display search results in a formatted way."""
    if not results:
        logger.info("No results found.")
        return
    
    for i, result in enumerate(results, 1):
        logger.info(f"Result {i}:")
        logger.info(f"   Similarity: {result['similarity']:.4f}")
        logger.info(f"   Source: {result['metadata'].get('source', 'unknown')}")
        if result['metadata'].get('page') is not None:
            logger.info(f"   Page: {result['metadata']['page']}")
        logger.info(f"   Text Preview: {result['document'][:200]}...")
        logger.info("-" * 60)


def main():
    """Main verification function."""
    logger.info("=" * 60)
    logger.info("AutoMind Motors - Ingestion Verification")
    logger.info("=" * 60)
    
    try:
        # Connect to database
        logger.info("Connecting to database...")
        connection = connect_to_database()
        logger.info("Connected successfully")
        
        # Get database statistics
        logger.info("Database Statistics:")
        total, sources = get_database_stats(connection)
        logger.info(f"   Total embeddings: {total}")
        logger.info("   Sources:")
        for source in sources:
            logger.info(f"     - {source['source']}: {source['count']} chunks")
        
        # Test queries
        test_queries = [
            "What are the safety procedures before engine disassembly?",
            "How do we calibrate the engine sensor?",
            "What is the maintenance schedule for the vehicle?",
        ]
        
        logger.info("=" * 60)
        logger.info("Running Test Queries")
        logger.info("=" * 60)
        
        for query in test_queries:
            results = similarity_search_using_vectorstore(query, top_k=3)
            display_results(results)
        
        logger.info("=" * 60)
        logger.info("Verification completed successfully!")
        logger.info("=" * 60)
        
        connection.close()
        
    except Exception as e:
        logger.error(f"Verification failed: {e}")
        raise


if __name__ == "__main__":
    main()
