"""
app/orchestration/nodes/router.py

Router (§3 roster #2) — deterministic, no LLM call, always runs. Two
independent pure functions live here, both "the same category of
decision: deterministic, auditable, no LLM call needed" (§6.1):

  1. route_by_category() — computes retrieval_mode from category +
     severity_initial. Used by router_node (the actual graph node,
     which writes retrieval_mode to state) right after classify_node.
  2. decide_action() — §6.1's literal escalation-decision pseudocode,
     used by graph.py's conditional edge after reflect_node. Not a graph
     node itself — graph.py calls it directly when building that edge.

Category -> retrieval_mode mapping (not spelled out verbatim anywhere in
Blueprint.md — filled in here, not left implicit, reasoned from §3's
roster "Always runs?" column + §13's traffic-percentage table):
  - out_of_scope -> None (not a "refusal" string — state.py's own
    `retrieval_mode: Literal["RAG","SQL","Hybrid","Critical"] | None`
    contract has no slot for a 5th value, and graph.py's conditional
    edge already reads `category` directly to decide the refusal path,
    so retrieval_mode doesn't need to encode that decision too).
    No retrieval agent should ever run for an out-of-scope query.
  - severity_initial == "Critical" always overrides to "Critical" mode
    regardless of category — matches §11's routing (Critical takes the
    same parallel-fan-out path as Hybrid, plus triggers incident_severity)
    and §13's Critical-path latency estimate being its own row, not
    folded into a specific category.
  - "billing" -> "SQL": a billing question is fundamentally about this
    customer's own account/subscription data, not product documentation.
  - "incident"/"security" -> "Hybrid": these plausibly need both
    documentation (troubleshooting steps, security procedures) and
    account-specific context (this customer's own tickets/incidents) —
    matches Account Validation's "SQL/Hybrid/Critical" and Documentation
    Retrieval's "RAG/Hybrid/Critical" roster entries, both covering these.
  - "usage"/"integration" -> "RAG": pure documentation questions.

Stage 6 wires all four real branches in graph.py: "RAG" -> doc_retrieval_node
alone, "SQL" -> account_validation_node alone, "Hybrid"/"Critical" -> both
concurrently via LangGraph's Send API (genuine parallel fan-out, not two
sequential calls).
"""

from __future__ import annotations

from app.schemas.state import SupportGraphState

RetrievalMode = str | None  # "RAG" | "SQL" | "Hybrid" | "Critical" | None (out_of_scope)


def route_by_category(category: str | None, severity_initial: str | None) -> RetrievalMode:
    if category == "out_of_scope":
        return None
    if severity_initial == "Critical":
        return "Critical"
    if category == "billing":
        return "SQL"
    if category in ("incident", "security"):
        return "Hybrid"
    return "RAG"  # usage, integration


def should_escalate_for_explicit_request(explicit_human_request: bool) -> bool:
    """README §5's "Explicit request for human support" escalation trigger
    — one of five listed triggers, and the only one with zero relationship
    to severity/confidence_tier at all. decide_action() only ever sees
    (severity, confidence_tier), so this can't be folded into its matrix
    without changing that function's signature and its existing exhaustive
    tests — deliberately not done here. Instead this is its own named,
    independently-testable predicate, checked by graph.py's
    _route_after_classify immediately alongside the existing out_of_scope
    check (§31 Layer A) — a literal "connect me with a human" request
    bypasses doc_retrieval/reflect entirely, the same short-circuit shape
    out_of_scope already uses, just routing to escalate_node instead of
    the fixed refusal."""
    return explicit_human_request


def _needs_incident_severity(category: str | None, retrieval_mode: str | None) -> bool:
    """§11's literal SEVCHECK diamond condition: category in
    (incident, security), or retrieval_mode == "Critical". Implemented as
    its own named, independently-testable predicate — not inlined
    redundantly in graph.py's three post-retrieval conditional edges
    (doc_retrieval_node's, account_validation_node's, and
    incident_severity_node's own).

    Side observation, not relied upon: given route_by_category's current
    mapping above, this condition is provably equivalent to "retrieval_mode
    is Hybrid or Critical" — Hybrid only ever results from category in
    (incident, security), and Critical mode's own name already satisfies
    the condition directly. The literal, general form is still what's
    implemented here, so a future change to route_by_category's mapping
    can't silently break SEVCHECK's real intent."""
    return category in ("incident", "security") or retrieval_mode == "Critical"


def resolve_effective_severity(severity_final: str | None, severity_initial: str | None) -> str | None:
    """The one place the `severity_final if severity_final else severity_initial`
    fallback (deviation F) lives. graph.py's post-reflect conditional edge,
    escalate_node, and respond_node's flagged_for_review computation all call
    this instead of re-deriving the expression independently, so the three
    call sites can't silently drift apart."""
    return severity_final if severity_final else severity_initial


def decide_action(severity: str | None, confidence_tier: str | None) -> tuple[str, bool]:
    """§6.1's escalation decision matrix, verbatim. Callers (graph.py's
    conditional edge) are responsible for resolving `severity` to
    `severity_final if severity_final else severity_initial` BEFORE
    calling this — this function stays a pure 2-argument match of the
    blueprint's literal pseudocode, not where that fallback lives."""
    if severity == "Critical":
        return "escalate", False
    if confidence_tier == "Low":
        return "escalate", False
    if confidence_tier == "Medium" or severity == "High":
        return "respond", True  # flagged_for_review
    return "respond", False


async def router_node(state: SupportGraphState) -> dict:
    """Reads: category, severity_initial. Writes: retrieval_mode (§4)."""
    retrieval_mode = route_by_category(state.get("category"), state.get("severity_initial"))
    return {"retrieval_mode": retrieval_mode}
