"""
Comprehensive test script for the RAG ingestion pipeline.
Tests each component independently before running the full pipeline.
"""

import os
import sys
import logging
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_environment():
    """Test that all required environment variables are set."""
    logger.info("Testing Environment Variables...")
    
    required_vars = [
        "DB_USER",
        "DB_PASSWORD",
        "DB_HOST",
        "DB_PORT",
        "DB_NAME",
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_DEPLOYMENT",
    ]
    optional_vars = ["AZURE_OPENAI_API_VERSION"]
    missing_vars = []
    
    # Check required variables
    for var in required_vars:
        value = os.getenv(var)
        if value:
            # Mask sensitive values
            if "KEY" in var or "PASSWORD" in var:
                display_value = value[:10] + "..." if len(value) > 10 else "***"
            else:
                display_value = value
            logger.info(f"  {var}: {display_value}")
        else:
            logger.error(f"  {var}: NOT SET")
            missing_vars.append(var)
    
    # Check optional variables
    for var in optional_vars:
        value = os.getenv(var)
        if value:
            logger.info(f"  {var}: {value}")
        else:
            logger.info("  AZURE_OPENAI_API_VERSION: NOT SET (using default: 2023-05-15)")
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        logger.error("   Please create a .env file with the required variables.")
        return False
    
    logger.info("All required environment variables are set")
    return True


def test_database_connection():
    """Test database connectivity."""
    logger.info("Testing Database Connection...")
    
    try:
        import psycopg2
        
        # Get database configuration from environment variables
        DB_USER = os.getenv("DB_USER")
        DB_PASSWORD = os.getenv("DB_PASSWORD")
        DB_HOST = os.getenv("DB_HOST", "localhost")
        DB_PORT = os.getenv("DB_PORT", "5432")
        DB_NAME = os.getenv("DB_NAME")
        
        if not all([DB_USER, DB_PASSWORD, DB_HOST, DB_NAME]):
            raise ValueError("Missing required database environment variables")
        
        connection = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        
        cursor = connection.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        logger.info("  Connected to PostgreSQL")
        logger.info(f"     Version: {version.split(',')[0]}")
        
        # Check for PgVector extension
        cursor.execute("""
            SELECT EXISTS(
                SELECT 1 FROM pg_extension WHERE extname = 'vector'
            );
        """)
        has_pgvector = cursor.fetchone()[0]
        
        if has_pgvector:
            logger.info("  PgVector extension is installed")
        else:
            logger.error("  PgVector extension is NOT installed")
            logger.error("     Run: CREATE EXTENSION vector;")
            cursor.close()
            connection.close()
            return False
        
        # Check for LangChain PGVector tables
        cursor.execute("""
            SELECT EXISTS(
                SELECT 1 FROM information_schema.tables 
                WHERE table_name = 'langchain_pg_collection'
            );
        """)
        has_collection_table = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT EXISTS(
                SELECT 1 FROM information_schema.tables 
                WHERE table_name = 'langchain_pg_embedding'
            );
        """)
        has_embedding_table = cursor.fetchone()[0]
        
        if has_collection_table and has_embedding_table:
            logger.info("  LangChain PGVector tables exist")
            
            # Check for automind_embedding collection
            cursor.execute("""
                SELECT COUNT(*) 
                FROM langchain_pg_collection 
                WHERE name = 'automind_embedding';
            """)
            collection_exists = cursor.fetchone()[0] > 0
            
            if collection_exists:
                # Get embedding count
                cursor.execute("""
                    SELECT COUNT(*) 
                    FROM langchain_pg_embedding 
                    WHERE collection_id = (
                        SELECT uuid FROM langchain_pg_collection 
                        WHERE name = 'automind_embedding'
                    );
                """)
                count = cursor.fetchone()[0]
                logger.info("  Collection 'automind_embedding' exists")
                logger.info(f"     Current embeddings: {count}")
            else:
                logger.info("  Collection 'automind_embedding' not found (will be created on first run)")
        else:
            logger.info("  LangChain PGVector tables not found (will be created automatically)")
        
        cursor.close()
        connection.close()
        logger.info("Database connection test passed")
        return True
        
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False


def test_azure_openai_embeddings():
    """Test Azure OpenAI embeddings connectivity."""
    logger.info("Testing Azure OpenAI Embeddings...")

    try:
        from langchain_openai import AzureOpenAIEmbeddings

        azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        azure_api_key = os.getenv("AZURE_OPENAI_API_KEY")
        azure_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")
        api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2023-05-15")

        embeddings = AzureOpenAIEmbeddings(
            azure_endpoint=azure_endpoint,
            azure_deployment=azure_deployment,
            api_key=azure_api_key,
            api_version=api_version,
        )

        test_text = "This is a test sentence."
        embedding = embeddings.embed_query(test_text)

        logger.info("  Azure OpenAI embeddings are accessible")
        logger.info(f"     Deployment: {azure_deployment}")
        logger.info(f"     Embedding dimension: {len(embedding)}")

        return True

    except Exception as e:
        logger.error(f"Azure OpenAI embeddings test failed: {e}")
        return False


def test_document_files():
    """Test that all required document files exist."""
    logger.info("Testing Document Files...")
    
    documents_dir = "documents"
    required_files = [
        "car_engine_manual.pdf",
        "quality_report.txt",
        "autocare_webpage.html"
    ]
    
    if not os.path.exists(documents_dir):
        logger.error(f"  Documents directory does not exist: {documents_dir}")
        logger.info("     Creating directory...")
        os.makedirs(documents_dir)
        return False
    
    missing_files = []
    for filename in required_files:
        filepath = os.path.join(documents_dir, filename)
        if os.path.exists(filepath):
            size = os.path.getsize(filepath)
            logger.info(f"  {filename} ({size:,} bytes)")
        else:
            logger.error(f"  {filename} NOT FOUND")
            missing_files.append(filename)
    
    if missing_files:
        logger.warning(f"Missing files: {', '.join(missing_files)}")
        if "car_engine_manual.pdf" in missing_files:
            logger.info("   Run: uv run python create_pdf.py")
        return False
    
    logger.info("All document files exist")
    return True


def test_document_loaders():
    """Test that document loaders work correctly."""
    logger.info("Testing Document Loaders...")
    
    try:
        from langchain_community.document_loaders import PyPDFLoader, TextLoader
        
        # Test PDF loader
        pdf_path = "documents/car_engine_manual.pdf"
        if os.path.exists(pdf_path):
            pdf_loader = PyPDFLoader(pdf_path)
            pdf_docs = pdf_loader.load()
            logger.info(f"  PDF Loader: Loaded {len(pdf_docs)} pages")
        
        # Test TXT loader
        txt_path = "documents/quality_report.txt"
        if os.path.exists(txt_path):
            txt_loader = TextLoader(txt_path, encoding='utf-8')
            txt_docs = txt_loader.load()
            logger.info(f"  TXT Loader: Loaded {len(txt_docs)} document(s)")
        
        # Test HTML loader
        html_path = "documents/autocare_webpage.html"
        if os.path.exists(html_path):
            from bs4 import BeautifulSoup
            with open(html_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            soup = BeautifulSoup(html_content, 'html.parser')
            text = soup.get_text()
            logger.info(f"  HTML Loader: Extracted {len(text)} characters")
        
        logger.info("Document loaders test passed")
        return True
        
    except Exception as e:
        logger.error(f"Document loaders test failed: {e}")
        return False


def test_text_splitter():
    """Test text splitting functionality."""
    logger.info("Testing Text Splitter...")
    
    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        from langchain_core.documents import Document
        
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=800,
            chunk_overlap=100,
            length_function=len
        )
        
        # Test with sample text
        sample_text = "This is a test. " * 100  # Create a longer text
        sample_doc = Document(page_content=sample_text, metadata={"source": "test"})
        
        chunks = splitter.split_documents([sample_doc])
        
        logger.info(f"  Text Splitter: Created {len(chunks)} chunks")
        logger.info("     Chunk size: 800 chars")
        logger.info("     Overlap: 100 chars")
        
        logger.info("Text splitter test passed")
        return True
        
    except Exception as e:
        logger.error(f"Text splitter test failed: {e}")
        return False


def run_all_tests():
    """Run all tests and report results."""
    logger.info("=" * 60)
    logger.info("RAG Ingestion Pipeline - Test Suite")
    logger.info("=" * 60)
    
    tests = [
        ("Environment Variables", test_environment),
        ("Database Connection", test_database_connection),
        ("Azure OpenAI Embeddings", test_azure_openai_embeddings),
        ("Document Files", test_document_files),
        ("Document Loaders", test_document_loaders),
        ("Text Splitter", test_text_splitter),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            logger.error(f"{test_name} failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    logger.info("=" * 60)
    logger.info("Test Summary")
    logger.info("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "PASS" if result else "FAIL"
        if result:
            logger.info(f"  {status}: {test_name}")
        else:
            logger.error(f"  {status}: {test_name}")
    
    logger.info(f"Total: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("All tests passed! Ready to run the ingestion pipeline.")
        logger.info("   Run: uv run python rag_ingestion_pipeline.py")
        return True
    else:
        logger.error("Some tests failed. Please fix the issues before running the pipeline.")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
