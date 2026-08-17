"""
Embedding generation and vector storage service.
"""

import logging
from typing import List, Optional
from langchain_core.documents import Document
from langchain_openai import AzureOpenAIEmbeddings
from langchain_postgres import PGVector

from main.config import logger, load_config


class EmbeddingService:
    """Service for generating embeddings and storing in vector database."""
    
    def __init__(self, collection_name: Optional[str] = None):
        """
        Initialize the embedding service.
        
        Args:
            collection_name: Name of the collection in vector database (default from config)
        """
        self.logger = logger or logging.getLogger(__name__)
        self.config = load_config()
        
        # Use provided collection name or from config
        self.collection_name = collection_name or self.config.get('collection_name', 'automind_embedding')
        
        # Initialize embeddings
        self.embeddings = self._initialize_embeddings()
        
        # Vectorstore will be initialized on first use
        self.vectorstore: Optional[PGVector] = None
    
    def _initialize_embeddings(self) -> AzureOpenAIEmbeddings:
        """Initialize Azure OpenAI embeddings."""
        # TODO: Implement embeddings initialization.
        # Expected:
        # - Read Azure settings from `self.config`
        # - Create `AzureOpenAIEmbeddings(...)` with endpoint, deployment, api_key, api_version
        # - Return the embeddings instance
        self.logger.info("Initializing Azure OpenAI embeddings")
        return AzureOpenAIEmbeddings(
            azure_endpoint=self.config['azure_endpoint'],
            azure_deployment=self.config['azure_embedding_deployment'],
            api_key=self.config['azure_api_key'],
            api_version=self.config['api_version']
        )
    
    def _initialize_vectorstore(self) -> PGVector:
        """Initialize PGVector store."""
        # TODO: Implement vectorstore initialization.
        # Expected:
        # - If `self.vectorstore` exists, return it
        # - Else, create `PGVector(embeddings=self.embeddings, collection_name=..., connection=...)`
        # - Assign to `self.vectorstore` and return it
        if self.vectorstore is not None:
            return self.vectorstore

        self.logger.info(f"Initializing PGVector store with collection: {self.collection_name}")
        self.vectorstore = PGVector(
            embeddings=self.embeddings,
            collection_name=self.collection_name,
            connection=self.config['database_url']
        )
        return self.vectorstore
    
    def store_documents(self, documents: List[Document]) -> List[str]:
        """
        Store documents in the vector database.
        Embeddings are generated automatically.
        
        Args:
            documents: List of Document objects to store
            
        Returns:
            List of document IDs
        """
        # TODO: Implement vector storage of documents.
        # Expected:
        # - Validate input (return [] if empty)
        # - Get vectorstore via `_initialize_vectorstore()`
        # - Call `add_documents(documents)` and return IDs
        # - Add basic logging and error handling
        if not documents:
            self.logger.warning("No documents provided to store, returning empty list")
            return []

        self.logger.info(f"Storing {len(documents)} document chunk(s) in vector database")
        try:
            vectorstore = self._initialize_vectorstore()
            ids = vectorstore.add_documents(documents)
            self.logger.info(f"Successfully stored {len(ids)} embeddings in collection '{self.collection_name}'")
            return ids
        except Exception as e:
            self.logger.error(f"Failed to store documents: {e}")
            raise
    
    def get_vectorstore(self) -> PGVector:
        """
        Get or initialize the vectorstore.
        
        Returns:
            PGVector instance
        """
        # TODO: Return initialized vectorstore.
        # Expected:
        # - Delegate to `_initialize_vectorstore()` and return the result
        return self._initialize_vectorstore()