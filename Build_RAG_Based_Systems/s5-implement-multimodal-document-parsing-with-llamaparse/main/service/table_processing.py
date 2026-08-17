"""Table Processing Service Module
Handles table summarization and node creation from extracted tables.

This module provides:
- Table summarization interface
- Node creation interface for table summaries
"""
import logging
from typing import List, Dict, Any

from llama_index.core.schema import TextNode
from llama_index.llms.azure_openai import AzureOpenAI

logger = logging.getLogger(__name__)


def summarize_table(llm: AzureOpenAI, table_md: str) -> str:
    """
    Summarize a markdown table into a natural language description.
    
    Args:
        llm: The language model instance
        table_md: Markdown table string
        
    Returns:
        Single-sentence summary of the table
    """
    logger.info("Summarizing table (boilerplate)")

    # TODO: Summarize the markdown table into a single-sentence natural language summary.
    # HINT: Use the provided `llm` to generate the summary text.
    # HINT: Keep the summary concise and factual (include key figures/relationships).
    # HINT: Decide how you want to handle model/content-filter failures (retry/fallback).
    # Your code here:
    prompt = (
        "You are a nutrition expert assistant. "
        "Summarize the following markdown table into a single concise sentence, "
        "capturing the key nutritional figures, relationships, or dietary information it contains.\n\n"
        f"Table:\n{table_md}\n\n"
        "Summary (one sentence):"
    )

    try:
        response = llm.complete(prompt)
        summary = response.text.strip()
        logger.info(f"Table summarized successfully ({len(summary)} characters)")
        return summary
    except Exception as e:
        # Fallback: return a plain description if LLM call fails
        logger.warning(f"LLM summarization failed ({e}), using fallback summary")
        return f"Table containing nutritional or dietary information: {table_md[:200]}"


def build_nodes_from_tables(
    source_name: str, 
    table_markdowns: List[str], 
    llm: AzureOpenAI,
    additional_metadata: Dict[str, Any] = None
) -> List[TextNode]:
    """
    Build TextNode objects from table markdowns with summaries.
    
    Args:
        source_name: Name of the source document
        table_markdowns: List of markdown table strings
        llm: Language model instance for summarization
        additional_metadata: Optional additional metadata to include
        
    Returns:
        List of TextNode objects with table summaries
    """
    logger.info("Building nodes from tables (boilerplate)")

    # TODO: Create TextNode objects from table markdowns.
    # HINT: For each table markdown:
    #   - create a summary using `summarize_table(llm, table_md)`
    #   - create a TextNode(text=summary, metadata=...)
    # HINT: Include at least these metadata fields:
    #   - source: source_name
    #   - content_type: "table_summary"
    #   - table_index: incremental index
    # HINT: Merge `additional_metadata` into each node's metadata if provided.
    # Your code here:
    nodes = []

    for table_index, table_md in enumerate(table_markdowns):
        logger.info(f"Processing table {table_index + 1}/{len(table_markdowns)}")

        summary = summarize_table(llm, table_md)

        metadata = {
            "source": source_name,
            "content_type": "table_summary",
            "table_index": table_index,
        }

        # Merge additional_metadata into each node's metadata if provided
        if additional_metadata:
            metadata.update(additional_metadata)

        node = TextNode(text=summary, metadata=metadata)
        nodes.append(node)

    logger.info(f"Built {len(nodes)} table node(s) from {len(table_markdowns)} table(s)")
    return nodes