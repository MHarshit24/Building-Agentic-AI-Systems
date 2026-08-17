"""
app/db/models.py

SQLAlchemy ORM models managed by Alembic for this project.

customers, support_tickets, incident_logs, knowledge_article_usage
  — the four course-specified tables (§21, §22.2 of Blueprint.md).
  Created BY Alembic from the verbatim DDL in
  capstone_software_support_dataset.md Part 2 — they are NOT pre-existing
  and are NOT excluded from autogenerate (that earlier exclusion in
  alembic/env.py was a false premise, reversed in §22.2).

document_versions, ingested_assets, chunks, tables (TableAsset),
images, diagram_graphs (DiagramGraphRow), ingestion_jobs
  — this project's own ingestion-pipeline tables (§21, §8.3). Fully
  Alembic-managed from the start, never excluded.

Later stages will add: escalation_log, notification_log (see §21).
"""

from __future__ import annotations

import enum
from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    Computed,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Text,
    JSON,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Project-wide declarative base.  All models that Alembic manages must
    inherit from this class so they are included in its metadata."""
    pass


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class UserRole(str, enum.Enum):
    """Roles per §16 — exactly two, no more."""
    support_agent = "support_agent"
    admin = "admin"


class ConversationStatus(str, enum.Enum):
    """Lifecycle status of a conversation per §38.

    archived — added for conversation-deletion item 2 (production-
    readiness gap analysis). A reversible, default-hidden state, not a
    delete: EscalationLog.trace_id references Message rows by a plain
    string match (no FK), so hard-deleting a Message would silently
    orphan any escalation record pointing at it — the same soft-retire
    discipline as everywhere else in this schema.
    """
    open = "open"
    in_progress = "in_progress"
    resolved = "resolved"
    escalated = "escalated"
    closed = "closed"
    archived = "archived"


# ---------------------------------------------------------------------------
# User model  (§16, §21)
# ---------------------------------------------------------------------------

class User(Base):
    """Support agents and admins who sign into the system.

    Columns per §16:
      user_id        — surrogate primary key (auto-incrementing integer)
      email          — unique login identifier, never returned in responses
      password_hash  — bcrypt hash via app/auth/security.py; raw password
                       is NEVER stored, logged, or returned
      role           — support_agent | admin (enforced as a PG ENUM)
      created_at     — UTC timestamp set on INSERT
      last_login_at  — UTC timestamp updated on each successful login
                       (nullable until the first login after account creation)
      is_active      — soft-retire flag (§21/§22 convention, same shape as
                       IngestedAsset.is_active) — set False to deactivate
                       an account; never hard-deleted
    """

    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
    )

    user_id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
        comment="Surrogate PK; used as handled_by_user_id in the graph state",
    )
    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        comment="Login identifier — unique, case-insensitive in practice",
    )
    password_hash: Mapped[str] = mapped_column(
        String(72),   # bcrypt output is always 60 chars; 72 gives comfortable headroom
        nullable=False,
        comment="bcrypt hash only — raw password is never stored",
    )
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", create_constraint=True),
        nullable=False,
        comment="support_agent or admin — enforced at DB level",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Row creation timestamp (UTC)",
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
        comment="Updated on each successful login; NULL until first login",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
        comment="Soft-retire flag (§21/§22 convention) — set False to deactivate an account, never hard-deleted",
    )

    def __repr__(self) -> str:
        return f"<User id={self.user_id} email={self.email!r} role={self.role}>"


class PasswordResetToken(Base):
    """Single-use, time-limited password reset token (production-readiness
    gap analysis, item B.4). The raw token is sent to the user by email and
    never stored — only its SHA-256 digest is persisted, matching
    password_hash's "never store the raw secret" principle. A plain fast
    hash (not bcrypt) is deliberate here: the token is a high-entropy
    random value, not a low-entropy human password, so bcrypt's
    slow-by-design cost adds latency with no security benefit.

    used_at is set (not deleted) on redemption — same soft-retire
    discipline as the rest of this schema; a used/expired token remains
    as an audit record rather than vanishing.
    """

    __tablename__ = "password_reset_tokens"

    token_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id"),
        nullable=False,
        comment="References users.user_id this token was issued for",
    )
    token_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        comment="sha256 hex digest of the raw token; the raw token itself is never stored",
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Token becomes unusable after this timestamp",
    )
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
        comment="Set once the token is redeemed; NULL means still unused",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return f"<PasswordResetToken id={self.token_id} user_id={self.user_id} used={self.used_at is not None}>"


# ---------------------------------------------------------------------------
# Conversation model  (§21, §29)
# ---------------------------------------------------------------------------

class Conversation(Base):
    """
    Persists every conversation turn, tied to customer_id and handled_by_user_id.
    """
    __tablename__ = "conversations"

    conversation_id: Mapped[str] = mapped_column(
        String(255),
        primary_key=True,
        comment="Unique conversation identifier (UUID string)",
    )
    customer_id: Mapped[int] = mapped_column(
        nullable=False,
        comment="References pre-existing customers table by ID, but NO foreign key constraint",
    )
    handled_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id"),
        nullable=False,
        comment="References user_id of the support agent handling this conversation",
    )
    status: Mapped[ConversationStatus] = mapped_column(
        Enum(ConversationStatus, name="conversation_status", create_constraint=True),
        nullable=False,
        comment="Status of the conversation per §38 — enforced at DB level",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="UTC timestamp when the conversation was started",
    )
    last_message_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
        comment="UTC timestamp when the last message was sent/received",
    )

    def __repr__(self) -> str:
        return f"<Conversation id={self.conversation_id!r} customer_id={self.customer_id} handled_by={self.handled_by_user_id}>"


# ---------------------------------------------------------------------------
# Message model  (§21, §29)
# ---------------------------------------------------------------------------

class Message(Base):
    """
    Persists individual turns/messages within a conversation.
    """
    __tablename__ = "messages"

    message_id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
        comment="Surrogate PK for messages",
    )
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.conversation_id"),
        nullable=False,
        comment="References the conversation this message belongs to",
    )
    role: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Role of the message author (e.g. user, assistant)",
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="The text content of the message",
    )
    trace_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Observability/Langfuse trace ID",
    )
    confidence_tier: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Confidence level of the response (e.g., High, Medium, Low)",
    )
    escalation_flag: Mapped[bool] = mapped_column(
        nullable=False,
        default=False,
        comment="True if this message triggered or is part of an escalation",
    )
    sources_json: Mapped[dict | list | None] = mapped_column(
        JSON,
        nullable=True,
        comment="JSON serialization of citation/sources references",
    )
    category: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Frontend integration pass: classify_node's category at the time this (assistant) message was produced — previously only returned live in ChatResponse, never persisted, so a reopened conversation couldn't show it",
    )
    severity: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Frontend integration pass: resolve_effective_severity() output for this turn — same persistence gap as category",
    )
    retrieval_mode: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Frontend integration pass: router_node's retrieval_mode for this turn (RAG/SQL/Hybrid/Critical) — same persistence gap as category",
    )
    confidence_score: Mapped[float | None] = mapped_column(
        nullable=True,
        comment="Frontend integration pass: reflect_node's blended confidence_score (0.3*retrieval_quality + 0.5*llm_self_critique + 0.2*groundedness) for this turn — confidence_tier alone was already persisted, the raw score wasn't",
    )
    flagged_for_review: Mapped[bool] = mapped_column(
        nullable=False,
        server_default=text("false"),
        comment="Frontend integration pass: router.decide_action()'s QA-sampling flag (§6.1) for this turn — previously only returned live in ChatResponse, never persisted. server_default (not just default=), since this column is added by ALTER TABLE against a messages table that already has real rows (§21's server_default convention for exactly this reason)",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="UTC timestamp when the message was created",
    )

    def __repr__(self) -> str:
        return f"<Message id={self.message_id} conversation_id={self.conversation_id!r} role={self.role!r}>"


# ---------------------------------------------------------------------------
# Course-provided data tables (§21, §22.2)
#
# Column names, types, constraints, and defaults are transcribed verbatim
# from capstone_software_support_dataset.md Part 2 — pinned, not paraphrased,
# to preserve benchmark comparability across teams. This includes the
# dataset's own asymmetry: customers/incident_logs/knowledge_article_usage
# default created_at to CURRENT_TIMESTAMP, but support_tickets.created_at
# has no default at all. Do not "fix" that inconsistency (§21).
# ---------------------------------------------------------------------------

class Customer(Base):
    """Table 1 of the course dataset."""

    __tablename__ = "customers"

    customer_id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )
    company_name: Mapped[str] = mapped_column(String(150), nullable=False)
    subscription_tier: Mapped[str | None] = mapped_column(String(50), nullable=True)
    account_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    sla_level: Mapped[str | None] = mapped_column(String(50), nullable=True)
    renewal_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    region: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=True,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    def __repr__(self) -> str:
        return f"<Customer id={self.customer_id} company_name={self.company_name!r}>"


class SupportTicket(Base):
    """Table 2 of the course dataset.

    created_at has no default (dataset asymmetry, preserved per §21) —
    the starter validation rows and any seed data must supply it explicitly.
    """

    __tablename__ = "support_tickets"

    ticket_id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )
    customer_id: Mapped[int | None] = mapped_column(
        ForeignKey("customers.customer_id", ondelete="CASCADE"),
        nullable=True,
    )
    issue_category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    severity_level: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ticket_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    assigned_team: Mapped[str | None] = mapped_column(String(100), nullable=True)
    escalation_flag: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
        server_default=text("FALSE"),
    )

    def __repr__(self) -> str:
        return f"<SupportTicket id={self.ticket_id} customer_id={self.customer_id}>"


class IncidentLog(Base):
    """Table 3 of the course dataset."""

    __tablename__ = "incident_logs"

    incident_id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )
    incident_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    severity: Mapped[str | None] = mapped_column(String(50), nullable=True)
    affected_region: Mapped[str | None] = mapped_column(String(100), nullable=True)
    start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    resolution_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    root_cause: Mapped[str | None] = mapped_column(Text, nullable=True)
    escalation_flag: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
        server_default=text("FALSE"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=True,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    def __repr__(self) -> str:
        return f"<IncidentLog id={self.incident_id} incident_type={self.incident_type!r}>"


class KnowledgeArticleUsage(Base):
    """Table 4 of the course dataset."""

    __tablename__ = "knowledge_article_usage"

    article_id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )
    article_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    product_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_updated: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    known_issue_flag: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    internal_confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=True,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    def __repr__(self) -> str:
        return f"<KnowledgeArticleUsage id={self.article_id} article_title={self.article_title!r}>"


# ---------------------------------------------------------------------------
# Ingestion pipeline tables (§21, §8.3) — this project's own tables, not
# course-external, so they follow the User/Conversation/Message convention
# (NOT NULL on genuinely essential columns, server_default=func.now() on
# row-creation timestamps) rather than the course tables' looser style.
#
# document_id cross-references (§8.3): document_versions has a NEW ROW
# per version ("insert new document_versions row, mark previous
# superseded"), so document_id repeats across a document's version
# history and is NOT unique on its own — version_id (a plain surrogate
# PK, matching every other table's single-column-PK style in this file)
# is the real per-row identity. That means document_id can't be a valid
# FK target (Postgres requires a UNIQUE/PK column), so
# ingested_assets.document_id and ingestion_jobs.document_id are
# deliberately plain, non-FK string columns — the exact same choice
# already made for Conversation.customer_id above, for the same reason
# (a real FK constraint isn't available, not that the reference doesn't
# matter). first_seen_version/last_seen_version DO get real FKs, since
# those reference version_id specifically, which is genuinely unique.
#
# tsv is a DB-level GENERATED ALWAYS ... STORED column (Computed()),
# not populated by application code: the whole reason to prefer
# database-enforced guarantees over app-level discipline (§21's own
# stated principle for timestamps) applies just as much here — a stored
# generated column can never drift out of sync with `text`, which
# hand-maintained Python code always risks after an UPDATE. Consequence
# for pipeline.py: it must never attempt to set/update `tsv` itself —
# Postgres rejects writes to a generated column — only INSERT `text`.
# ---------------------------------------------------------------------------

class DocumentStatus(str, enum.Enum):
    """§8.3 — exactly two states: the current row for a document, or one
    a newer version has superseded."""
    active = "active"
    superseded = "superseded"


class IngestionJobStatus(str, enum.Enum):
    """§8.1 — the four states GET /ingest/{job_id} reports."""
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class DocumentVersion(Base):
    """One row per ingested version of a document (§8.3 step 1/4).
    content_hash is the whole-file SHA256 §8.3 step 1 compares against to
    detect an unchanged re-upload before any extraction runs.
    """

    __tablename__ = "document_versions"

    version_id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
        comment="Surrogate PK — the real per-row identity (see module comment on why document_id can't be)",
    )
    document_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        comment="Stable identifier for the document across its version history — repeats across rows, not unique",
    )
    content_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="SHA256 hex of the raw file bytes (hashing.hash_bytes()) — §8.3 step 1",
    )
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="UTC timestamp when this version was ingested",
    )
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, name="document_version_status", create_constraint=True),
        nullable=False,
        comment="active (current) or superseded — enforced at DB level",
    )
    doc_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    product_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)

    def __repr__(self) -> str:
        return f"<DocumentVersion version_id={self.version_id} document_id={self.document_id!r} status={self.status}>"


class IngestedAsset(Base):
    """One row per extracted asset (chunk/table/image/diagram) tracked
    across re-ingestion runs — the hash-based dedup ledger §8.3 diffs
    against (dedup_engine.diff_assets()).
    """

    __tablename__ = "ingested_assets"

    asset_id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
        comment="Surrogate PK — referenced by chunks/tables/images/diagram_graphs.asset_id",
    )
    document_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        comment="References document_versions.document_id logically, no FK constraint (see module comment)",
    )
    asset_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="'chunk' | 'table' | 'image' | 'diagram'",
    )
    asset_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        comment="SHA256 hex of the extracted content — §8.3's entire dedup mechanism reads/diffs this",
    )
    embedding_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Identifier of the associated embedding row in whichever asset-type table this asset "
        "produced — not a single FK, since which table depends on asset_type (polymorphic)",
    )
    first_seen_version: Mapped[int | None] = mapped_column(
        ForeignKey("document_versions.version_id"),
        nullable=True,
        comment="document_versions.version_id this asset (this exact hash) first appeared in",
    )
    last_seen_version: Mapped[int | None] = mapped_column(
        ForeignKey("document_versions.version_id"),
        nullable=True,
        comment="document_versions.version_id this asset (this exact hash) was last seen in",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
        comment="§8.3's soft-retire flag — set False when a re-ingestion no longer produces this hash, never hard-deleted",
    )
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section_header: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<IngestedAsset asset_id={self.asset_id} asset_type={self.asset_type!r} is_active={self.is_active}>"


class Chunk(Base):
    """A text chunk produced by extract_text.py's structure-aware
    recursive splitter (§8.2.1), with full retrieval metadata (§27).
    """

    __tablename__ = "chunks"
    __table_args__ = (
        Index(
            "ix_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index("ix_chunks_tsv_gin", "tsv", postgresql_using="gin"),
    )

    chunk_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("ingested_assets.asset_id"), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)
    embedding_namespace: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="Which real embedding model produced this row's vector — "
        "BaseLLMClient.embedding_namespace at insert time (e.g. "
        "'azure:text-embedding-3-small', 'gemini:gemini-embedding-001'). "
        "Real, confirmed bug this closes: without this, a live query "
        "embedded under a DIFFERENT provider than whatever embedded the "
        "corpus (e.g. after a real LLM_PROVIDER fallback, Azure -> "
        "Groq/Gemini) would be compared via pgvector cosine distance "
        "against a non-comparable embedding space with zero error — "
        "app/retrieval/vector_search.py filters on this column so a "
        "provider mismatch degrades to an empty vector leg (keyword leg "
        "still works) instead of silently returning meaningless results.",
    )
    tsv: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('english', text)", persisted=True),
        nullable=False,
        comment="DB-generated (STORED), never written by application code — see module comment",
    )
    source_document: Mapped[str | None] = mapped_column(String(255), nullable=True)
    section_header: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    product_version: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    doc_type: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    last_updated: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<Chunk chunk_id={self.chunk_id} asset_id={self.asset_id}>"


class TableAsset(Base):
    """A table extracted by extract_tables.py. Named TableAsset, not
    Table — SQLAlchemy's own Table class already owns that name, and a
    model called `Table` sitting next to `sqlalchemy.Table` (imported
    throughout this codebase's Alembic tooling) invites exactly the kind
    of same-name collision this whole naming exercise is about avoiding.
    __tablename__ is still the plain "tables" the schema calls for.
    """

    __tablename__ = "tables"
    __table_args__ = (
        Index(
            "ix_tables_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index("ix_tables_tsv_gin", "tsv", postgresql_using="gin"),
    )

    table_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("ingested_assets.asset_id"), nullable=False)
    raw_json: Mapped[dict | list] = mapped_column(JSON, nullable=False)
    text_serialization: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)
    embedding_namespace: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="Which real embedding model produced this row's vector — see Chunk.embedding_namespace's own comment for the full, real bug this closes.",
    )
    tsv: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('english', text_serialization)", persisted=True),
        nullable=False,
        comment="DB-generated (STORED), never written by application code — see module comment. "
        "text_serialization is NOT NULL already, so no COALESCE needed here (unlike Image/DiagramGraphRow's caption).",
    )
    source_document: Mapped[str | None] = mapped_column(String(255), nullable=True)
    section_header: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    product_version: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    possibly_truncated: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
        comment="extract_tables.py's cross-page-stitch fallback flag: this fragment sat near "
        "a page bottom but a matching continuation on the next page couldn't be confirmed "
        "(§8.2's known find_tables()-per-page limitation) — an honest 'might be incomplete' "
        "signal, not a guess. DB-level default, matching this project's own established "
        "convention (§21) — every insert path gets false unconditionally, not just pipeline.py's.",
    )
    has_unresolved_symbols: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
        comment="extract_tables.py's ZapfDingbats-glyph flag: this table's source PDF region "
        "contains an icon-font character this module doesn't have a visually-confirmed-safe "
        "Unicode substitution for (distinct from possibly_truncated — nothing here is missing "
        "rows, the concern is cell CONTENT, since the glyph's raw code point collides with an "
        "ordinary letter once it's plain text with no font attached). DB-level default, same "
        "convention as possibly_truncated (§21) — every insert path gets false unconditionally.",
    )

    def __repr__(self) -> str:
        return f"<TableAsset table_id={self.table_id} asset_id={self.asset_id}>"


class Image(Base):
    """An image extracted by extract_images.py. blob_ref points at the
    on-disk file (extract_images.py's blob_ref convention); caption is
    None until caption_image() has run (§8.3 — captioning is costed).
    """

    __tablename__ = "images"
    __table_args__ = (
        Index(
            "ix_images_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index("ix_images_tsv_gin", "tsv", postgresql_using="gin"),
    )

    image_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("ingested_assets.asset_id"), nullable=False)
    blob_ref: Mapped[str] = mapped_column(String(500), nullable=False)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)
    embedding_namespace: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="Which real embedding model produced this row's vector — see Chunk.embedding_namespace's own comment for the full, real bug this closes.",
    )
    tsv: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('english', COALESCE(caption, ''))", persisted=True),
        nullable=False,
        comment="DB-generated (STORED), never written by application code — see module comment. "
        "caption is nullable (None until caption_image() has run, §8.3), so COALESCE(..., '') "
        "keeps to_tsvector() from ever receiving NULL.",
    )
    source_document: Mapped[str | None] = mapped_column(String(255), nullable=True)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)

    def __repr__(self) -> str:
        return f"<Image image_id={self.image_id} asset_id={self.asset_id}>"


class DiagramGraphRow(Base):
    """A diagram/flowchart extracted by extract_diagrams.py, parsed into
    a structured {nodes, edges} graph.

    Naming collision, resolved deliberately, not ignored:
    app/ingestion/extract_diagrams.py already defines a Pydantic class
    named `DiagramGraph` — the structured-output schema parse_diagram()
    validates the LLM's response against. That class and this one
    represent the same real-world concept (a parsed diagram) but are
    fundamentally different objects for different layers (an in-flight
    LLM-output contract vs. a persisted DB row with a surrogate PK and
    FK), so keeping them separate classes is correct, not an accident to
    paper over. What needed a real decision was the NAME: two classes
    named `DiagramGraph` in different modules only causes a problem if
    both are ever imported into the same module under that same name
    (e.g. a future pipeline.py doing
    `from app.ingestion.extract_diagrams import DiagramGraph` alongside
    `from app.db.models import DiagramGraph` would silently shadow one).
    Renaming the DB-row side to `DiagramGraphRow` here removes the
    collision at the source rather than relying on every future importer
    remembering to alias one of them. __tablename__ stays the plain
    "diagram_graphs" the schema calls for.
    """

    __tablename__ = "diagram_graphs"
    __table_args__ = (
        Index(
            "ix_diagram_graphs_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index("ix_diagram_graphs_tsv_gin", "tsv", postgresql_using="gin"),
    )

    diagram_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("ingested_assets.asset_id"), nullable=False)
    graph_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)
    embedding_namespace: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="Which real embedding model produced this row's vector — see Chunk.embedding_namespace's own comment for the full, real bug this closes.",
    )
    tsv: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('english', COALESCE(caption, ''))", persisted=True),
        nullable=False,
        comment="DB-generated (STORED), never written by application code — see module comment. "
        "caption is nullable (None until parse_diagram() has run, §8.3), so COALESCE(..., '') "
        "keeps to_tsvector() from ever receiving NULL.",
    )
    source_document: Mapped[str | None] = mapped_column(String(255), nullable=True)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    diagram_type: Mapped[str | None] = mapped_column(String(50), nullable=True)

    def __repr__(self) -> str:
        return f"<DiagramGraphRow diagram_id={self.diagram_id} asset_id={self.asset_id} diagram_type={self.diagram_type!r}>"


class IngestionJob(Base):
    """Tracks one POST /ingest run end-to-end (§8.1) — job_id is
    generated at request time and returned immediately (202 Accepted),
    so it's a String PK like Conversation.conversation_id, not a
    DB-autoincrement value that wouldn't exist yet when the response is built.
    """

    __tablename__ = "ingestion_jobs"

    job_id: Mapped[str] = mapped_column(
        String(255),
        primary_key=True,
        comment="Generated at request time (UUID string), returned in the 202 response",
    )
    document_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        comment="References document_versions.document_id logically, no FK constraint (see module comment)",
    )
    status: Mapped[IngestionJobStatus] = mapped_column(
        Enum(IngestionJobStatus, name="ingestion_job_status", create_constraint=True),
        nullable=False,
    )
    stats_json: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="§8's step 5: {assets_new, assets_unchanged_skipped, assets_updated, assets_retired}",
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="NULL until the job actually finishes",
    )

    def __repr__(self) -> str:
        return f"<IngestionJob job_id={self.job_id!r} status={self.status}>"


# ---------------------------------------------------------------------------
# Escalation / notification tables (§21, §7, §36) — Stage 7
# ---------------------------------------------------------------------------

class NotificationStatus(str, enum.Enum):
    """Defined as a 3-value enum from the start, even though Stage 7's own
    code (mcp_servers/notification_mcp/server.py) only ever writes `sent`
    or `failed` — this avoids a later migration to widen the enum once a
    real retry job exists. `failed_permanently` is reserved vocabulary for
    that future job (deferred to Stage 10, per §36 — a scheduled retry
    job is infrastructure-shaped, the same category of thing as
    docker-compose.yml, already deferred) to write once its one retry
    attempt also fails. See is_eligible_for_retry() below."""
    sent = "sent"
    failed = "failed"
    failed_permanently = "failed_permanently"


def is_eligible_for_retry(status: str) -> bool:
    """§36: a failed notification is retried exactly once via a scheduled
    retry job. This is the pure retry-ELIGIBILITY decision — real and
    testable today — deliberately separate from the scheduled EXECUTION
    mechanism itself (deferred to Stage 10). Lives here, next to
    NotificationStatus, rather than in the MCP client/server layer: it's
    pure logic over this enum, and the natural place for a future
    scheduler (which needs the NotificationLog model regardless) to find
    it without importing through the MCP protocol layer at all."""
    return status == NotificationStatus.failed.value


class EscalationLog(Base):
    """One row per fired escalation (§6.1's matrix decided "escalate").
    Columns per §21, pinned exactly — no additions. handled_by_user_id
    closes the audit-trail requirement (§16): every escalation records
    which support agent was handling the ticket when it fired.
    ticket_context_json carries README's "full context transfer"
    requirement — see escalate.py's build_ticket_context() for the
    real-state-field mapping (§4), not invented here.
    """

    __tablename__ = "escalation_log"

    escalation_id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
        comment="Surrogate PK — referenced by notification_log.escalation_id",
    )
    trace_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        comment="Correlates to the request's trace_id (Message.trace_id, structured logs)",
    )
    handled_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id"),
        nullable=False,
        comment="Audit trail (§16) — which support agent was handling the ticket when this fired",
    )
    ticket_context_json: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        comment="Full context transfer for the human agent — see escalate.build_ticket_context()",
    )
    reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="escalate_node's own escalation_reason (EscalationOutput, §39.3), or a fixed "
        "fallback string if that LLM call itself failed",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return f"<EscalationLog escalation_id={self.escalation_id} trace_id={self.trace_id!r}>"


class NotificationLog(Base):
    """One row per notification attempt (§21, §36). channel is a plain
    string, not a DB enum — Slack/PagerDuty are explicitly documented,
    extensible, undetermined-cardinality future values (§7), matching
    how Chunk.category/Customer.subscription_tier are plain strings in
    this schema for the same reason, versus a true closed set like
    UserRole getting a real enum.
    """

    __tablename__ = "notification_log"

    notification_id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
        comment="Surrogate PK",
    )
    escalation_id: Mapped[int] = mapped_column(
        ForeignKey("escalation_log.escalation_id"),
        nullable=False,
        index=True,
    )
    channel: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="'email' today (Mailtrap) — Slack/PagerDuty are documented, unbuilt extension points (§7)",
    )
    status: Mapped[NotificationStatus] = mapped_column(
        Enum(NotificationStatus, name="notification_status", create_constraint=True),
        nullable=False,
    )
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return f"<NotificationLog notification_id={self.notification_id} escalation_id={self.escalation_id} status={self.status}>"


class EvaluationRun(Base):
    """One row per real golden-eval pass (§24, §25's "Stage 8 —
    Observability + Calibration"). A disclosed schema addition beyond
    §21's originally pinned tables — none of §24's TSR/SQL-correctness/
    routing-accuracy/risk-accuracy/escalation-recall/RAGAS-style metrics
    are live production values (they only mean anything against
    golden-labeled ground truth), so GET /metrics can only ever report
    the most recent real run's numbers, and that requires persisting
    them somewhere.

    Written by evaluation/calibrate_thresholds.py — the "full pass"
    driver that runs golden_50.json through the real graph once and
    feeds the same results to both its own threshold search and
    evaluation/ragas_metrics.py's scorer functions, so the expensive
    real graph run only happens once per evaluation pass, not twice.
    All metric columns are nullable: a --sample-limited or partial run
    (see the call-volume/rate-limit safety mechanisms) may not populate
    every field, and GET /metrics falls back to null for whatever the
    most recent row doesn't have.
    """

    __tablename__ = "evaluation_runs"

    run_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, comment="Surrogate PK")
    run_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    sample_size: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Number of golden_50 queries actually run this pass — 50 for a full run, "
        "fewer for a --sample N run (§24's judge call-volume/rate-limit safety mechanism)",
    )

    # §24 SLO metrics graded against golden_50 ground truth
    task_success_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    sql_correctness: Mapped[float | None] = mapped_column(Float, nullable=True)
    query_routing_accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_classification_accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    escalation_recall: Mapped[float | None] = mapped_column(Float, nullable=True)

    # §24.2 RAGAS-style metrics (evaluation/ragas_metrics.py)
    faithfulness: Mapped[float | None] = mapped_column(Float, nullable=True)
    answer_relevance: Mapped[float | None] = mapped_column(Float, nullable=True)
    context_precision: Mapped[float | None] = mapped_column(Float, nullable=True)
    context_recall: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Deliberate simplification of canonical RAGAS context recall — "
        "golden_50.json's own expected_sources label-matching, not judge-based "
        "sentence-attribution (see ragas_metrics.py's own docstring)",
    )

    # evaluation/calibrate_thresholds.py's own output
    calibrated_high_threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    calibrated_medium_threshold: Mapped[float | None] = mapped_column(Float, nullable=True)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<EvaluationRun run_id={self.run_id} run_at={self.run_at} sample_size={self.sample_size}>"
