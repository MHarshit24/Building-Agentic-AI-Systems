"""
app/schemas/agent_contracts.py

Two families of Pydantic models, both defined here per §4/§39.3 of
Blueprint.md:

  1. Retrieval-result / citation types (RetrievedChunk, RetrievedTable,
     RetrievedDiagram, SourceRef) — imported by app/schemas/state.py under
     TYPE_CHECKING. These aren't LLM output schemas; they're the shape
     doc_retrieval_node populates state's accumulator fields with, and
     the shape respond_node reads back out to build `sources`.

  2. Per-agent LLM output schemas (§39.3) — the literal Pydantic shape
     every call_llm_structured() call validates against. Classification,
     Documentation Retrieval, Reflection (Stage 5), Account Validation,
     Incident Severity (Stage 6), Escalation Manager (Stage 7) are all
     defined here.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Retrieval-result / citation types (§4, §27's metadata fields)
# ---------------------------------------------------------------------------
# All three share the same field set deliberately — they differ only in
# which asset table they came from (already implicit in which one of the
# three state.py accumulator fields they're appended to), not in shape.
# `cited` defaults to False and is set True by doc_retrieval_node itself,
# for whichever items match the LLM's own cited_source_ids — respond_node
# later filters on this flag to build `sources` (see doc_retrieval.py's
# docstring for the full reasoning on why this lives here instead of a
# new state.py field).


class RetrievedChunk(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_id: int
    text: str
    source_document: str | None
    section_header: str | None
    page_number: int | None
    product_version: str | None
    category: str | None
    score: float
    cited: bool = False


class RetrievedTable(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_id: int
    text: str
    source_document: str | None
    section_header: str | None
    page_number: int | None
    product_version: str | None
    category: str | None
    score: float
    cited: bool = False


class RetrievedDiagram(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_id: int
    text: str
    source_document: str | None
    section_header: str | None
    page_number: int | None
    product_version: str | None
    category: str | None
    score: float
    cited: bool = False


class SourceRef(BaseModel):
    """What respond_node actually puts in the POST /chat response's
    `sources` list (§17) — one entry per cited retrieved item.

    type="sql" (Stage 6, Deviation L) uses `table`/`record_id` instead of
    the chunk/table/diagram fields, matching §17's own literal example
    ({"type": "sql", "table": "incident_logs", "record_id": 1}) exactly.

    Frontend integration pass correction: sql_results rows USED TO have no
    `cited`-subset filter at all (every fetched row became a source
    unconditionally) — that read reasonably from §14 point 1 ("SQL facts
    are grounded by construction") but produced real citation noise once
    actually used: a single-customer question could cite a dozen+ region-
    wide incident_logs rows the narrative never even mentioned, since
    get_incidents() matches by region, not by account (see sql_tools/
    queries.py's own docstring). "Grounded by construction" is true of
    each fact's provenance, but says nothing about whether the narrative
    actually relied on that specific row — respond_node now filters SQL
    sources by the same `cited` mechanism chunks/tables/diagrams already
    used, via account_validation_node's own cited_record_ids output
    (mirrors DocRetrievalOutput.cited_source_ids exactly)."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["chunk", "table", "diagram", "sql"]
    source_document: str | None = None
    section_header: str | None = None
    page_number: int | None = None
    table: str | None = None
    record_id: int | None = None


# ---------------------------------------------------------------------------
# Per-agent LLM output schemas (§39.3) — enforced via call_llm_structured()
# ---------------------------------------------------------------------------


class ClassificationOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: Literal["usage", "integration", "billing", "incident", "security", "out_of_scope"]
    severity_initial: Literal["Low", "Medium", "High", "Critical"]
    explicit_human_request: bool = Field(
        default=False,
        description="True only when the user literally, directly asks to speak with or be "
        "connected to a human support agent — never implied by severity, frustration, or "
        "category alone. Independent of the severity/confidence_tier-driven escalation matrix "
        "(§6.1) — this is its own unconditional escalation trigger (README §5, 'Explicit "
        "request for human support'). Defaults False (not required in every raw JSON payload "
        "validated here) so existing fixtures/tests that predate this field keep validating; "
        "Azure's strict structured-output mode still forces the real model to return it on "
        "every real call regardless of this Python-level default (see "
        "structured_output.py's _make_strict_compatible()).",
    )


class DocRetrievalOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    draft_answer: str
    cited_source_ids: list[str] = Field(
        description="Subset of the candidate source IDs shown in the prompt that draft_answer actually relies on"
    )
    evidence_sufficient: bool
    rewritten_query: str | None = Field(
        default=None,
        description="Only when evidence_sufficient is false: a rephrased/improved search query to retry "
        "retrieval with. Null when evidence_sufficient is true. Produced in the same call rather than a "
        "separate query-rewriting step, per §2.3.",
    )


class ReflectionOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confidence_score: float
    groundedness_flag: bool
    confidence_tier: Literal["High", "Medium", "Low"]


class AccountValidationOutput(BaseModel):
    """Deviates from §39.3's literal `{sql_results: list[dict], narrative:
    str}` (Stage 6 Deviation H) — same reasoning already established for
    DocRetrievalOutput: the LLM never re-emits fetched evidence verbatim.
    `sql_results` is populated directly in Python from get_customer/
    get_tickets/get_incidents' own return values before the LLM ever runs;
    asking a reasoning_effort="minimal" call to faithfully transcribe
    several rows of JSON back out as part of its own JSON response is a
    real, avoidable transcription-error risk. The LLM only ever narrates
    over pre-fetched context."""

    model_config = ConfigDict(extra="forbid")

    narrative: str
    cited_record_ids: list[str] = Field(
        default_factory=list,
        description="Subset of the candidate record IDs shown in the prompt (each evidence line is "
        "labeled [table_id], e.g. [customers_5], [support_tickets_42], [incident_logs_7]) that narrative "
        "actually relies on. Mirrors DocRetrievalOutput.cited_source_ids exactly — same reasoning: a "
        "record being fetched doesn't mean the narrative discussed it (get_incidents() in particular "
        "returns every incident affecting the customer's region, most of which a given answer won't "
        "touch). Defaults to an empty list (same ClassificationOutput.explicit_human_request precedent) "
        "so pre-existing fixtures/tests that predate this field keep validating; Azure's strict "
        "structured-output mode still forces the real model to return it on every real call.",
    )
    evidence_sufficient: bool = Field(
        default=True,
        description="Whether the fetched account data was enough to address the query — mirrors "
        "DocRetrievalOutput's own field. Usually true, since get_customer/get_tickets/get_incidents "
        "are always called unconditionally and either return real data or an empty list; false "
        "mainly covers a customer_id with no matching customer row at all.",
    )


class IncidentSeverityOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    severity_final: Literal["Low", "Medium", "High", "Critical"]
    severity_reasoning: str = Field(
        description="Not persisted to state — state.py's own SupportGraphState has no "
        "severity_reasoning field (§4's actual contract, checked directly, not assumed from §39.3's "
        "roster prose). Logged via structured_logger for traceability instead, mirroring Stage 5's "
        "draft_answer/cited_source_ids precedent for LLM output with no dedicated state slot.",
    )


class EscalationOutput(BaseModel):
    """Unlike severity_reasoning above, both fields here DO get persisted
    to state (escalation_reason, human_handoff_summary — Stage 7) — this
    node's caller (routes_chat.py) genuinely needs them after
    graph.ainvoke() returns, to build the escalation_log row and the
    notification email. Not customer-facing: escalate_node's own
    final_answer (what the chat UI shows) stays Stage 5's fixed/templated
    text, deliberately not replaced by this LLM's prose — see escalate.py's
    own docstring for why."""

    model_config = ConfigDict(extra="forbid")

    escalation_reason: str = Field(
        description="Internal/audit string — why the system escalated. Maps directly to "
        "escalation_log.reason (§21)."
    )
    human_handoff_summary: str = Field(
        description="Written for the human agent picking up this ticket (§13: 'drafting a handoff "
        "summary'), not for the customer — used as the notification email body / ticket_context_json, "
        "never as final_answer."
    )
