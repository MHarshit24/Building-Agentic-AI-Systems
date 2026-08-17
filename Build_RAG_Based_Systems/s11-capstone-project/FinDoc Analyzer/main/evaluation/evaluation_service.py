"""
FinDoc Analyzer — Evaluation & SLO Measurement Service
Dual .env loader: root .env (secrets) + project .env (config).
evaluation_service.py: main/evaluation/evaluation_service.py

Langfuse SDK: v4 API
  - get_langfuse_client()               → returns Langfuse()
  - langfuse.create_trace_id()          → generate a trace ID
  - langfuse.start_observation(...)     → create a span (replaces trace.span())
  - langfuse.create_score(trace_id=...) → attach a score (replaces langfuse.score())
  - langfuse.flush()                    → flush all pending events
"""

import os
import re
import sys
import time
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from urllib.parse import quote_plus
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


def _load_env():
    if "pytest" in sys.modules:
        return
    base_dir = Path(__file__).resolve().parents[5]
    base_env_path = base_dir / ".env"
    if base_env_path.exists():
        load_dotenv(dotenv_path=base_env_path)
    else:
        load_dotenv()
        logger.warning(f"Root .env not found at {base_env_path}")
    _preserved = {
        "DB_PASSWORD":           os.getenv("DB_PASSWORD"),
        "AZURE_OPENAI_API_KEY":  os.getenv("AZURE_OPENAI_API_KEY"),
        "AZURE_OPENAI_ENDPOINT": os.getenv("AZURE_OPENAI_ENDPOINT"),
        "LANGFUSE_PUBLIC_KEY":   os.getenv("LANGFUSE_PUBLIC_KEY"),
        "LANGFUSE_SECRET_KEY":   os.getenv("LANGFUSE_SECRET_KEY"),
        "LANGFUSE_HOST":         os.getenv("LANGFUSE_HOST"),
    }
    proj_dir = Path(__file__).resolve().parents[2]
    proj_env_path = proj_dir / ".env"
    if proj_env_path.exists():
        load_dotenv(dotenv_path=proj_env_path, override=True)
    else:
        load_dotenv()
        logger.warning(f"Project .env not found at {proj_env_path}")
    for key, val in _preserved.items():
        if val:
            os.environ[key] = val
    for var in ["DATABASE_URL", "POSTGRES_URL", "PGHOST", "PGPORT",
                "PGUSER", "PGPASSWORD", "PGDATABASE"]:
        os.environ.pop(var, None)


_load_env()

# ── SLO thresholds ────────────────────────────────────────────────
SLO_FAITHFULNESS_MIN = float(os.getenv("SLO_FAITHFULNESS_MIN", "0.6"))
SLO_RELEVANCE_MIN    = float(os.getenv("SLO_RELEVANCE_MIN",    "0.5"))
SLO_LATENCY_MAX_MS   = float(os.getenv("SLO_LATENCY_MAX_MS",   "5000"))

# ── RAGAS (graceful import) ───────────────────────────────────────
try:
    from ragas import evaluate as ragas_evaluate
    from ragas.metrics import faithfulness, answer_relevancy, context_precision
    from datasets import Dataset
    RAGAS_AVAILABLE = True
    logger.info("RAGAS framework loaded ✓")
except ImportError:
    RAGAS_AVAILABLE = False
    logger.info("RAGAS not installed — using LLM-based evaluation")

# In-memory query log
_query_log: List[Dict[str, Any]] = []


# ═══════════════════════════════════════════════════════════════════
# Langfuse v4 client
# ═══════════════════════════════════════════════════════════════════

def get_langfuse_client():
    """Return a Langfuse() instance if keys are present, else None."""
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    if not public_key or not secret_key:
        return None
    try:
        from langfuse import Langfuse
        # v4: reads LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST from env
        return Langfuse()
    except Exception as e:
        logger.warning(f"Langfuse init failed: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════
# RAGAS batch evaluation
# ═══════════════════════════════════════════════════════════════════

async def run_ragas_evaluation(
    questions:     List[str],
    answers:       List[str],
    contexts:      List[List[str]],
    ground_truths: Optional[List[str]] = None,
) -> Optional[Dict[str, float]]:
    if not RAGAS_AVAILABLE or not questions:
        return None
    try:
        data = {"question": questions, "answer": answers, "contexts": contexts}
        if ground_truths:
            data["ground_truth"] = ground_truths
        dataset = Dataset.from_dict(data)
        metrics = [faithfulness, answer_relevancy]
        if ground_truths:
            metrics.append(context_precision)
        logger.info(f"Running RAGAS evaluation on {len(questions)} sample(s)...")
        result = ragas_evaluate(dataset=dataset, metrics=metrics)
        scores = result.to_pandas().mean().to_dict()
        logger.info(f"RAGAS scores: {scores}")
        return scores
    except Exception as e:
        logger.error(f"RAGAS evaluation failed: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════
# LLM-based per-query evaluation  (Langfuse v4)
# ═══════════════════════════════════════════════════════════════════

async def evaluate_faithfulness_score(
    langfuse,
    trace_id: str,
    question: str,
    context:  str,
    answer:   str,
) -> Optional[float]:
    """Evaluate answer faithfulness via LLM prompt. Returns score 0–1.
    Uses langfuse.create_score() (v4 API).
    """
    from llama_index.core.settings import Settings
    if not context or not answer:
        return None
    llm = Settings.llm
    if llm is None:
        return None
    try:
        prompt = (
            "You are a financial fact-checker. "
            "Rate how well the ANSWER is supported by the CONTEXT on a scale 0.0 to 1.0.\n"
            "  1.0 = every claim is directly supported\n"
            "  0.0 = answer contains hallucinated or unsupported claims\n"
            "Return ONLY a single decimal number, nothing else.\n\n"
            f"CONTEXT:\n{context[:1500]}\n\n"
            f"ANSWER:\n{answer[:600]}\n\n"
            "SCORE:"
        )
        resp  = await llm.acomplete(prompt)
        match = re.search(r"0?\.\d+|[01]\.?\d*", resp.text.strip())
        score = float(match.group()) if match else 0.5
        score = max(0.0, min(1.0, score))

        # ── Langfuse v4: create_score() ──────────────────────────
        if langfuse and trace_id:
            try:
                langfuse.create_score(
                    trace_id=trace_id,
                    name="faithfulness",
                    value=score,
                    comment=f"Auto-evaluated via LLM | route=rag",
                )
            except Exception as e:
                logger.debug(f"Langfuse faithfulness score failed: {e}")

        return score
    except Exception as e:
        logger.error(f"Faithfulness evaluation failed: {e}")
        return None


async def evaluate_answer_relevance(
    langfuse,
    trace_id: str,
    question: str,
    answer:   str,
) -> Optional[float]:
    """Evaluate answer relevance to question via LLM. Returns score 0–1.
    Uses langfuse.create_score() (v4 API).
    """
    from llama_index.core.settings import Settings
    if not question or not answer:
        return None
    llm = Settings.llm
    if llm is None:
        return None
    try:
        prompt = (
            "You are a financial QA evaluator. "
            "Rate how well the ANSWER addresses the QUESTION on a scale 0.0 to 1.0.\n"
            "  1.0 = directly and completely addresses the question\n"
            "  0.0 = completely irrelevant\n"
            "Return ONLY a single decimal number, nothing else.\n\n"
            f"QUESTION: {question}\n\n"
            f"ANSWER:\n{answer[:600]}\n\n"
            "SCORE:"
        )
        resp  = await llm.acomplete(prompt)
        match = re.search(r"0?\.\d+|[01]\.?\d*", resp.text.strip())
        score = float(match.group()) if match else 0.5
        score = max(0.0, min(1.0, score))

        # ── Langfuse v4: create_score() ──────────────────────────
        if langfuse and trace_id:
            try:
                langfuse.create_score(
                    trace_id=trace_id,
                    name="answer_relevance",
                    value=score,
                    comment=f"Auto-evaluated via LLM",
                )
            except Exception as e:
                logger.debug(f"Langfuse relevance score failed: {e}")

        return score
    except Exception as e:
        logger.error(f"Relevance evaluation failed: {e}")
        return None


async def evaluate_context_precision(
    question: str,
    contexts: List[str],
    answer:   str,
) -> Optional[float]:
    """Evaluate how precisely retrieved context is relevant to the question."""
    from llama_index.core.settings import Settings
    if not contexts or not question:
        return None
    llm = Settings.llm
    if llm is None:
        return None
    try:
        chunks_text = "\n---\n".join(contexts[:4])
        prompt = (
            "You are evaluating retrieval quality. "
            "Rate what fraction of the retrieved CHUNKS are relevant to the QUESTION.\n"
            "  1.0 = all chunks are highly relevant\n"
            "  0.0 = no chunks are relevant\n"
            "Return ONLY a single decimal number between 0.0 and 1.0.\n\n"
            f"QUESTION: {question}\n\n"
            f"RETRIEVED CHUNKS:\n{chunks_text[:1500]}\n\n"
            "SCORE:"
        )
        resp  = await llm.acomplete(prompt)
        match = re.search(r"0?\.\d+|[01]\.?\d*", resp.text.strip())
        score = float(match.group()) if match else 0.5
        return max(0.0, min(1.0, score))
    except Exception as e:
        logger.error(f"Context precision evaluation failed: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════
# Query log + SLO reporting
# ═══════════════════════════════════════════════════════════════════

def log_query(
    question:          str,
    answer:            str,
    routing_used:      str,
    latency_ms:        float,
    faithfulness:      Optional[float] = None,
    relevance:         Optional[float] = None,
    context_precision: Optional[float] = None,
    trace_id:          Optional[str]   = None,
):
    _query_log.append({
        "question":          question,
        "answer":            answer[:200],
        "routing_used":      routing_used,
        "latency_ms":        latency_ms,
        "faithfulness":      faithfulness,
        "relevance":         relevance,
        "context_precision": context_precision,
        "trace_id":          trace_id,
        "timestamp":         time.time(),
    })


def _percentile(data: List[float], pct: float) -> Optional[float]:
    if not data:
        return None
    sorted_data = sorted(data)
    idx = int(len(sorted_data) * pct / 100)
    return sorted_data[min(idx, len(sorted_data) - 1)]


def compute_slo_report() -> Dict[str, Any]:
    if not _query_log:
        return {
            "total_queries_evaluated": 0,
            "avg_faithfulness":        None,
            "avg_relevance":           None,
            "avg_context_precision":   None,
            "avg_latency_ms":          None,
            "p95_latency_ms":          None,
            "routing_distribution":    {},
            "slo_passed":              False,
            "slo_details":             {"message": "No queries logged yet"},
            "ragas_available":         RAGAS_AVAILABLE,
        }

    n            = len(_query_log)
    faith_scores = [r["faithfulness"]      for r in _query_log if r.get("faithfulness")      is not None]
    rel_scores   = [r["relevance"]         for r in _query_log if r.get("relevance")         is not None]
    cp_scores    = [r["context_precision"] for r in _query_log if r.get("context_precision") is not None]
    latencies    = [r["latency_ms"]        for r in _query_log]

    avg_faith = sum(faith_scores) / len(faith_scores) if faith_scores else None
    avg_rel   = sum(rel_scores)   / len(rel_scores)   if rel_scores   else None
    avg_cp    = sum(cp_scores)    / len(cp_scores)    if cp_scores    else None
    avg_lat   = sum(latencies)    / len(latencies)    if latencies    else None
    p95_lat   = _percentile(latencies, 95)

    routing_dist: Dict[str, int] = {}
    for r in _query_log:
        k = r["routing_used"]
        routing_dist[k] = routing_dist.get(k, 0) + 1

    faith_ok   = avg_faith is None or avg_faith >= SLO_FAITHFULNESS_MIN
    rel_ok     = avg_rel   is None or avg_rel   >= SLO_RELEVANCE_MIN
    latency_ok = avg_lat   is None or avg_lat   <= SLO_LATENCY_MAX_MS
    slo_passed = faith_ok and rel_ok and latency_ok

    return {
        "total_queries_evaluated": n,
        "avg_faithfulness":        round(avg_faith, 4) if avg_faith is not None else None,
        "avg_relevance":           round(avg_rel,   4) if avg_rel   is not None else None,
        "avg_context_precision":   round(avg_cp,    4) if avg_cp    is not None else None,
        "avg_latency_ms":          round(avg_lat,   2) if avg_lat   is not None else None,
        "p95_latency_ms":          round(p95_lat,   2) if p95_lat   is not None else None,
        "routing_distribution":    routing_dist,
        "slo_passed":              slo_passed,
        "slo_details": {
            "faithfulness": {"value": avg_faith, "threshold": SLO_FAITHFULNESS_MIN, "passed": faith_ok},
            "relevance":    {"value": avg_rel,   "threshold": SLO_RELEVANCE_MIN,    "passed": rel_ok},
            "latency_ms":   {"value": avg_lat,   "threshold": SLO_LATENCY_MAX_MS,   "passed": latency_ok},
        },
        "ragas_available": RAGAS_AVAILABLE,
    }