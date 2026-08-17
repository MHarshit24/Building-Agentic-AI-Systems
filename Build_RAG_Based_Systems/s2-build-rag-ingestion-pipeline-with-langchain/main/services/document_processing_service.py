"""
Multi-source document processing service.
Handles file type detection and routes to appropriate loader.
"""

import os
import logging
from typing import List, Optional
from langchain_core.documents import Document

from main.config import logger
from main.services.pdf_loader_service import PDFLoaderService
from main.services.text_loader_service import TextLoaderService
from main.services.html_loader_service import HTMLLoaderService
from main.services.web_loader_service import WebLoaderService

def detect_file_type(file_path: str) -> Optional[str]:
    """
    Detect file type from file extension.
    
    Args:
        file_path: Path to the file
        
    Returns:
        File type string ('pdf', 'txt', 'html', 'docx') or None if unsupported
    """
    file_extension = os.path.splitext(file_path)[1].lower()
    
    if file_extension == ".pdf":
        return "pdf"
    elif file_extension == ".txt":
        return "txt"
    elif file_extension in [".html", ".htm"]:
        return "html"
    elif file_extension == ".docx":
        return "docx"
    else:
        return None

def is_supported_file(file_path: str) -> bool:
    """
    Check if file is supported based on extension.
    
    Args:
        file_path: Path to the file
        
    Returns:
        True if file is supported, False otherwise
    """
    file_type = detect_file_type(file_path)
    return file_type is not None


class DocumentProcessingService:
    """Service for processing documents from multiple sources."""
    
    def __init__(self):
        """Initialize the document processing service."""
        self.logger = logger or logging.getLogger(__name__)
        self.pdf_loader = PDFLoaderService()
        self.text_loader = TextLoaderService()
        self.html_loader = HTMLLoaderService()
        self.web_loader = WebLoaderService()
    
    def process_file(self, file_path: str) -> List[Document]:
        """
        Process a file and return Document objects.
        Automatically detects file type and uses appropriate loader.
        
        Args:
            file_path: Path to the file to process
            
        Returns:
            List of Document objects
            
        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file type is not supported
            Exception: If processing fails
        """
        # TODO: Implement file processing.
        # Expected steps:
        # 1) Validate `file_path` exists
        # 2) Detect file type via `detect_file_type`
        # 3) Route to the appropriate loader service:
        #    - PDF: `self.pdf_loader.load(file_path)`
        #    - TXT: `self.text_loader.load(file_path)`
        #    - HTML/HTM: `self.html_loader.load(file_path)`
        # 4) Return a list of `Document`
        # 5) Raise informative errors for missing files or unsupported types
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        file_type = detect_file_type(file_path)
        if file_type is None:
            raise ValueError(f"Unsupported file type for: {file_path}")

        self.logger.info(f"Processing file: {file_path} (detected type: {file_type})")

        if file_type == "pdf":
            return self.pdf_loader.load(file_path)
        elif file_type == "txt":
            return self.text_loader.load(file_path)
        elif file_type == "html":
            return self.html_loader.load(file_path)
        else:
            raise ValueError(f"No loader available for file type: {file_type}")
    
    def process_url(self, url: str, header_template: Optional[dict] = None) -> List[Document]:
        """
        Process a web URL and return Document objects.
        
        Args:
            url: URL of the web page to process
            header_template: Optional headers for the request
            
        Returns:
            List of Document objects
            
        Raises:
            Exception: If processing fails
        """
        # TODO: Implement URL processing.
        # Expected:
        # - Use `self.web_loader.load(url, header_template)` to fetch and parse
        # - Return a list of `Document`
        # - Add basic logging and error handling
        self.logger.info(f"Processing URL: {url}")
        try:
            documents = self.web_loader.load(url, header_template)
            self.logger.info(f"Loaded {len(documents)} document(s) from URL: {url}")
            return documents
        except Exception as e:
            self.logger.error(f"Failed to process URL {url}: {e}")
            raise
    
    def process_directory(self, directory: str, recursive: bool = False) -> List[Document]:
        """
        Process all supported files in a directory.
        
        Args:
            directory: Directory path to process
            recursive: Whether to process subdirectories recursively
            
        Returns:
            List of Document objects from all processed files
        """
        # TODO: Implement directory processing.
        # Expected:
        # - Validate directory exists
        # - Iterate over supported files (optionally recursively)
        # - Use `self.process_file` for each file
        # - Collect and return all `Document` objects
        if not os.path.exists(directory):
            raise FileNotFoundError(f"Directory not found: {directory}")

        self.logger.info(f"Processing directory: {directory} (recursive={recursive})")

        all_documents = []
        pattern = "**/*" if recursive else "*"

        from pathlib import Path
        for file_path in Path(directory).glob(pattern):
            if file_path.is_file() and is_supported_file(str(file_path)):
                try:
                    docs = self.process_file(str(file_path))
                    all_documents.extend(docs)
                except Exception as e:
                    self.logger.warning(f"Skipping file {file_path}: {e}")

        self.logger.info(f"Loaded {len(all_documents)} total document(s) from directory: {directory}")
        return all_documents