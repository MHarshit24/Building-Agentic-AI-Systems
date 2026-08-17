"""
Service module for managing vectorstore operations.
"""

import logging
from typing import List, Optional

# TODO: Import necessary modules here (Document, PGVector, AzureOpenAIEmbeddings, etc.)

from langchain_core.documents import Document
from langchain_postgres import PGVector
from langchain_openai import AzureOpenAIEmbeddings

from main.config import load_config

logger = logging.getLogger(__name__)


class VectorstoreService:
    """Service class for vectorstore operations."""
    
    def __init__(self):
        """Initialize the vectorstore service with embeddings and vectorstore."""
        self.config = load_config()
        self.embeddings = self._initialize_embeddings()
        self.vectorstore = self._initialize_vectorstore()
    
    def _initialize_embeddings(self):
        """Initialize Azure OpenAI embeddings."""
        try:
            # TODO: Initialize Azure OpenAI embeddings using config values
            # Access config values from self.config (azure_endpoint, azure_embedding_deployment, azure_api_key, api_version)
            # Log success message
            # Return the embeddings object
            
            embeddings = AzureOpenAIEmbeddings(
                azure_endpoint=self.config["azure_endpoint"],
                azure_deployment=self.config["azure_embedding_deployment"],
                api_key=self.config["azure_api_key"],
                api_version=self.config["api_version"],
            )
            
            logger.info("Azure OpenAI embeddings initialized successfully")
            
            return embeddings
            
        except Exception as e:
            # TODO: Add exception handling here
            # Log error appropriately
            # Re-raise the exception
            
            logger.error(f"Failed to initialize embeddings: {e}")
            raise
    
    def _initialize_vectorstore(self):
        """Initialize PGVector store."""
        try:
            # TODO: Initialize PGVector store
            # Use self.embeddings, collection_name from self.config, and database_url from self.config
            # Log success message
            # Return the vectorstore object
            
            vectorstore = PGVector(
                embeddings=self.embeddings,
                collection_name=self.config["collection_name"],
                connection=self.config["database_url"],
            )
            
            logger.info("PGVector store initialized successfully")
            
            return vectorstore
            
        except Exception as e:
            # TODO: Add exception handling here
            # Log error appropriately
            # Re-raise the exception
            
            logger.error(f"Failed to initialize PGVector store: {e}")
            raise
    
    def add_document(self, content: str, metadata: Optional[dict] = None) -> str:
        """
        Add a single document to the vectorstore.
        
        Args:
            content: The text content to add
            metadata: Optional metadata dictionary
            
        Returns:
            Document ID of the inserted document
        """
        try:
            # TODO: Create a Document object with content and metadata
            
            document = Document(
                page_content=content,
                metadata=metadata or {}
            )
            
            # TODO: Add the document to the vectorstore using self.vectorstore
            
            result = self.vectorstore.add_documents([document])
            
            # TODO: Get the document ID from the result
            
            document_id = result[0]
            
            # TODO: Log success message with document ID
            
            logger.info(f"Document added successfully with ID: {document_id}")
            
            # TODO: Return the document ID
            
            return document_id
            
        except Exception as e:
            # TODO: Add exception handling here
            # Log error appropriately
            # Re-raise the exception
            
            logger.error(f"Failed to add document: {e}")
            raise
    
    def add_documents(self, documents: List) -> List[str]:
        """
        Add multiple documents to the vectorstore.
        
        Args:
            documents: List of Document objects
            
        Returns:
            List of document IDs
        """
        try:
            # TODO: Add documents to the vectorstore using self.vectorstore
            
            document_ids = self.vectorstore.add_documents(documents)
            
            # TODO: Get the list of document IDs from the result
            
            # TODO: Log success message with number of documents added
            
            logger.info(f"Successfully added {len(document_ids)} documents")
            
            # TODO: Return the list of document IDs
            
            return document_ids
            
        except Exception as e:
            # TODO: Add exception handling here
            # Log error appropriately
            # Re-raise the exception
            
            logger.error(f"Failed to add documents: {e}")
            raise
    
    def query(self, query_text: str, top_k: int = 1) -> List[dict]:
        """
        Query the vectorstore for similar documents.
        
        Args:
            query_text: The search query
            top_k: Number of results to return
            
        Returns:
            List of result dictionaries with content and metadata
        """
        try:
            # TODO: Perform similarity search using self.vectorstore
            
            results = self.vectorstore.similarity_search(
                query=query_text,
                k=top_k
            )
            
            # TODO: Transform results into list of dictionaries with "content" and "metadata" keys
            
            formatted_results = [
                {
                    "content": doc.page_content,
                    "metadata": doc.metadata
                }
                for doc in results
            ]
            
            # TODO: Return the list of result dictionaries
            
            return formatted_results
            
        except Exception as e:
            # TODO: Add exception handling here
            # Log error appropriately
            # Re-raise the exception
            
            logger.error(f"Failed to query vectorstore: {e}")
            raise


# Global service instance (singleton pattern)
_vectorstore_service: Optional[VectorstoreService] = None


def get_vectorstore_service() -> VectorstoreService:
    """Get or create the global vectorstore service instance."""
    global _vectorstore_service
    # TODO: Implement singleton pattern
    # Check if _vectorstore_service is None, if so create a new instance
    # Return the service instance
    
    if _vectorstore_service is None:
        _vectorstore_service = VectorstoreService()
    
    return _vectorstore_service