"""
Document chunking service.
"""

import logging
from datetime import datetime
from typing import List
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from main.config import logger, load_config


class ChunkingService:
    """Service for chunking documents into smaller pieces."""
    
    def __init__(self, chunk_size: int = None, chunk_overlap: int = None):
        """
        Initialize the chunking service.
        
        Args:
            chunk_size: Size of each chunk (default from config)
            chunk_overlap: Overlap between chunks (default from config)
        """
        self.logger = logger or logging.getLogger(__name__)
        
        # TODO: Initialize chunking configuration and text splitter.
        # Expected steps:
        # 1) If `chunk_size` or `chunk_overlap` is None, load defaults from `load_config()`
        # 2) Assign `self.chunk_size` and `self.chunk_overlap`
        # 3) Create `self.text_splitter = RecursiveCharacterTextSplitter(...)`
        #    with sensible separators and `length_function=len`
        # Note: Keep this constructor side-effect free except initialization.
        if chunk_size is None or chunk_overlap is None:
            config = load_config()
            chunk_size = chunk_size if chunk_size is not None else config.get('chunk_size', 1000)
            chunk_overlap = chunk_overlap if chunk_overlap is not None else config.get('chunk_overlap', 200)

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=["\n\n", "\n", ".", "!", "?", ",", " ", ""],
            length_function=len
        )
        
        self.logger.debug(f"ChunkingService initialized: chunk_size={chunk_size}, overlap={chunk_overlap}")
    
    def chunk_documents(self, documents: List[Document]) -> List[Document]:
        """
        Split documents into chunks with overlap.
        
        Args:
            documents: List of Document objects to chunk
            
        Returns:
            List of chunked Document objects
        """
        # TODO: Implement document chunking.
        # Expected steps:
        # 1) Log the number of documents to chunk
        # 2) Use `self.text_splitter.split_documents(documents)` to create chunks
        # 3) For each chunk, add metadata such as:
        #    - "chunk_id" (sequential index)
        #    - "chunk_identifier" (derive from source_file/source_url + page + chunk_id)
        #    - "chunk_size" (len of chunk.page_content)
        #    - "upload_time" (ISO 8601 string)
        # 4) Return the list of chunked `Document` objects
        self.logger.info(f"Chunking {len(documents)} document(s) into smaller pieces")

        chunks = self.text_splitter.split_documents(documents)

        upload_time = datetime.utcnow().isoformat()
        for chunk_id, chunk in enumerate(chunks):
            # Derive a readable identifier from available metadata
            source = (
                chunk.metadata.get("source_file")
                or chunk.metadata.get("source_url")
                or chunk.metadata.get("source")
                or "unknown"
            )
            page = chunk.metadata.get("page", "")
            page_part = f"_p{page}" if page != "" else ""
            chunk.metadata["chunk_id"] = chunk_id
            chunk.metadata["chunk_identifier"] = f"{source}{page_part}_chunk{chunk_id}"
            chunk.metadata["chunk_size"] = len(chunk.page_content)
            chunk.metadata["upload_time"] = upload_time

        self.logger.info(f"Created {len(chunks)} chunks from {len(documents)} document(s)")
        return chunks
    
    def chunk_text(self, text: str, metadata: dict = None) -> List[Document]:
        """
        Chunk a single text string into Document objects.
        
        Args:
            text: Text to chunk
            metadata: Optional metadata to attach to chunks
            
        Returns:
            List of chunked Document objects
        """
        # TODO: Implement convenience chunking for raw text.
        # Expected:
        # - Wrap `text` into a `Document(page_content=text, metadata=metadata or {})`
        # - Delegate to `self.chunk_documents([doc])`
        # - Return the result
        doc = Document(page_content=text, metadata=metadata or {})
        return self.chunk_documents([doc])