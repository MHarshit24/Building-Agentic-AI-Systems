"""
PDF document loading service.
"""

import os
import logging
from typing import List
from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document

from main.config import logger


class PDFLoaderService:
    """Service for loading PDF documents."""
    
    def __init__(self):
        """Initialize the PDF loader service."""
        self.logger = logger or logging.getLogger(__name__)
    
    def load(self, file_path: str) -> List[Document]:
        """
        Load a PDF file and return Document objects.
        
        Args:
            file_path: Path to the PDF file
            
        Returns:
            List of Document objects (one per page)
            
        Raises:
            FileNotFoundError: If file doesn't exist
            Exception: If loading fails
        """
        # TODO: Implement PDF file loading.
        # Expected steps:
        # 1) Validate that `file_path` exists (raise FileNotFoundError if missing)
        # 2) Initialize `PyPDFLoader(file_path)` and call `loader.load()` to get List[Document]
        # 3) For each document, attach metadata:
        #    - "source_file" (os.path.basename(file_path))
        #    - "file_type" = "pdf"
        # 4) Return the list of documents and add basic logging/error handling
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"PDF file not found: {file_path}")

        self.logger.info(f"Loading PDF file: {file_path}")
        try:
            loader = PyPDFLoader(file_path)
            documents = loader.load()

            for doc in documents:
                doc.metadata["source_file"] = os.path.basename(file_path)
                doc.metadata["file_type"] = "pdf"

            self.logger.info(f"Loaded {len(documents)} page(s) from PDF: {os.path.basename(file_path)}")
            return documents

        except Exception as e:
            self.logger.error(f"Failed to load PDF {file_path}: {e}")
            raise