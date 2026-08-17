"""
Semantic Chunking Service Module
Handles semantic chunking operations using SemanticSplitterNodeParser.

This module provides:
- Semantic splitter initialization
- Node generation from documents using semantic chunking
"""

import logging
from typing import List, Any
from llama_index.core.node_parser import SemanticSplitterNodeParser
from llama_index.core import Document

logger = logging.getLogger(__name__)


def create_semantic_splitter(embed_model, buffer_size=1, breakpoint_percentile_threshold=95):
    """
    Create a SemanticSplitterNodeParser for semantic chunking.
    
    Args:
        embed_model: Embedding model for semantic similarity calculation
        buffer_size: Number of sentences to include on either side of a split
        breakpoint_percentile_threshold: Percentile threshold for determining split points
        
    Returns:
        SemanticSplitterNodeParser: The configured node parser
    """
    logger.info("Creating SemanticSplitterNodeParser...")
    
    # TODO: Create a SemanticSplitterNodeParser instance and return it
    # HINT: Import and use SemanticSplitterNodeParser from llama_index.core.node_parser
    # HINT: Pass the following parameters:
    #   - buffer_size: Number of sentences to include on either side of a split
    #   - breakpoint_percentile_threshold: Percentile threshold for determining split points
    #   - embed_model: The embedding model for semantic similarity calculation
    # Your code here:
    semantic_splitter = SemanticSplitterNodeParser(
        buffer_size=buffer_size,
        breakpoint_percentile_threshold=breakpoint_percentile_threshold,
        embed_model=embed_model
    )
    return semantic_splitter


def generate_nodes_from_documents(semantic_splitter, documents: List[Document]) -> List[Any]:
    """
    Use the node parser to explicitly generate nodes from documents.
    
    Args:
        semantic_splitter: SemanticSplitterNodeParser instance
        documents: List of Document objects
        
    Returns:
        list: List of Node objects
    """
    logger.info("Generating nodes using semantic splitter...")
    
    # TODO: Generate nodes from documents using the semantic splitter and return them
    # HINT: Use the semantic_splitter's get_nodes_from_documents() method
    # HINT: Pass the documents list as the argument
    # Your code here:
    nodes = semantic_splitter.get_nodes_from_documents(documents)
    return nodes