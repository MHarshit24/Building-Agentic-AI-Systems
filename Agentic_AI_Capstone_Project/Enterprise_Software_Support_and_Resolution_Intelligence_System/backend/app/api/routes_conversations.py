"""
app/api/routes_conversations.py

GET /conversations, GET /conversations/{conversation_id} — section 17/29
of Blueprint.md.

No dedicated schemas/conversations.py exists in the section 18 folder
structure, so response models are defined inline here rather than
inventing a new file outside the spec'd structure.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Conversation, ConversationStatus, Message
from app.db.session import get_db
from app.middleware.rate_limit import limiter
from app.middleware.rbac_check import require_support_or_admin

router = APIRouter(prefix="/conversations", tags=["conversations"])


class ConversationSummary(BaseModel):
    conversation_id: str
    customer_id: int
    last_message_at: str
    status: str
    escalated: bool


class ConversationListResponse(BaseModel):
    conversations: list[ConversationSummary]


class MessageOut(BaseModel):
    role: str
    content: str
    created_at: str
    confidence_tier: str | None = None
    sources: Any | None = None
    trace_id: str | None = None
    # Frontend integration pass (A3): previously only ChatResponse (the
    # just-answered turn) carried these — a reopened conversation showed a
    # stripped-down trace for every earlier turn. Now persisted per-message
    # (db/models.py Message), so history is fully populated too.
    category: str | None = None
    severity: str | None = None
    retrieval_mode: str | None = None
    confidence_score: float | None = None
    flagged_for_review: bool = False
    # escalation_flag already existed as a DB column (used server-side by
    # routes_metrics.py's escalation-rate calc) but was never surfaced here
    # — trivial to close alongside A3 since no migration is needed, and
    # ReasoningTraceDropdown/EscalationBanner need it to render correctly
    # for a REOPENED escalated conversation, not just the live turn.
    escalated: bool = False


class ConversationDetailResponse(BaseModel):
    conversation_id: str
    messages: list[MessageOut]


@router.get("", response_model=ConversationListResponse)
@limiter.limit("60/minute")
async def list_conversations(
    request: Request,
    limit: int = Query(default=50, le=100, ge=1),
    offset: int = Query(default=0, ge=0),
    include_archived: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_support_or_admin),
) -> ConversationListResponse:
    """
    Lists conversations the authenticated user has handled. Admins see
    all conversations, matching §17's "admins see all" note. Paginated
    via limit/offset — exact pagination params aren't specified in the
    blueprint, chosen as a reasonable default.

    Archived conversations are excluded by default (matching archival's
    own "declutter, not delete" intent) — pass include_archived=true to
    see them again. Never permanently hidden, just off by default.
    """
    stmt = select(Conversation).order_by(Conversation.last_message_at.desc())
    if user.get("role") != "admin":
        stmt = stmt.where(Conversation.handled_by_user_id == user["user_id"])
    if not include_archived:
        stmt = stmt.where(Conversation.status != ConversationStatus.archived)
    stmt = stmt.limit(limit).offset(offset)

    result = await db.execute(stmt)
    conversations = result.scalars().all()

    return ConversationListResponse(
        conversations=[
            ConversationSummary(
                conversation_id=c.conversation_id,
                customer_id=c.customer_id,
                last_message_at=c.last_message_at.isoformat(),
                status=c.status.value,
                escalated=(c.status.value == "escalated"),
            )
            for c in conversations
        ]
    )


@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
@limiter.limit("60/minute")
async def get_conversation(
    request: Request,
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_support_or_admin),
) -> ConversationDetailResponse:
    """
    Returns the full message thread for one conversation. Per §17/§29,
    only the assigned agent (matching handled_by_user_id) or an admin
    may view it — enforced here by role, not just authentication.

    Both "conversation doesn't exist" and "exists but not yours" return
    404, not 403 — deliberately not revealing whether a conversation_id
    exists to a user who isn't authorized to see it.
    """
    conv_result = await db.execute(
        select(Conversation).where(Conversation.conversation_id == conversation_id)
    )
    conversation = conv_result.scalar_one_or_none()

    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    if user.get("role") != "admin" and conversation.handled_by_user_id != user["user_id"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    # created_at alone is not a stable sort — see routes_chat.py's
    # _load_chat_history() for the real, confirmed reason (same-transaction
    # inserts share one Postgres transaction timestamp). message_id is the
    # real, deterministic secondary key.
    msg_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc(), Message.message_id.asc())
    )
    messages = msg_result.scalars().all()

    return ConversationDetailResponse(
        conversation_id=conversation_id,
        messages=[
            MessageOut(
                role=m.role,
                content=m.content,
                created_at=m.created_at.isoformat(),
                confidence_tier=m.confidence_tier,
                sources=m.sources_json,
                trace_id=m.trace_id,
                category=m.category,
                severity=m.severity,
                retrieval_mode=m.retrieval_mode,
                confidence_score=m.confidence_score,
                flagged_for_review=m.flagged_for_review,
                escalated=m.escalation_flag,
            )
            for m in messages
        ],
    )


async def _get_conversation_or_404(db: AsyncSession, conversation_id: str, user: dict) -> Conversation:
    result = await db.execute(select(Conversation).where(Conversation.conversation_id == conversation_id))
    conversation = result.scalar_one_or_none()

    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    if user.get("role") != "admin" and conversation.handled_by_user_id != user["user_id"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return conversation


def _to_summary(conversation: Conversation) -> ConversationSummary:
    return ConversationSummary(
        conversation_id=conversation.conversation_id,
        customer_id=conversation.customer_id,
        last_message_at=conversation.last_message_at.isoformat(),
        status=conversation.status.value,
        escalated=(conversation.status == ConversationStatus.escalated),
    )


@router.post("/{conversation_id}/archive", response_model=ConversationSummary)
@limiter.limit("10/minute")
async def archive_conversation(
    request: Request,
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_support_or_admin),
) -> ConversationSummary:
    """
    Reversible archival, not deletion — matches this project's soft-
    retire convention (see ConversationStatus.archived's own docstring
    for why a hard delete would orphan EscalationLog.trace_id references).
    Same assigned-agent-or-admin access rule as get_conversation, argued
    explicitly (production-readiness gap analysis, deletion item 2): this
    is the same access boundary an agent already has to read their own
    conversation, and archiving is fully reversible, so a stricter
    boundary than read access has no real security benefit here.
    """
    conversation = await _get_conversation_or_404(db, conversation_id, user)
    conversation.status = ConversationStatus.archived
    await db.commit()
    await db.refresh(conversation)
    return _to_summary(conversation)


@router.post("/{conversation_id}/unarchive", response_model=ConversationSummary)
@limiter.limit("10/minute")
async def unarchive_conversation(
    request: Request,
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_support_or_admin),
) -> ConversationSummary:
    """Restores an archived conversation to `open`. Rejects unarchiving a
    conversation that wasn't archived in the first place (e.g. `closed`
    for a real, different reason) — this endpoint only ever undoes this
    endpoint's own sibling, not some other status transition."""
    conversation = await _get_conversation_or_404(db, conversation_id, user)

    if conversation.status != ConversationStatus.archived:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Conversation is not archived")

    conversation.status = ConversationStatus.open
    await db.commit()
    await db.refresh(conversation)
    return _to_summary(conversation)