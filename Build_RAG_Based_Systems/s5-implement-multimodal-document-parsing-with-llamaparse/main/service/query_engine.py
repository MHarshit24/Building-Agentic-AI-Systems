"""Query engine creation for RAG queries.

This module provides:
- Query engine creation from a VectorStoreIndex with configurable similarity search
- Optional metadata filtering using LlamaIndex MetadataFilters
"""
import logging
from typing import Any, Optional, Dict

from llama_index.core import VectorStoreIndex
from llama_index.core.vector_stores.types import ExactMatchFilter, MetadataFilters

logger = logging.getLogger(__name__)

def create_query_engine(
    index: VectorStoreIndex,
    llm: Any,
    similarity_top_k: int = 2,
    filters: Optional[Any] = None,
):
    """Create a LlamaIndex query engine from an index.

    Args:
        index: VectorStoreIndex instance
        llm: LLM instance (AzureOpenAI, etc.)
        similarity_top_k: Number of top similar nodes to retrieve
        filters: Either:
          - None
          - dict[str, Any] (converted to MetadataFilters via ExactMatchFilter)
          - MetadataFilters (passed through as-is)
    """
    logger.info("Creating query engine...")

    metadata_filters = None
    if filters:
        if isinstance(filters, dict):
            metadata_filters = MetadataFilters(
                filters=[ExactMatchFilter(key=k, value=v) for k, v in filters.items()]
            )
        else:
            # Assume caller passed a MetadataFilters-compatible object
            metadata_filters = filters

    query_engine = index.as_query_engine(
        llm=llm,
        similarity_top_k=similarity_top_k,
        filters=metadata_filters,
    )

    logger.info(f"✓ Query engine created (similarity_top_k={similarity_top_k})")
    if metadata_filters:
        logger.info(f"  Filters applied: {metadata_filters}")

    return query_engine
