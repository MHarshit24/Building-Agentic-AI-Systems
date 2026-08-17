from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

from llama_index.vector_stores.postgres import PGVectorStore

from main.service.fusion_retrieval import FusionRetrievalService
from main.service.guardrails import GuardrailsValidator
import time


logger = logging.getLogger(__name__)


class RAGService:
    """RAG orchestration: input checks -> fusion retrieval -> output checks/redaction."""

    logger = logging.getLogger(__name__)

    def __init__(
        self,
        *,
        table_name: str,
        similarity_top_k: int = 5,
        validator: Optional[GuardrailsValidator] = None,
    ) -> None:
        """
        TODO: Initialize the RAG service
        
        Steps to implement:
        1. Store table_name and similarity_top_k as instance variables
        2. Create PGVectorStore from environment variables
        3. Initialize FusionRetrievalService
        4. Set up the validator (use provided or get from app.py)
        """
        # TODO: Store instance variables
        # Hint: Save the table_name and similarity_top_k parameters as instance attributes
        self.table_name = table_name
        self.similarity_top_k = similarity_top_k

        # TODO: Create PGVectorStore from environment variables
        # Hint: Use the PGVectorStore class to create a vector store instance by reading database connection parameters from environment variables (host, port, database, user, password) and the table name and embedding dimension
        password = os.getenv("DB_PASSWORD")
        if not password:
            raise EnvironmentError("DB_PASSWORD environment variable is required")

        vector_store = PGVectorStore.from_params(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", "5432")),
            database=os.getenv("DB_NAME", "investment_rag_db"),
            user=os.getenv("DB_USER", "postgres"),
            password=quote_plus(password),
            table_name=self.table_name,
            embed_dim=1536,
        )
        self.logger.info("RAGService: PGVectorStore created table=%s", self.table_name)

        # TODO: Initialize FusionRetrievalService
        # Hint: Create a new FusionRetrievalService instance using the vector store, table name, similarity top k, and configure it with reciprocal rerank mode
        self.retrieval_service = FusionRetrievalService(
            vector_store=vector_store,
            table_name=self.table_name,
            similarity_top_k=self.similarity_top_k,
            mode="reciprocal_rerank",
        )

        # TODO: Set up the validator
        # Hint: If no validator is provided, import and use the get_validator function from the app module, otherwise use the provided validator
        if validator is not None:
            self.validator = validator
        else:
            from main.app import get_validator
            self.validator = get_validator()

        self.logger.info("RAGService: initialized table=%s top_k=%d", self.table_name, self.similarity_top_k)

    def query(self, query_text: str) -> Dict[str, Any]:
        """
        TODO: Implement the query orchestration method
        
        Steps to implement:
        1. Initialize validation_results dictionary with default values
        2. Validate input using validator.decide_input()
        3. If input is blocked, return early with blocked response
        4. Try to retrieve and generate answer using retrieval service
        5. Handle retrieval errors gracefully
        6. Validate and sanitize output using validator
        7. Update validation_results with output validation results
        8. Return the final result dictionary
        
        Expected return structure:
        {
            "query": str,
            "answer": str,
            "retrieved_nodes": List[Dict[str, Any]],
            "validation_results": Dict[str, Any]
        }
        """
        t0 = time.perf_counter()

        # TODO: Initialize validation_results dictionary with default values
        # Hint: Create a dictionary to track validation state with fields for input validation, PII detection, output sanitization, and blocking status
        validation_results: Dict[str, Any] = {
            "input_allowed": True,
            "input_block_reason": None,
            "pii_detected": False,
            "pii_summaries": [],
            "output_sanitized": False,
            "output_blocked": False,
            "output_block_reason": None,
        }

        # TODO: Validate input using validator
        # Hint: Use the validator's decide_input method to check if the query text is allowed
        input_decision = self.validator.decide_input(query_text)

        # TODO: Check if input is blocked and return early if needed
        # Hint: If the input decision indicates the query is not allowed, update the validation results with the blocking reason and return a response indicating the query was blocked
        if not input_decision.allowed:
            validation_results["input_allowed"] = False
            validation_results["input_block_reason"] = input_decision.reason
            self.logger.info("query.input_blocked reason=%s", input_decision.reason)
            return {
                "query": query_text,
                "answer": f"Query blocked: {input_decision.reason}",
                "retrieved_nodes": [],
                "validation_results": validation_results,
            }

        # TODO: Try to retrieve and generate answer (handle errors gracefully)
        # Hint: Use the retrieval service to query for an answer and retrieve relevant chunks, wrapping this in error handling to catch cases where no documents are available
        try:
            answer = self.retrieval_service.query(query_text)
            chunks = self.retrieval_service.retrieve(query_text)
        except Exception as e:
            self.logger.warning("query.retrieval_error: %s", e)
            return {
                "query": query_text,
                "answer": "No documents available. Please upload documents before querying.",
                "retrieved_nodes": [],
                "validation_results": validation_results,
            }

        # TODO: Validate and sanitize output
        # Hint: Use the validator to check the generated answer for PII and sanitize it if necessary
        output_decision = self.validator.validate_and_sanitize_output(answer)

        # TODO: Update validation_results with output validation results
        # Hint: Extract the PII detection status, summaries, sanitization status, and blocking information from the output decision and update the validation results dictionary
        validation_results["pii_detected"] = output_decision.pii_detected
        validation_results["pii_summaries"] = output_decision.pii_summaries
        validation_results["output_sanitized"] = output_decision.output_sanitized
        validation_results["output_blocked"] = output_decision.blocked
        validation_results["output_block_reason"] = output_decision.reason

        self.logger.info(
            "query.done ms=%.1f pii=%s sanitized=%s nodes=%d",
            (time.perf_counter() - t0) * 1000,
            output_decision.pii_detected,
            output_decision.output_sanitized,
            len(chunks),
        )

        # TODO: Return the final result dictionary
        # Hint: Construct and return a dictionary containing the original query, the sanitized answer, the retrieved nodes with their metadata, and the complete validation results
        return {
            "query": query_text,
            "answer": output_decision.sanitized_text,
            "retrieved_nodes": [
                {"text": c.text, "score": c.score, "source": c.source}
                for c in chunks
            ],
            "validation_results": validation_results,
        }