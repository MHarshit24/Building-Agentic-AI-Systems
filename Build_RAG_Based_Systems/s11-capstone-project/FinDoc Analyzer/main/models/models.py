"""
FinDoc Analyzer — Pydantic models for all API endpoints.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ══════════════════════════════════════════════════════
# INGEST  (/api/v1/ingest)
# ══════════════════════════════════════════════════════

class IngestResponse(BaseModel):
    message: str
    documents_indexed: int
    chunks_created: int
    document_id: Optional[str] = None
    file_name: Optional[str] = None
    file_type: Optional[str] = None


# ══════════════════════════════════════════════════════
# QUERY  (/api/v1/query)
# ══════════════════════════════════════════════════════

class QueryRequest(BaseModel):
    question: str = Field(..., description="Natural language financial question")
    user_email: Optional[str] = Field(None, description="User email for handoff context")
    routing_hint: Optional[str] = Field(
        None,
        description="Optional routing hint: 'rag', 'sql', 'hybrid', or 'mcp'",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "question": "What was the revenue growth over the last three years?",
                    "user_email": "analyst@example.com",
                },
                {
                    "question": "What are the key risks mentioned in the annual report?",
                    "user_email": "auditor@example.com",
                },
            ]
        }
    }


class SourceNode(BaseModel):
    chunk_id: str
    text: str
    score: float
    source: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class QueryResponse(BaseModel):
    question: str
    answer: str
    routing_used: str                           # "rag" | "sql" | "hybrid" | "mcp"
    source_nodes: List[SourceNode] = []
    sql_query: Optional[str] = None             # populated for sql/hybrid routes
    validation_results: Optional[Dict[str, Any]] = None
    handoff_triggered: bool = False
    handoff_reference_id: Optional[str] = None
    trace_id: Optional[str] = None


# ══════════════════════════════════════════════════════
# EVALUATE  (/api/v1/evaluate)
# ══════════════════════════════════════════════════════

class SLOMetrics(BaseModel):
    total_queries_evaluated: int
    avg_faithfulness: Optional[float] = None
    avg_relevance: Optional[float] = None
    avg_latency_ms: Optional[float] = None
    routing_distribution: Dict[str, int] = {}
    slo_passed: bool = False
    slo_details: Dict[str, Any] = {}


class EvaluateResponse(BaseModel):
    status: str
    metrics: SLOMetrics
    evaluation_dataset_size: int
    langfuse_enabled: bool
    message: str


# ══════════════════════════════════════════════════════
# HANDOFF  (/api/v1/handoff)
# ══════════════════════════════════════════════════════

class HandoffRequest(BaseModel):
    question: str
    answer: str
    user_email: Optional[str] = None
    reason: Optional[str] = Field(None, description="Reason for manual escalation")
    session_id: Optional[str] = None
    source_nodes: Optional[List[SourceNode]] = []
    evaluation_scores: Optional[Dict[str, Any]] = {}

    model_config = {
        "json_schema_extra": {
            "example": {
                "question": "Explain the off-balance sheet liabilities in the 2023 annual report",
                "answer": "I am not confident in my answer.",
                "user_email": "analyst@firm.com",
                "reason": "Complex accounting question requiring expert review",
            }
        }
    }


class HandoffResponse(BaseModel):
    reference_id: str
    status: str
    message: str
    email_sent: bool
    timestamp_utc: str


# ══════════════════════════════════════════════════════
# HEALTH  (/api/v1/health)
# ══════════════════════════════════════════════════════

class ComponentStatus(BaseModel):
    status: str          # "ok" | "error" | "disabled"
    detail: Optional[str] = None


class HealthResponse(BaseModel):
    status: str          # "healthy" | "degraded" | "unhealthy"
    service: str
    version: str
    components: Dict[str, ComponentStatus]
