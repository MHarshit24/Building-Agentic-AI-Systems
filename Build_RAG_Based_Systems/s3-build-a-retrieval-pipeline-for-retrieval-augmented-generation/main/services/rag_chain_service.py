"""
RAG chain service for building and managing LCEL chains.

TODO: Complete the implementation of format_docs() and build_rag_chain() functions.
These functions handle document formatting and LCEL chain construction for the RAG pipeline.
"""

# TODO: Import necessary modules
# Verify these imports are correct for your implementation:
from typing import List, Dict, Any
from langchain_postgres import PGVector
from langchain_openai import AzureChatOpenAI
from langchain_core.documents import Document
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from ..config import logger
from ..prompts import create_production_prompt


def format_docs(docs: List[Document]) -> str:
    """
    Format retrieved documents for context with source attribution.
    
    This function takes a list of Document objects and formats them into a single
    string with source citations, making it suitable for inclusion in LLM prompts.
    
    Args:
        docs: List of retrieved Document objects with metadata
        
    Returns:
        Formatted string with source citations, separated by delimiters.
        Format: "[Source N: filename | Chunk ID: id]\ncontent\n\n---\n\n"
        Returns "No relevant context found." if docs list is empty.
        
    Hints:
        1. Check if docs list is empty - if so, return early with "No relevant context found."
        2. Initialize an empty list for formatted chunks
        3. Iterate through documents with enumerate (starting at 1)
        4. Extract source from doc.metadata.get('source', 'Unknown')
        5. Extract chunk_id from doc.metadata.get('chunk_id', 'N/A')
        6. Get content from doc.page_content
        7. Format each chunk as: "[Source N: source | Chunk ID: chunk_id]\ncontent"
        8. Append formatted chunk to list
        9. Join all chunks with "\n\n---\n\n" separator
        10. Return the formatted string
    """

    # TODO: Step 1 - Check if docs list is empty
    # If empty, return "No relevant context found."

    if not docs:
        return "No relevant context found."

    # TODO: Step 2 - Initialize list for formatted chunks

    formatted_chunks = []

    # TODO: Step 3 - Iterate through documents
    # Use enumerate starting at 1 to get index numbers

    for index, doc in enumerate(
        docs,
        start=1
    ):

        # TODO: Step 4 - Extract metadata from each document
        # Get source from doc.metadata.get('source', 'Unknown')
        # Get chunk_id from doc.metadata.get('chunk_id', 'N/A')
        # Get content from doc.page_content

        source = doc.metadata.get(
            "source",
            "Unknown"
        )

        chunk_id = doc.metadata.get(
            "chunk_id",
            "N/A"
        )

        content = doc.page_content

        # TODO: Step 5 - Format each chunk
        # Format: "[Source N: source | Chunk ID: chunk_id]\ncontent"
        # Append to formatted_chunks list

        formatted_chunk = (
            f"[Source {index}: "
            f"{source} | "
            f"Chunk ID: {chunk_id}]\n"
            f"{content}"
        )

        formatted_chunks.append(
            formatted_chunk
        )

    # TODO: Step 6 - Join all formatted chunks
    # Use "\n\n---\n\n" as separator

    context = "\n\n---\n\n".join(
        formatted_chunks
    )

    logger.debug(
        f"Formatted {len(docs)} documents"
    )

    # TODO: Step 7 - Return the formatted string

    return context


def build_rag_chain(
    vectorstore: PGVector,
    llm: AzureChatOpenAI,
    config: Dict[str, Any]
) -> tuple:
    """
    Build complete LCEL chain: retriever → prompt → LLM → parser.
    
    This function constructs a LangChain Expression Language (LCEL) chain that:
    1. Retrieves relevant documents from the vectorstore
    2. Formats them with source citations
    3. Passes them to the prompt template along with the question
    4. Generates an answer using the LLM
    5. Parses the output to a string
    
    Args:
        vectorstore: PGVector instance connected to the vector database
        llm: AzureChatOpenAI instance for answer generation
        config: Configuration dictionary containing 'top_k' for retrieval
        
    Returns:
        Tuple of (rag_chain, retriever) where:
        - rag_chain: The complete LCEL chain ready for invocation
        - retriever: The retriever instance for direct document retrieval
        
    Hints:
        1. Create retriever from vectorstore using as_retriever()
           - search_type: "similarity"
           - search_kwargs: {"k": config['top_k']}
        2. Create prompt template using create_production_prompt()
        3. Build LCEL chain using pipe operator (|):
           - Start with a dictionary containing:
             * "context": retriever | format_docs (retrieves and formats docs)
             * "question": RunnablePassthrough() (passes question through)
           - Pipe to prompt template
           - Pipe to llm
           - Pipe to StrOutputParser()
        4. Return tuple of (rag_chain, retriever)
    """

    try:

        # TODO: Step 1 - Create retriever from vectorstore
        # Use as_retriever() with:
        #   - search_type="similarity"
        #   - search_kwargs={"k": config['top_k']}

        retriever = vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs={
                "k": config["top_k"]
            }
        )

        logger.info(
            f"Retriever initialized "
            f"(top_k={config['top_k']})"
        )

        # TODO: Step 2 - Create prompt template
        # Call create_production_prompt() function

        prompt = create_production_prompt()

        # TODO: Step 3 - Build LCEL chain
        # Use pipe operator (|) to chain components:
        #   - Start with dictionary: {"context": retriever | format_docs, "question": RunnablePassthrough()}
        #   - Pipe to prompt
        #   - Pipe to llm
        #   - Pipe to StrOutputParser()
        # Store in rag_chain variable

        rag_chain = (
            {
                "context":
                    retriever | format_docs,

                "question":
                    RunnablePassthrough()
            }
            | prompt
            | llm
            | StrOutputParser()
        )

        logger.info(
            "RAG chain built successfully"
        )

        # TODO: Step 4 - Return tuple of (rag_chain, retriever)

        return rag_chain, retriever

    except Exception as e:

        logger.error(
            f"Failed to build RAG chain: {e}",
            exc_info=True
        )

        raise