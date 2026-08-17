"""
app/api/routes_metrics.py

GET /metrics — §17/§18. Data-sourcing split, investigated (not assumed
"everything from Langfuse") during Stage 8 planning:
  - P50/P95 latency + cost/ticket: Langfuse's real per-TRACE data
    (app/observability/tracing.py's safe_query_trace_metrics —
    client.api.trace.list(), filtered by `name` to the 3 terminal-node
    span names (respond/escalate/out_of_scope_refusal), which — a real,
    confirmed finding, not an assumption — resolves to whichever node ran
    LAST for a given real request, so filtering on it selects "one
    complete real request," the same intent as picking the terminal
    nodes in the first place. A real, confirmed, now-fixed bug lived
    here: an earlier version queried the "observations" metrics-
    aggregation API instead, which only ever saw the terminal spans' own
    thin-wrapper duration/cost (a few ms; no LLM call happens inside
    respond_node/escalate_node/out_of_scope_refusal_node itself) — not
    the real per-request total, which lives on OTHER node spans
    (classify/account_validation/reflect) and their nested LLM-generation
    children. client.api.trace.list() instead returns Langfuse's own
    pre-computed real trace.latency/trace.total_cost, which correctly
    sum every one of a request's descendant observations — confirmed
    directly against a real trace (see safe_query_trace_metrics()'s own
    docstring for the exact numbers). p50/p95 are computed locally here
    from the real per-trace latency values this endpoint fetches, since
    trace.list() returns raw records, not a server-side percentile.
  - Escalation rate: the local `messages` table — this Langfuse SDK
    version has no clean way to query trace-level metadata (escalation_
    flag is only ever attached as span metadata, not trace metadata),
    so the local DB is simply more practical here, not a fallback.
  - TSR/SQL-correctness/routing-accuracy/risk-accuracy/escalation-recall/
    RAGAS-style scores: none of these are live production metrics at all
    (§24: "measured via golden_50 eval") — this endpoint reports the
    single most recent app.db.models.EvaluationRun row (written by
    evaluation/calibrate_thresholds.py), `null` for all of them if no
    real eval run has happened yet.

RBAC + rate limit match §16.1's own table row for this endpoint exactly
(same as GET /conversations): support_agent|admin, 60/minute.

Caching: a short-TTL (30s) Redis cache — now routed through
app/cache/redis_cache.py's shared cache_get()/cache_set() (Stage 8's own
gap, since redis_cache.py was still an empty stub when this route was
first built; refactored once the shared module existed rather than
leaving this route's own hand-rolled Redis error handling as a second,
duplicate implementation of the same safe-wrapping logic). A Redis
outage degrades to computing the snapshot fresh every call, never a 500;
caching here is an optimization, not a dependency, same philosophy as
tracing.py's own safe_* wrappers.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.redis_cache import cache_get, cache_set
from app.db.models import EvaluationRun, Message
from app.db.session import get_db
from app.middleware.rate_limit import limiter
from app.middleware.rbac_check import require_support_or_admin
from app.observability import tracing

router = APIRouter(prefix="/metrics", tags=["metrics"])

_WINDOW_HOURS = 24
_CACHE_KEY = "metrics:snapshot"
_CACHE_TTL_SECONDS = 30

# §15's node spans that are terminal on some path through the graph — one
# request produces exactly one of these, so their combined latency
# distribution approximates whole-request latency without being diluted
# by every short intermediate node/generation sub-span.
_TERMINAL_SPAN_NAMES = ["respond", "escalate", "out_of_scope_refusal"]


def _percentile(values: list[float], pct: float) -> float:
    """Nearest-rank percentile over already-fetched real trace latencies —
    simple and deterministic, not attempting statistically precise
    interpolation; good enough for a dashboard tile. client.api.trace.
    list() aggregates at the trace level only (real per-trace records,
    not a server-side percentile query — see safe_query_trace_metrics()'s
    own docstring), so this endpoint computes p50/p95 itself."""
    ordered = sorted(values)
    index = min(int(pct / 100 * len(ordered)), len(ordered) - 1)
    return ordered[index]


class LatencyMs(BaseModel):
    p50: float | None = None
    p95: float | None = None


class MetricsResponse(BaseModel):
    window: dict[str, str]
    latency_ms: LatencyMs
    cost_per_ticket_usd: float | None = None
    escalation_rate: float | None = None
    last_eval_run_at: str | None = None
    task_success_rate: float | None = None
    sql_correctness: float | None = None
    query_routing_accuracy: float | None = None
    risk_classification_accuracy: float | None = None
    escalation_recall: float | None = None
    faithfulness: float | None = None
    answer_relevance: float | None = None
    context_precision: float | None = None
    context_recall: float | None = None


@router.get("", response_model=MetricsResponse)
@limiter.limit("60/minute")
async def get_metrics(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_support_or_admin),
) -> MetricsResponse:
    cached = await cache_get(_CACHE_KEY)
    if cached:
        return MetricsResponse.model_validate_json(cached)

    now = datetime.now(timezone.utc)
    window_start = now - timedelta(hours=_WINDOW_HOURS)

    trace_records = tracing.safe_query_trace_metrics(
        names=_TERMINAL_SPAN_NAMES, from_timestamp=window_start, to_timestamp=now
    )

    if trace_records:
        latencies_ms = [record["latency"] * 1000 for record in trace_records]  # trace.latency is seconds
        p50_latency = _percentile(latencies_ms, 50)
        p95_latency = _percentile(latencies_ms, 95)
        sum_cost = sum(record["total_cost"] for record in trace_records)
    else:
        p50_latency = None
        p95_latency = None
        sum_cost = None

    ticket_count_result = await db.execute(
        select(func.count())
        .select_from(Message)
        .where(Message.role == "assistant", Message.created_at >= window_start)
    )
    ticket_count = ticket_count_result.scalar_one()

    escalation_result = await db.execute(
        select(
            func.count().filter(Message.escalation_flag.is_(True)),
            func.count(),
        )
        .select_from(Message)
        .where(Message.role == "assistant", Message.created_at >= window_start)
    )
    escalated_count, total_count = escalation_result.one()

    eval_result = await db.execute(select(EvaluationRun).order_by(EvaluationRun.run_at.desc()).limit(1))
    latest_eval = eval_result.scalar_one_or_none()

    cost_per_ticket = (sum_cost / ticket_count) if (sum_cost is not None and ticket_count) else None

    response = MetricsResponse(
        window={"from": window_start.isoformat(), "to": now.isoformat()},
        latency_ms=LatencyMs(p50=p50_latency, p95=p95_latency),
        cost_per_ticket_usd=cost_per_ticket,
        escalation_rate=(escalated_count / total_count) if total_count else None,
        last_eval_run_at=latest_eval.run_at.isoformat() if latest_eval else None,
        task_success_rate=latest_eval.task_success_rate if latest_eval else None,
        sql_correctness=latest_eval.sql_correctness if latest_eval else None,
        query_routing_accuracy=latest_eval.query_routing_accuracy if latest_eval else None,
        risk_classification_accuracy=latest_eval.risk_classification_accuracy if latest_eval else None,
        escalation_recall=latest_eval.escalation_recall if latest_eval else None,
        faithfulness=latest_eval.faithfulness if latest_eval else None,
        answer_relevance=latest_eval.answer_relevance if latest_eval else None,
        context_precision=latest_eval.context_precision if latest_eval else None,
        context_recall=latest_eval.context_recall if latest_eval else None,
    )

    await cache_set(_CACHE_KEY, response.model_dump_json(), ttl_seconds=_CACHE_TTL_SECONDS)

    return response
