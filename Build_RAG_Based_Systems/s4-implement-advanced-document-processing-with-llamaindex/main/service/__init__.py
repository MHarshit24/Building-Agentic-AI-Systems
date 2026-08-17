"""
Service Package
Service layer for API and CLI usage.
"""

from main.service.rag_service import (
    initialize_services,
    get_index,
    get_query_engine,
    get_embed_model,
    get_llm,
    add_documents_to_index
)
from main.service.metadata import get_file_metadata
from main.service.semantic_chunking import (
    create_semantic_splitter,
    generate_nodes_from_documents
)
from main.service.query_engine import create_query_engine

__all__ = [
    "initialize_services",
    "get_index",
    "get_query_engine",
    "get_embed_model",
    "get_llm",
    "add_documents_to_index",
    "get_file_metadata",
    "create_semantic_splitter",
    "generate_nodes_from_documents",
    "create_query_engine"
]

