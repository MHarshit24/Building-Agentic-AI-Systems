"""
Query service for executing RAG queries with error handling.

TODO: Complete the implementation of query_with_error_handling() and evaluate_response() functions.
These functions handle query execution, error handling, and response evaluation in the RAG pipeline.
"""

# TODO: Import necessary modules
# Verify these imports are correct for your implementation:
from typing import Dict, Any
from datetime import datetime
from langchain_core.runnables import Runnable
from ..config import logger


def query_with_error_handling(
    rag_chain: Runnable,
    retriever: Any,
    query: str
) -> Dict[str, Any]:
    """
    Execute query with comprehensive error handling and validation.

    This function orchestrates the RAG query pipeline: validates input, retrieves documents,
    executes the RAG chain, validates the response, and analyzes quality metrics.

    Args:
        rag_chain: The LCEL chain that combines retriever, prompt, and LLM
        retriever: The retriever for fetching source documents from vectorstore
        query: User question string

    Returns:
        Dictionary containing:
        - query: Original query string
        - timestamp: ISO format timestamp
        - status: "success", "failed", or "unknown"
        - answer: Generated answer (if successful)
        - retrieved_chunks: Number of chunks retrieved
        - sources: List of source documents with metadata
        - quality_metrics: Dictionary with quality indicators
        - error: Error message (if failed)

    Hints:
        1. Initialize result dictionary with query, timestamp, and status
        2. Wrap the entire logic in try-except for error handling
        3. Validate input query (minimum 3 characters, not empty)
        4. If validation fails, set status to "failed" and return early
        5. Invoke retriever to get relevant documents
        6. Extract source information from retrieved documents (source, chunk_id, content preview)
        7. Invoke the RAG chain to get the answer
        8. Validate the response is not empty
        9. If response is empty, set status to "failed" and return
        10. Set answer and status to "success"
        11. Calculate quality metrics (has_answer, cited_sources, graceful_failure, contact_provided)
        12. In except block, set error details
    """

    # TODO: Step 1 - Initialize result dictionary
    # Include: query, timestamp (ISO format using datetime.now().isoformat()), status ("unknown")
    # This dictionary will be used throughout the function and returned at the end

    result = {
        "query": query,
        "timestamp": datetime.now().isoformat(),
        "status": "unknown"
    }

    try:

        # TODO: Step 2 - Validate input query
        # Check if query is empty or less than 3 characters after stripping
        # If invalid, set status to "failed", add error message, and return result

        if not query or len(query.strip()) < 3:

            result["status"] = "failed"

            result["error"] = (
                "Query must contain at least "
                "3 characters"
            )

            return result

        logger.info(
            f"Executing query: "
            f"{query[:100]}"
        )

        # TODO: Step 3 - Retrieve relevant documents
        # Invoke the retriever with the query
        # Store the number of retrieved chunks in result

        docs = retriever.invoke(query)

        result["retrieved_chunks"] = len(
            docs
        )

        logger.info(
            f"Retrieved {len(docs)} chunks"
        )

        # TODO: Step 4 - Extract source information
        # Create a list of dictionaries with source metadata:
        #   - source: from doc.metadata.get('source', 'Unknown')
        #   - chunk_id: from doc.metadata.get('chunk_id', 'N/A')
        #   - content_preview: first 200 characters of doc.page_content + "..."
        # Store this list in result["sources"]

        result["sources"] = []

        for doc in docs:

            source_info = {

                "source":
                    doc.metadata.get(
                        "source",
                        "Unknown"
                    ),

                "chunk_id":
                    doc.metadata.get(
                        "chunk_id",
                        "N/A"
                    ),

                "content_preview":
                    doc.page_content[:200]
                    + "..."
            }

            result["sources"].append(
                source_info
            )

        # TODO: Step 5 - Execute RAG chain
        # Invoke the rag_chain with the query

        response = rag_chain.invoke(
            query
        )

        # TODO: Step 6 - Validate response
        # Check if response is empty or only whitespace
        # If empty, set status to "failed", add error message, and return result

        if (
            not response
            or
            not response.strip()
        ):

            result["status"] = "failed"

            result["error"] = (
                "Generated response is empty"
            )

            return result

        # TODO: Step 7 - Set success status and answer
        # Store the response in result["answer"]
        # Set result["status"] to "success"

        result["answer"] = response

        result["status"] = "success"

        # TODO: Step 8 - Calculate quality metrics
        # Create a dictionary with:
        #   - has_answer: boolean (response length > 0)
        #   - cited_sources: boolean (check if "Source" appears in response)
        #   - graceful_failure: boolean (check if "don't have enough information" in lowercase response)
        #   - contact_provided: boolean (check if support email or phone number in response)
        # Store in result["quality_metrics"]

        lower_response = response.lower()

        result["quality_metrics"] = {

            "has_answer":
                len(
                    response.strip()
                ) > 0,

            "cited_sources":
                "source" in lower_response,

            "graceful_failure":
                (
                    "don't have enough information"
                    in lower_response
                ),

            "contact_provided":
                (
                    "support@automind.com"
                    in lower_response
                )
                or
                (
                    "1-800-auto-mind"
                    in lower_response
                )
        }

        logger.info(
            "Query completed successfully"
        )

        # TODO: Step 9 - Return the result dictionary

        return result

    except Exception as e:

        logger.error(
            f"Query execution failed: {e}",
            exc_info=True
        )

        # TODO: Step 10 - Handle errors
        # Set result["status"] to "failed"
        # Set result["error"] with error message (str(e))
        # Set result["error_type"] with exception type name (type(e).__name__)
        # Return the result dictionary (do not raise - return the error result)

        result["status"] = "failed"

        result["error"] = str(e)

        result["error_type"] = (
            type(e).__name__
        )

        return result


def evaluate_response(result: Dict[str, Any]) -> None:
    """
    Evaluate and display response quality metrics.

    This function logs comprehensive evaluation metrics for the query result,
    including status, retrieved chunks, quality indicators, and source information.

    Args:
        result: Query result dictionary from query_with_error_handling()
    """

    # TODO: Log the result dictionary

    logger.info("=" * 60)

    logger.info(
        f"Status: "
        f"{result.get('status')}"
    )

    logger.info(
        f"Retrieved Chunks: "
        f"{result.get('retrieved_chunks', 0)}"
    )

    quality = result.get(
        "quality_metrics",
        {}
    )

    for metric, value in quality.items():

        logger.info(
            f"{metric}: {value}"
        )

    logger.info(
        f"Sources: "
        f"{len(result.get('sources', []))}"
    )

    if result.get("error"):

        logger.error(
            f"Error: "
            f"{result['error']}"
        )

    logger.info("=" * 60)