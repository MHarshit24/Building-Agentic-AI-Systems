"""
Vector similarity search service.
"""

import logging
from typing import List, Dict, Any, Optional
from langchain_postgres import PGVector

from main.config import logger
from main.services.embedding_service import EmbeddingService


class QueryService:
    """Service for querying the vector database."""
    
    def __init__(self, collection_name: Optional[str] = None):
        """
        Initialize the query service.
        
        Args:
            collection_name: Name of the collection in vector database (default from config)
        """
        self.logger = logger or logging.getLogger(__name__)
        self.embedding_service = EmbeddingService(collection_name=collection_name)
        self.vectorstore: Optional[PGVector] = None
    
    def _get_vectorstore(self) -> PGVector:
        """Get or initialize the vectorstore."""
        if self.vectorstore is None:
            self.vectorstore = self.embedding_service.get_vectorstore()
        return self.vectorstore
    
    def similarity_search(
        self, 
        query: str, 
        top_k: int = 5,
        filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Perform similarity search on the vector database.
        
        Args:
            query: Search query text
            top_k: Number of results to return
            filter: Optional metadata filter
            
        Returns:
            List of result dictionaries with content and metadata
        """
        try:
            # TODO: Get the vectorstore instance using the helper method
            # Hint: Use self._get_vectorstore()
            vectorstore = self._get_vectorstore()
            
            self.logger.debug(f"Performing similarity search: query='{query}', top_k={top_k}")
            
            # TODO: Perform similarity search on the vectorstore
            # Hint: Use similarity_search_with_score method
            # - If filter is provided, pass it as a parameter
            # - Use top_k for the k parameter
            # - Store results in a variable called 'results'
            if filter:
                results = vectorstore.similarity_search_with_score(query, k=top_k, filter=filter)
            else:
                results = vectorstore.similarity_search_with_score(query, k=top_k)
            
            # TODO: Log the number of results found
            # Hint: Use self.logger.info() with the count of results
            self.logger.info(f"Similarity search returned {len(results)} result(s)")
            
            # TODO: Return the results
            # Note: Results should be a list of tuples (Document, distance_score)
            return results
            
        except Exception as e:
            self.logger.error(f"Query failed: {e}", exc_info=True)
            raise