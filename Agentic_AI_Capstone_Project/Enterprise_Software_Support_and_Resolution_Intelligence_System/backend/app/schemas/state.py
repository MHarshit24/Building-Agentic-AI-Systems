"""
app/schemas/state.py

Shared LangGraph state contract for the Enterprise Software Support &
Resolution Intelligence System.

Convention (§4 / §2.3):
  - The orchestrator is deterministic code, not an LLM agent.
  - Nodes return *only* the fields they own; they never read-modify-write
    the full state object.
  - Fields typed Annotated[list, operator.add] are *accumulators*: nodes
    must return only the **new / partial items** they produced in the
    current step.  LangGraph merges them automatically via operator.add
    (list concatenation).  Never return the full accumulated list from a
    node — that would double-count on every update.
  - Fields without Annotated are last-write-wins; nodes may overwrite them
    freely.
"""

from __future__ import annotations

import operator
from typing import Annotated, Literal

from typing_extensions import TypedDict

# NOT behind `if TYPE_CHECKING:` despite `from __future__ import annotations`
# making every annotation a lazy string: LangGraph's StateGraph resolves this
# TypedDict's fields via typing.get_type_hints() at graph-construction time
# (app/orchestration/graph.py's build_graph()), which evaluates these
# forward-referenced names against this module's *real* runtime namespace.
# A TYPE_CHECKING-only import satisfies static type checkers but leaves
# RetrievedChunk etc. undefined at runtime, so get_type_hints() raises
# NameError the moment anything actually builds the graph. No circular
# import risk: agent_contracts.py does not import this module.
from app.schemas.agent_contracts import (
    RetrievedChunk,
    RetrievedDiagram,
    RetrievedTable,
    SourceRef,
)


class SupportGraphState(TypedDict):
    # ── Input / conversation context ──────────────────────────────────────────
    query: str
    chat_history: list[dict]          # full history passed in; not accumulated across nodes
    customer_id: int | None
    handled_by_user_id: int           # authenticated support agent — audit trail (§16)

    # ── Classification output ─────────────────────────────────────────────────
    category: Literal["usage", "integration", "billing", "incident", "security", "out_of_scope"] | None
    conversation_id: str
    severity_initial: Literal["Low", "Medium", "High", "Critical"] | None
    severity_final: Literal["Low", "Medium", "High", "Critical"] | None
    retrieval_mode: Literal["RAG", "SQL", "Hybrid", "Critical"] | None
    explicit_human_request: bool  # README §5 escalation trigger — set by classify_node, read by graph.py's post-classify short-circuit

    # ── Retrieval results (§4, §5, §11) ──────────────────────────────────────
    # Plain last-write-wins lists.  On the reflect→doc_retrieval loop-back
    # (§5) doc_retrieval fully *replaces* the previous result set — it was
    # already judged ungrounded/insufficient by reflect_node, so accumulating
    # stale, rejected results would pollute the final context.
    retrieved_chunks: list[RetrievedChunk]
    retrieved_tables: list[RetrievedTable]
    retrieved_diagrams: list[RetrievedDiagram]
    sql_results: list[dict]
    # account_validation_node's own narrative, ALWAYS written when it runs —
    # unlike final_answer below, which it only writes directly in SQL-alone
    # mode (the "sole responder" case). Frontend integration pass bugfix:
    # in Hybrid/Critical mode, account_validation_node used to compute this
    # exact narrative (a real LLM call, not free) and then discard it
    # entirely, since writing it straight to final_answer there would be a
    # concurrent-write conflict with doc_retrieval_node's own final_answer
    # write in the same LangGraph superstep. Keeping it in this separate,
    # single-writer field lets reflect_node's own merge step (see reflect.py)
    # fold it into the real final_answer without touching the concurrent-
    # write-safety property final_answer itself relies on.
    account_narrative: str | None
    # Real bug fix, frontend QA: doc_retrieval_node and account_validation_
    # node each already compute their own evidence_sufficient verdict
    # internally (DocRetrievalOutput/AccountValidationOutput) but never
    # exposed it to state — so when they run CONCURRENTLY (genuine Hybrid/
    # Critical fan-out, not the sequential SQL-alone-then-retry case
    # account_narrative's own docstring above already covers), neither
    # node can see the other's verdict while drafting its own text. One
    # side correctly, honestly says "I don't have enough information" from
    # its own narrow view (e.g. doc_retrieval has no account context; or
    # account_validation found no matching incident) while the OTHER side
    # genuinely does have a real answer — reflect.py's merge step used to
    # just concatenate them, producing a self-contradictory final answer
    # ("I don't have enough information... [real answer anyway]"). Each is
    # single-writer (doc_retrieval_node / account_validation_node
    # respectively), same "plain last-write-wins" shape as every other
    # field in this section — no concurrent-write conflict, since the two
    # nodes write different keys even when they run in the same superstep.
    doc_evidence_sufficient: bool | None
    account_evidence_sufficient: bool | None

    # ── Reflection / confidence ───────────────────────────────────────────────
    confidence_score: float | None
    confidence_tier: Literal["High", "Medium", "Low"] | None
    groundedness_flag: bool | None

    # ── Loop-count guards (§5) ────────────────────────────────────────────────
    retrieval_retry_count: int        # capped at 1 — doc_retrieval query rewrite
    reflection_loopback_count: int    # capped at 1 — reflect → doc_retrieval loop

    # ── Escalation flags ──────────────────────────────────────────────────────
    # escalation_flag is a reducer field (Stage 6) — NOT plain last-write-wins
    # like the rest of this section, despite this module's own docstring
    # convention above. Required, not stylistic: in Hybrid/Critical mode,
    # doc_retrieval_node and account_validation_node run CONCURRENTLY (same
    # LangGraph superstep) via Send. Both are wrapped in graph.py's
    # _guard_structured_output, which returns {"escalation_flag": True} on a
    # caught StructuredOutputError — if both branches failed in the same
    # request, both would write this plain key in the same step, and
    # LangGraph raises InvalidUpdateError for concurrent writes to a
    # last-value channel regardless of whether the two values agree.
    # operator.or_ is exactly the right semantics (once flagged, stays
    # flagged; concurrent flags just OR together) and is a no-op for every
    # existing single-writer call site (True or True == True, False or True
    # == True, identical to plain overwrite). Audited every other field
    # either concurrent node writes — this is the only real concurrent-write
    # collision risk in the whole state contract (see Stage 6 plan, Deviation J).
    escalation_flag: Annotated[bool, operator.or_]
    flagged_for_review: bool          # Medium-confidence, non-blocking QA queue (§6)
    notification_sent: bool           # always False from inside the graph — the real outcome is only
                                       # knowable after routes_chat.py's BackgroundTask runs, well past
                                       # graph completion (§7); Stage 7 does not change this field
    escalation_reason: str | None     # Stage 7 — escalate_node's EscalationOutput; maps to escalation_log.reason
    human_handoff_summary: str | None # Stage 7 — for the human agent, not the customer; never final_answer

    # ── Output ────────────────────────────────────────────────────────────────
    final_answer: str | None
    sources: list[SourceRef]          # assembled once by respond_node; not accumulated
    trace_id: str
