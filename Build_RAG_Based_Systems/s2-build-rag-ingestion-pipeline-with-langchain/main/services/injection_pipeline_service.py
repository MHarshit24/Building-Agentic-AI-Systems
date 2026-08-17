"""
Complete ingestion pipeline orchestration service.
"""

import os
import logging
from typing import List, Dict, Any, Optional
from langchain_core.documents import Document

from main.config import logger
from main.services.document_processing_service import DocumentProcessingService
from main.services.chunking_service import ChunkingService
from main.services.embedding_service import EmbeddingService


class InjectionPipelineService:
    """Service for orchestrating the complete document ingestion pipeline."""
    
    def __init__(
        self,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
        collection_name: Optional[str] = None
    ):
        """
        Initialize the ingestion pipeline service.
        
        Args:
            chunk_size: Size of each chunk (default from config)
            chunk_overlap: Overlap between chunks (default from config)
            collection_name: Name of the collection in vector database (default from config)
        """
        self.logger = logger or logging.getLogger(__name__)
        
        # Initialize services
        self.document_processor = DocumentProcessingService()
        self.chunking_service = ChunkingService(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
        self.embedding_service = EmbeddingService(collection_name=collection_name)
    
    def process_file(
        self, 
        file_path: str,
        chunk: bool = True
    ) -> Dict[str, Any]:
        """
        Process a single file through the complete pipeline.
        
        Args:
            file_path: Path to the file to process
            chunk: Whether to chunk the documents (default: True)
            
        Returns:
            Dictionary with processing results
        """
        try:
            self.logger.info(f"Processing file: {file_path}")
            
            # Step 1: Load document
            documents = self.document_processor.process_file(file_path)
            
            if not documents:
                return {
                    "status": "warning",
                    "message": f"No documents loaded from {file_path}",
                    "filename": os.path.basename(file_path),
                    "documents_loaded": 0,
                    "chunks_created": 0,
                    "embeddings_stored": 0
                }
            
            # Step 2: Chunk documents (if requested)
            if chunk:
                chunks = self.chunking_service.chunk_documents(documents)
            else:
                chunks = documents
            
            # Step 3: Store in vector database
            ids = self.embedding_service.store_documents(chunks)
            
            return {
                "status": "success",
                "message": f"Successfully processed {os.path.basename(file_path)}",
                "filename": os.path.basename(file_path),
                "documents_loaded": len(documents),
                "chunks_created": len(chunks),
                "embeddings_stored": len(ids)
            }
            
        except Exception as e:
            error_msg = f"Error processing file {file_path}: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            return {
                "status": "error",
                "message": error_msg,
                "filename": os.path.basename(file_path) if os.path.exists(file_path) else file_path,
                "documents_loaded": 0,
                "chunks_created": 0,
                "embeddings_stored": 0
            }
    
    def process_directory(
        self,
        directory: str,
        recursive: bool = False,
        chunk: bool = True
    ) -> Dict[str, Any]:
        """
        Process all files in a directory through the complete pipeline.
        
        Args:
            directory: Directory path to process
            recursive: Whether to process subdirectories recursively
            chunk: Whether to chunk the documents (default: True)
            
        Returns:
            Dictionary with processing results
        """
        try:
            self.logger.info(f"Processing directory: {directory}")
            
            # Step 1: Load all documents
            documents = self.document_processor.process_directory(directory, recursive=recursive)
            
            if not documents:
                return {
                    "status": "warning",
                    "message": f"No documents found in {directory}",
                    "documents_loaded": 0,
                    "chunks_created": 0,
                    "embeddings_stored": 0
                }
            
            # Step 2: Chunk documents (if requested)
            if chunk:
                chunks = self.chunking_service.chunk_documents(documents)
            else:
                chunks = documents
            
            # Step 3: Store in vector database
            ids = self.embedding_service.store_documents(chunks)
            
            return {
                "status": "success",
                "message": f"Successfully processed directory: {directory}",
                "documents_loaded": len(documents),
                "chunks_created": len(chunks),
                "embeddings_stored": len(ids)
            }
            
        except Exception as e:
            error_msg = f"Error processing directory {directory}: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            return {
                "status": "error",
                "message": error_msg,
                "documents_loaded": 0,
                "chunks_created": 0,
                "embeddings_stored": 0
            }
    
    def process_url(
        self,
        url: str,
        chunk: bool = True
    ) -> Dict[str, Any]:
        """
        Process a web URL through the complete pipeline.
        
        Args:
            url: URL of the web page to process
            chunk: Whether to chunk the documents (default: True)
            
        Returns:
            Dictionary with processing results
        """
        try:
            self.logger.info(f"Processing URL: {url}")
            
            # Step 1: Load document
            documents = self.document_processor.process_url(url)
            
            if not documents:
                return {
                    "status": "warning",
                    "message": f"No documents loaded from {url}",
                    "url": url,
                    "documents_loaded": 0,
                    "chunks_created": 0,
                    "embeddings_stored": 0
                }
            
            # Step 2: Chunk documents (if requested)
            if chunk:
                chunks = self.chunking_service.chunk_documents(documents)
            else:
                chunks = documents
            
            # Step 3: Store in vector database
            ids = self.embedding_service.store_documents(chunks)
            
            return {
                "status": "success",
                "message": f"Successfully processed {url}",
                "url": url,
                "documents_loaded": len(documents),
                "chunks_created": len(chunks),
                "embeddings_stored": len(ids)
            }
            
        except Exception as e:
            error_msg = f"Error processing URL {url}: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            return {
                "status": "error",
                "message": error_msg,
                "url": url,
                "documents_loaded": 0,
                "chunks_created": 0,
                "embeddings_stored": 0
            }
    
    def run(self, documents_dir: str = "Documents") -> Dict[str, Any]:
        """
        Run the complete ingestion pipeline on a documents directory.
        
        Args:
            documents_dir: Directory containing documents to process
            
        Returns:
            Dictionary with processing results
        """
        self.logger.info("=" * 60)
        self.logger.info("AutoMind Motors - RAG Ingestion Pipeline")
        self.logger.info("=" * 60)
        
        result = self.process_directory(documents_dir, recursive=False, chunk=True)
        
        self.logger.info("=" * 60)
        if result["status"] == "success":
            self.logger.info("Ingestion pipeline completed successfully!")
        else:
            self.logger.warning(f"Ingestion pipeline completed with status: {result['status']}")
        self.logger.info("=" * 60)
        
        return result

