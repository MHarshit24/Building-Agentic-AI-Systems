"""
Document Ingestion Service - Loads and stores policy documents with embeddings
"""
import logging
from llama_index.core import SimpleDirectoryReader, Document, VectorStoreIndex, StorageContext
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.ingestion import IngestionPipeline
from llama_index.vector_stores.postgres import PGVectorStore
from typing import List, Optional
import os
from pathlib import Path
from urllib.parse import quote_plus

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class DocumentIngestionPipeline:
    """
    LlamaIndex ingestion pipeline for loading, processing, and persisting documents
    with embeddings in PostgreSQL using pgvector
    """
    
    def __init__(
        self,
        data_dir: str = "./Documents",
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        table_name: str = None,
        db_host: str = None,
        db_port: int = None,
        db_name: str = None,
        db_user: str = None,
        db_password: str = None
    ):
        """
        Initialize the ingestion pipeline with PostgreSQL pgvector
        
        Args:
            data_dir: Directory containing policy documents (default: ./Documents)
            chunk_size: Size of text chunks for splitting
            chunk_overlap: Overlap between chunks
            table_name: PostgreSQL table name for storing vectors (reads from DB_TABLE_NAME env)
            db_host: PostgreSQL host (reads from DB_HOST env)
            db_port: PostgreSQL port (reads from DB_PORT env)
            db_name: Database name (reads from DB_NAME env)
            db_user: Database user (reads from DB_USER env)
            db_password: Database password (reads from DB_PASSWORD env)
        """
        self.data_dir = data_dir
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        
        # Get database credentials from environment or parameters
        self.db_user = db_user or os.getenv("DB_USER", "postgres")
        self.db_password = db_password or os.getenv("DB_PASSWORD", "password")
        self.db_host = db_host or os.getenv("DB_HOST", "localhost")
        self.db_port = db_port or int(os.getenv("DB_PORT", "5432"))
        self.db_name = db_name or os.getenv("DB_NAME", "hospital_analytics_db")
        self.table_name = table_name or os.getenv("DB_TABLE_NAME", "policy_document_embeddings")
        
    def load_documents(self) -> List[Document]:
        """
        Load documents from the Documents directory
        
        Returns:
            List of Document objects
        
        Raises:
            FileNotFoundError: If data directory doesn't exist
            ValueError: If no .txt files found in directory
        """
        if not os.path.exists(self.data_dir):
            raise FileNotFoundError(
                f"Upload directory not found: {self.data_dir}. "
                "Please upload documents first using /api/documents/upload"
            )
        
        # Check if there are any .txt files
        txt_files = list(Path(self.data_dir).glob("*.txt"))
        if not txt_files:
            raise ValueError(
                f"No .txt files found in {self.data_dir}. "
                "Please upload documents using /api/documents/upload"
            )
        
        # Load all text files from the Documents directory
        reader = SimpleDirectoryReader(
            input_dir=self.data_dir,
            required_exts=[".txt"],
            recursive=False
        )
        
        documents = reader.load_data()
        logger.info(f"Loaded {len(documents)} document(s) from {self.data_dir}")
        
        return documents
    
    def _get_vector_store(self) -> PGVectorStore:
        """
        Create and return a PostgreSQL vector store instance
        
        Returns:
            PGVectorStore instance
        """
        return PGVectorStore.from_params(
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
            user=self.db_user,
            password=quote_plus(self.db_password),
            table_name=self.table_name,
            embed_dim=1536,  # Azure OpenAI text-embedding-3-small dimension
        )
    
    def process_and_store_documents(
        self, 
        documents: List[Document]
    ) -> tuple[List[Document], VectorStoreIndex]:
        """
        Process documents and store them with embeddings in PostgreSQL pgvector
        
        Args:
            documents: List of documents to process
            
        Returns:
            Tuple of (processed nodes, vector store index)
        """
        # Create a sentence splitter for chunking
        text_splitter = SentenceSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap
        )
        
        # Create ingestion pipeline with transformations
        pipeline = IngestionPipeline(
            transformations=[
                text_splitter,
            ]
        )
        
        # Run the pipeline to create nodes
        nodes = pipeline.run(documents=documents)
        logger.info(f"Processed {len(documents)} document(s) into {len(nodes)} chunk(s)")
        
        # Initialize PostgreSQL vector store
        try:
            vector_store = self._get_vector_store()
            logger.info(f"Connected to PostgreSQL at {self.db_host}:{self.db_port}/{self.db_name}")
        except Exception as e:
            raise ConnectionError(f"Failed to connect to PostgreSQL: {e}")
        
        # Clear existing data in table (optional - removes old embeddings)
        try:
            # This will be handled by the vector store's upsert logic
            logger.info(f"Using table: {self.table_name}")
        except Exception as e:
            logger.warning(f"Warning: {e}")
        
        # Create storage context with vector store
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        
        # Create and persist vector index
        logger.info("Creating embeddings and storing in PostgreSQL pgvector...")
        vector_index = VectorStoreIndex(
            nodes=nodes,
            storage_context=storage_context,
            show_progress=True
        )
        
        logger.info(f"Embeddings persisted to PostgreSQL table: {self.table_name}")
        
        return nodes, vector_index
    
    def run(self) -> tuple[List[Document], VectorStoreIndex]:
        """
        Run the complete ingestion pipeline with PostgreSQL persistent storage
        
        Returns:
            Tuple of (processed nodes, vector store index)
        """
        logger.info("="*60)
        logger.info("Document Ingestion Pipeline with PostgreSQL pgvector")
        logger.info("="*60)
        
        # Step 1: Load documents
        logger.info("[1/3] Loading policy documents...")
        documents = self.load_documents()
        
        # Log document metadata
        for i, doc in enumerate(documents, 1):
            filename = doc.metadata.get('file_name', 'Unknown')
            file_size = len(doc.text)
            logger.info(f"Document {i}: {filename} ({file_size:,} characters)")
        
        # Step 2: Process and store documents with embeddings
        logger.info("[2/3] Processing and creating embeddings...")
        nodes, vector_index = self.process_and_store_documents(documents)
        
        # Step 3: Summary
        logger.info("[3/3] Storage Summary:")
        logger.info(f"Total chunks: {len(nodes)}")
        logger.info(f"Database: {self.db_host}:{self.db_port}/{self.db_name}")
        logger.info(f"Table name: {self.table_name}")
        
        logger.info("="*60)
        logger.info("Ingestion Pipeline Complete - Embeddings Persisted to PostgreSQL")
        logger.info("="*60)
        
        return nodes, vector_index
    
    @staticmethod
    def load_from_db(
        table_name: str = None,
        db_host: str = None,
        db_port: int = None,
        db_name: str = None,
        db_user: str = None,
        db_password: str = None
    ) -> Optional[VectorStoreIndex]:
        """
        Load a previously stored vector index from PostgreSQL
        
        Args:
            table_name: PostgreSQL table name (reads from DB_TABLE_NAME env)
            db_host: PostgreSQL host (reads from DB_HOST env)
            db_port: PostgreSQL port (reads from DB_PORT env)
            db_name: Database name (reads from DB_NAME env)
            db_user: Database user (reads from DB_USER env)
            db_password: Database password (reads from DB_PASSWORD env)
            
        Returns:
            VectorStoreIndex if found, None otherwise
        """
        try:
            # Get database credentials from environment
            user = db_user or os.getenv("DB_USER", "postgres")
            password = db_password or os.getenv("DB_PASSWORD", "password")
            host = db_host or os.getenv("DB_HOST", "localhost")
            port = db_port or int(os.getenv("DB_PORT", "5432"))
            database = db_name or os.getenv("DB_NAME", "hospital_analytics_db")
            table = table_name or os.getenv("DB_TABLE_NAME", "policy_document_embeddings")
            
            # Initialize PostgreSQL vector store
            vector_store = PGVectorStore.from_params(
                host=host,
                port=port,
                database=database,
                user=user,
                password=quote_plus(password),
                table_name=table,
                embed_dim=1536,
            )
            
            # Load index from vector store
            vector_index = VectorStoreIndex.from_vector_store(vector_store)
            
            logger.info(f"Loaded existing embeddings from PostgreSQL table: {table}")
            return vector_index
            
        except Exception as e:
            logger.warning(f"Could not load existing embeddings: {e}")
            return None