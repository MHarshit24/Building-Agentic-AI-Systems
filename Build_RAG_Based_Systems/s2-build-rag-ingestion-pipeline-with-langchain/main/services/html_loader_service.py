"""
HTML file loading service.
"""

import os
import logging
from typing import List
from langchain_community.document_loaders import BSHTMLLoader
from langchain_core.documents import Document

from main.config import logger


class HTMLLoaderService:
    """Service for loading HTML documents."""
    
    def __init__(self):
        """Initialize the HTML loader service."""
        self.logger = logger or logging.getLogger(__name__)
    
    def load(self, file_path: str) -> List[Document]:
        """
        Load an HTML file and return Document objects.
        
        Args:
            file_path: Path to the HTML file
            
        Returns:
            List of Document objects
            
        Raises:
            FileNotFoundError: If file doesn't exist
            Exception: If loading fails
        """
        # TODO: Implement HTML file loading.
        # Expected steps:
        # 1) Validate that `file_path` exists (raise FileNotFoundError if missing)
        # 2) Initialize `BSHTMLLoader(file_path, bs_kwargs={"features": "html.parser"})`
        # 3) Call `loader.load()` to get a List[Document]
        # 4) Attach metadata to each document: "source_file" (basename) and "file_type" = "html"
        # 5) Return the documents and add basic logging/error handling
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"HTML file not found: {file_path}")

        self.logger.info(f"Loading HTML file: {file_path}")
        try:
            loader = BSHTMLLoader(file_path, bs_kwargs={"features": "html.parser"})
            documents = loader.load()

            for doc in documents:
                doc.metadata["source_file"] = os.path.basename(file_path)
                doc.metadata["file_type"] = "html"

            self.logger.info(f"Loaded {len(documents)} document(s) from HTML file: {os.path.basename(file_path)}")
            return documents

        except Exception as e:
            self.logger.error(f"Failed to load HTML file {file_path}: {e}")
            raise