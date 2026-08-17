"""
LLM-as-a-Judge Evaluators and Evaluation Pipeline
Implements faithfulness and answer relevance evaluators, plus end-to-end evaluation pipeline.

TODO: Implement the evaluator functions and evaluation pipeline below.
"""

import os
import asyncio
import logging
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from langfuse import Langfuse
from llama_index.core.settings import Settings

from main.service.rag_service import initialize_services, get_query_engine, add_documents_to_index, get_embed_model
from main.service.indexing import load_documents
from main.evaluation.dataset import get_langfuse_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load env vars
load_dotenv()

DATASET_NAME = "product_manual"


async def evaluate_faithfulness_score(
    langfuse,
    trace_id: str,
    query: str,
    context: str,
    answer: str,
) -> float:
    """
    Evaluate if answer is grounded in retrieved context (0.0 - 1.0).
    
    TODO: 
    1. Create judge prompt with question, context, answer, and scoring criteria (0.0-1.0 scale)
    2. Use Settings.llm.complete(judge_prompt) to get judgment
    3. Extract score from judgment text (look for "Score:" line)
    4. Clamp score to 0.0-1.0 range
    5. Attach to Langfuse using langfuse.create_score(trace_id, name="faithfulness", value=score, comment=judgment)
    6. Return score
    """
    judge_prompt = f"""You are an expert evaluator assessing whether an AI-generated answer is faithful to the provided context.

Question: {query}

Retrieved Context:
{context}

Answer:
{answer}

Evaluate if the answer is grounded in and supported by the retrieved context.
- Score 1.0: Answer is completely faithful, every claim is supported by the context
- Score 0.75: Answer is mostly faithful with minor details not explicitly in context
- Score 0.5: Answer is partially faithful, some claims are unsupported
- Score 0.25: Answer has significant content not supported by context
- Score 0.0: Answer contradicts or is completely unrelated to the context

Provide your evaluation in the following format:
Reasoning: <your detailed reasoning>
Score: <score between 0.0 and 1.0>"""

    try:
        judgment = str(Settings.llm.complete(judge_prompt))

        # Extract score from judgment text (look for "Score:" line)
        score = 0.0
        for line in judgment.split("\n"):
            if line.strip().startswith("Score:"):
                try:
                    score = float(line.split("Score:")[1].strip())
                    break
                except (ValueError, IndexError):
                    pass

        # Clamp score to 0.0-1.0 range
        score = max(0.0, min(1.0, score))

        # Attach to Langfuse
        langfuse.create_score(
            trace_id=trace_id,
            name="faithfulness",
            value=score,
            comment=judgment
        )

        logger.info(f"  Faithfulness score: {score:.2f}")
        return score

    except Exception as e:
        logger.error(f"Error evaluating faithfulness: {e}")
        return 0.0


async def evaluate_answer_relevance(
    langfuse,
    trace_id: str,
    query: str,
    answer: str,
) -> float:
    """
    Evaluate how well the answer addresses the question (0.0 - 1.0).
    
    TODO: Similar to evaluate_faithfulness_score but for answer relevance.
    Create prompt with question and answer, get LLM judgment, extract score, attach to Langfuse with name="answer_relevance"
    """
    judge_prompt = f"""You are an expert evaluator assessing how well an AI-generated answer addresses the given question.

Question: {query}

Answer:
{answer}

Evaluate how relevant and complete the answer is in addressing the question.
- Score 1.0: Answer directly and completely addresses the question
- Score 0.75: Answer mostly addresses the question with minor gaps
- Score 0.5: Answer partially addresses the question, missing key aspects
- Score 0.25: Answer barely addresses the question, mostly off-topic
- Score 0.0: Answer does not address the question at all

Provide your evaluation in the following format:
Reasoning: <your detailed reasoning>
Score: <score between 0.0 and 1.0>"""

    try:
        judgment = str(Settings.llm.complete(judge_prompt))

        # Extract score from judgment text (look for "Score:" line)
        score = 0.0
        for line in judgment.split("\n"):
            if line.strip().startswith("Score:"):
                try:
                    score = float(line.split("Score:")[1].strip())
                    break
                except (ValueError, IndexError):
                    pass

        # Clamp score to 0.0-1.0 range
        score = max(0.0, min(1.0, score))

        # Attach to Langfuse
        langfuse.create_score(
            trace_id=trace_id,
            name="answer_relevance",
            value=score,
            comment=judgment
        )

        logger.info(f"  Answer relevance score: {score:.2f}")
        return score

    except Exception as e:
        logger.error(f"Error evaluating answer relevance: {e}")
        return 0.0


async def query_with_evaluation(
    langfuse: Langfuse,
    question: str,
    expected_output: Optional[str] = None,
    similarity_top_k: int = 2,
) -> Dict[str, Any]:
    """
    Execute a RAG query and trigger automated evaluation.
    
    TODO:
    1. Create Langfuse span with langfuse.start_span()
    2. Get query engine and execute query
    3. Extract answer and build context from source_nodes
    4. Run evaluate_faithfulness_score and evaluate_answer_relevance asynchronously
    5. Update span with output and end it
    6. Return dict with question, answer, trace_id, faithfulness, answer_relevance
    """
    # Create Langfuse span with langfuse.start_observation()
    # Note: Langfuse v4 uses create_trace_id() + start_observation() instead of start_span()
    trace_id = langfuse.create_trace_id()
    span = langfuse.start_observation(
        trace_context={"trace_id": trace_id},
        name="rag_query_evaluation",
        input={"question": question},
        metadata={
            "similarity_top_k": similarity_top_k,
            "dataset": DATASET_NAME
        }
    )

    try:
        # Get query engine and execute query
        query_engine = get_query_engine(similarity_top_k=similarity_top_k)
        response = query_engine.query(question)
        answer = str(response)

        # Extract answer and build context from source_nodes
        context_chunks = []
        if hasattr(response, 'source_nodes') and response.source_nodes:
            for node in response.source_nodes:
                text = getattr(node, "text", "") or ""
                if text:
                    context_chunks.append(text)

        context = "\n\n".join(context_chunks) if context_chunks else ""

        # Run evaluate_faithfulness_score and evaluate_answer_relevance asynchronously
        faithfulness, answer_relevance = await asyncio.gather(
            evaluate_faithfulness_score(langfuse, trace_id, question, context, answer),
            evaluate_answer_relevance(langfuse, trace_id, question, answer)
        )

        # Update span with output and end it
        span.update(
            output={
                "answer": answer,
                "faithfulness_score": faithfulness,
                "answer_relevance_score": answer_relevance
            }
        )
        span.end()

        # Return dict with question, answer, trace_id, faithfulness, answer_relevance
        return {
            "question": question,
            "answer": answer,
            "trace_id": trace_id,
            "faithfulness": faithfulness,
            "answer_relevance": answer_relevance,
            "expected_output": expected_output
        }

    except Exception as e:
        logger.error(f"Error in query_with_evaluation: {e}")
        span.update(output={"error": str(e)})
        span.end()
        return {
            "question": question,
            "answer": "",
            "trace_id": trace_id,
            "faithfulness": 0.0,
            "answer_relevance": 0.0,
            "expected_output": expected_output
        }


async def run_dataset_evaluation():
    """
    Evaluation Pipeline: Initialize RAG, load dataset, run evaluation on all items, calculate metrics.
    
    TODO:
    1. Initialize RAG services and load/index documents
    2. Get Langfuse client and load dataset
    3. Loop through dataset items, call query_with_evaluation() for each
    4. Calculate aggregate metrics (average scores, SLO compliance, lowest scoring questions)
    5. Log results and return
    """
    print(f"\n{'='*60}")
    print("Starting RAG Evaluation Pipeline")
    print(f"{'='*60}")

    # Initialize RAG services and load/index documents
    logger.info("Initializing RAG services...")
    initialize_services()

    logger.info("Loading and indexing documents...")
    try:
        documents = load_documents()
        if documents:
            add_documents_to_index(documents)
            logger.info(f"✓ Indexed {len(documents)} document(s)")
        else:
            logger.warning("No documents found to index")
    except Exception as e:
        logger.warning(f"Document loading skipped: {e}")

    # Get Langfuse client and load dataset
    langfuse = get_langfuse_client()
    logger.info(f"Loading dataset '{DATASET_NAME}' from Langfuse...")

    dataset = langfuse.get_dataset(DATASET_NAME)
    items = dataset.items
    logger.info(f"✓ Loaded {len(items)} dataset items")

    # Loop through dataset items, call query_with_evaluation() for each
    results = []
    for i, item in enumerate(items, 1):
        question = item.input.get("question", "") if isinstance(item.input, dict) else str(item.input)
        expected_output = item.expected_output

        logger.info(f"\n[{i}/{len(items)}] Evaluating: {question[:70]}...")

        result = await query_with_evaluation(
            langfuse=langfuse,
            question=question,
            expected_output=expected_output,
            similarity_top_k=2
        )
        results.append(result)

    # Calculate aggregate metrics (average scores, SLO compliance, lowest scoring questions)
    if results:
        faithfulness_scores = [r["faithfulness"] for r in results]
        relevance_scores = [r["answer_relevance"] for r in results]

        avg_faithfulness = sum(faithfulness_scores) / len(faithfulness_scores)
        avg_relevance = sum(relevance_scores) / len(relevance_scores)

        # SLO compliance: both scores >= 0.7 threshold
        SLO_THRESHOLD = 0.7
        slo_compliant = sum(
            1 for r in results
            if r["faithfulness"] >= SLO_THRESHOLD and r["answer_relevance"] >= SLO_THRESHOLD
        )
        slo_compliance_pct = (slo_compliant / len(results)) * 100

        # Lowest scoring questions
        sorted_by_faithfulness = sorted(results, key=lambda x: x["faithfulness"])
        sorted_by_relevance = sorted(results, key=lambda x: x["answer_relevance"])

        print(f"\n{'='*60}")
        print("Evaluation Results Summary")
        print(f"{'='*60}")
        print(f"Total Questions Evaluated : {len(results)}")
        print(f"Avg Faithfulness Score    : {avg_faithfulness:.3f}")
        print(f"Avg Answer Relevance Score: {avg_relevance:.3f}")
        print(f"SLO Threshold             : {SLO_THRESHOLD}")
        print(f"SLO Compliant Items       : {slo_compliant}/{len(results)} ({slo_compliance_pct:.1f}%)")

        print(f"\n--- Lowest Faithfulness Scores ---")
        for r in sorted_by_faithfulness[:3]:
            print(f"  [{r['faithfulness']:.2f}] {r['question'][:70]}...")

        print(f"\n--- Lowest Answer Relevance Scores ---")
        for r in sorted_by_relevance[:3]:
            print(f"  [{r['answer_relevance']:.2f}] {r['question'][:70]}...")

        print(f"\n--- Per-Question Results ---")
        for r in results:
            print(f"  F:{r['faithfulness']:.2f} R:{r['answer_relevance']:.2f} | {r['question'][:60]}...")

        print(f"{'='*60}\n")

        logger.info("✓ Evaluation pipeline complete. All traces logged to Langfuse.")

    langfuse.flush()
    return results


if __name__ == "__main__":
    asyncio.run(run_dataset_evaluation())