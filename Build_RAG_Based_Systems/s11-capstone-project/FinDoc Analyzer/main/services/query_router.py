"""
FinDoc Analyzer — Intelligent Query Router
Dual .env loader: root .env (secrets) + project .env (config).
query_router.py: main/services/query_router.py
  parents[5] = Building_Agentic_AI_Systems  -> root .env
  parents[2] = FinDoc Analyzer              -> project .env
"""

import os
import sys
import logging
from pathlib import Path
from typing import Dict, Any
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

# ── Keyword-based routing heuristics ─────────────────────────────

SQL_KEYWORDS = [
    "revenue", "profit", "earnings", "ebitda", "eps", "ratio",
    "net income", "gross margin", "operating income", "cash flow",
    "total assets", "liabilities", "equity", "debt", "capex",
    "how much", "what is the", "calculate", "compare", "growth rate",
    "year over year", "yoy", "quarter", "fiscal year",
    "per share", "market cap", "balance sheet", "income statement",
    "cash flow statement", "return on", "price to", "p/e",
]

RAG_KEYWORDS = [
    "explain", "describe", "what are", "discuss", "summarize",
    "risk", "strategy", "outlook", "guidance", "management",
    "notes", "disclosure", "footnote", "policy", "compliance",
    "why", "how does", "what happened", "tell me about",
    "annual report", "10-k", "10-q", "filing", "narrative",
]

MCP_KEYWORDS = [
    "current", "latest", "today", "real-time", "live",
    "market data", "stock price", "news", "analyst",
    "current price", "share price", "market cap today",
]


def classify_query(question: str, routing_hint: str = None) -> str:
    """
    Classify a query into routing category.
    Priority: explicit hint > keyword scoring > default (hybrid)
    """
    if routing_hint and routing_hint.lower() in ("rag", "sql", "hybrid", "mcp"):
        logger.info(f"Query routed via explicit hint: {routing_hint}")
        return routing_hint.lower()

    q_lower = question.lower()

    sql_score = sum(1 for kw in SQL_KEYWORDS if kw in q_lower)
    rag_score = sum(1 for kw in RAG_KEYWORDS if kw in q_lower)
    mcp_score = sum(1 for kw in MCP_KEYWORDS if kw in q_lower)

    logger.debug(f"Routing scores — SQL:{sql_score} RAG:{rag_score} MCP:{mcp_score}")

    if mcp_score >= 2:
        return "mcp"
    if sql_score >= 3 and rag_score <= 1:
        return "sql"
    if rag_score >= 3 and sql_score <= 1:
        return "rag"
    return "hybrid"


async def route_and_execute(
    question: str,
    routing_hint: str = None,
) -> Dict[str, Any]:
    """
    Route query and execute against the appropriate service.
    Returns unified result dict consumed by query_routes.py.
    """
    from main.services.rag_service import get_query_engine
    from main.services.sql_service import execute_sql_query
    from main.mcp.mcp_client import query_mcp_tools

    route = classify_query(question, routing_hint)
    logger.info(f"Query routed to: [{route.upper()}] — '{question[:80]}...'")

    result: Dict[str, Any] = {
        "routing_used": route,
        "answer":       "",
        "source_nodes": [],
        "sql_query":    None,
    }

    # ── RAG ──────────────────────────────────────────────────────
    if route == "rag":
        qe       = get_query_engine(similarity_top_k=4)
        response = qe.query(question)
        result["answer"] = str(response)
        if hasattr(response, "source_nodes"):
            result["source_nodes"] = _extract_source_nodes(response.source_nodes)

    # ── SQL ──────────────────────────────────────────────────────
    elif route == "sql":
        sql_result      = execute_sql_query(question)
        result["answer"]    = sql_result["answer"]
        result["sql_query"] = sql_result.get("sql_query")

    # ── HYBRID ───────────────────────────────────────────────────
    elif route == "hybrid":
        qe           = get_query_engine(similarity_top_k=4)
        rag_response = qe.query(question)
        rag_answer   = str(rag_response)
        rag_nodes    = []
        if hasattr(rag_response, "source_nodes"):
            rag_nodes = _extract_source_nodes(rag_response.source_nodes)

        sql_result = execute_sql_query(question)
        sql_answer = sql_result.get("answer", "")

        merged = _merge_rag_sql(question, rag_answer, sql_answer)
        result["answer"]       = merged
        result["source_nodes"] = rag_nodes
        result["sql_query"]    = sql_result.get("sql_query")

    # ── MCP ──────────────────────────────────────────────────────
    elif route == "mcp":
        try:
            mcp_answer     = await query_mcp_tools(question)
            result["answer"] = mcp_answer
        except Exception as e:
            logger.warning(f"MCP call failed ({e}), falling back to RAG")
            qe             = get_query_engine(similarity_top_k=4)
            response       = qe.query(question)
            result["answer"]       = str(response)
            result["routing_used"] = "rag"
            if hasattr(response, "source_nodes"):
                result["source_nodes"] = _extract_source_nodes(response.source_nodes)

    return result


def _extract_source_nodes(source_nodes) -> list:
    """Convert LlamaIndex source nodes to serialisable dicts."""
    nodes = []
    for node in source_nodes:
        nodes.append({
            "chunk_id": getattr(node, "node_id", ""),
            "text":     getattr(node, "text", ""),
            "score":    float(getattr(node, "score", 0.0) or 0.0),
            "source":   node.metadata.get("file_path") if node.metadata else None,
            "metadata": node.metadata or {},
        })
    return nodes


def _merge_rag_sql(question: str, rag_answer: str, sql_answer: str) -> str:
    """Synthesise RAG + SQL answers into one coherent hybrid response."""
    from llama_index.core.settings import Settings

    if not sql_answer or "failed" in sql_answer.lower():
        return rag_answer
    if not rag_answer:
        return sql_answer

    try:
        llm    = Settings.llm
        prompt = (
            f'You are a financial analyst assistant.\n'
            f'A user asked: "{question}"\n\n'
            f'Narrative context from documents:\n{rag_answer}\n\n'
            f'Structured data from financial database:\n{sql_answer}\n\n'
            f'Synthesise both into a single, precise, well-attributed answer. '
            f'Cite numbers from the structured data and reference the document '
            f'narrative where relevant.'
        )
        return str(llm.complete(prompt))
    except Exception as e:
        logger.error(f"LLM merge failed: {e}")
        return f"{rag_answer}\n\n--- Structured Data ---\n{sql_answer}"