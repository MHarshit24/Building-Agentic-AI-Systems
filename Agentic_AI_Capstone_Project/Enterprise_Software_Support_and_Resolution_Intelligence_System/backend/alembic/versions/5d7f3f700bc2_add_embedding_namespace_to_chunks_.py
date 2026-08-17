"""add embedding_namespace to chunks tables images diagram_graphs

Revision ID: 5d7f3f700bc2
Revises: 7c8dd5055638
Create Date: 2026-08-13 18:39:39.528235

Real, confirmed bug this closes: app/retrieval/vector_search.py and
app/guardrails/scope_guardrail.py both compared a live query's embedding
(whichever provider is currently active, resolved once at process
startup) against stored corpus vectors with NO record of which provider
produced them — so a real LLM_PROVIDER fallback (Azure -> Groq/Gemini)
would silently compare two non-comparable embedding spaces via pgvector
cosine distance, with zero error, potentially corrupting retrieval
quality across the entire vector-search leg for the whole fallback
session. This column, backfilled below for every existing row (this
project's real corpus was ingested entirely under Azure's
text-embedding-3-small, confirmed against the real AZURE_OPENAI_
EMBEDDING_DEPLOYMENT value), is what app/retrieval/vector_search.py now
filters on.

Note: alembic's autogenerate also detected an unrelated, pre-existing
drift on messages.flagged_for_review's column COMMENT (model vs. DB text
mismatch, apparently from an edit that was never migrated) — deliberately
NOT included here. Bundling an unrelated schema-comment fix into this
migration would make the history harder to read; that drift is real but
out of this migration's scope and is left for its own dedicated fix.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5d7f3f700bc2'
down_revision: Union[str, Sequence[str], None] = '7c8dd5055638'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# The real, confirmed provider every existing row in this project's real
# corpus was actually embedded under (AZURE_OPENAI_EMBEDDING_DEPLOYMENT=
# text-embedding-3-small, per the real root .env) — matches
# AzureLLMClient.embedding_namespace's own f"azure:{deployment}" format
# exactly, so a post-migration app instance still running Azure sees its
# own live namespace match every pre-existing row without a gap.
_BACKFILL_NAMESPACE = "azure:text-embedding-3-small"


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('chunks', sa.Column('embedding_namespace', sa.String(length=100), nullable=True, comment="Which real embedding model produced this row's vector — BaseLLMClient.embedding_namespace at insert time (e.g. 'azure:text-embedding-3-small', 'gemini:gemini-embedding-001'). Real, confirmed bug this closes: without this, a live query embedded under a DIFFERENT provider than whatever embedded the corpus (e.g. after a real LLM_PROVIDER fallback, Azure -> Groq/Gemini) would be compared via pgvector cosine distance against a non-comparable embedding space with zero error — app/retrieval/vector_search.py filters on this column so a provider mismatch degrades to an empty vector leg (keyword leg still works) instead of silently returning meaningless results."))
    op.create_index(op.f('ix_chunks_embedding_namespace'), 'chunks', ['embedding_namespace'], unique=False)
    op.add_column('diagram_graphs', sa.Column('embedding_namespace', sa.String(length=100), nullable=True, comment="Which real embedding model produced this row's vector — see Chunk.embedding_namespace's own comment for the full, real bug this closes."))
    op.create_index(op.f('ix_diagram_graphs_embedding_namespace'), 'diagram_graphs', ['embedding_namespace'], unique=False)
    op.add_column('images', sa.Column('embedding_namespace', sa.String(length=100), nullable=True, comment="Which real embedding model produced this row's vector — see Chunk.embedding_namespace's own comment for the full, real bug this closes."))
    op.create_index(op.f('ix_images_embedding_namespace'), 'images', ['embedding_namespace'], unique=False)
    op.add_column('tables', sa.Column('embedding_namespace', sa.String(length=100), nullable=True, comment="Which real embedding model produced this row's vector — see Chunk.embedding_namespace's own comment for the full, real bug this closes."))
    op.create_index(op.f('ix_tables_embedding_namespace'), 'tables', ['embedding_namespace'], unique=False)

    # Backfill: only rows that actually HAVE an embedding get a namespace —
    # a NULL embedding (never embedded) should stay NULL here too, not be
    # given a false provenance it never had.
    for table_name in ("chunks", "tables", "images", "diagram_graphs"):
        op.execute(
            f"UPDATE {table_name} SET embedding_namespace = '{_BACKFILL_NAMESPACE}' "
            "WHERE embedding IS NOT NULL"
        )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_tables_embedding_namespace'), table_name='tables')
    op.drop_column('tables', 'embedding_namespace')
    op.drop_index(op.f('ix_images_embedding_namespace'), table_name='images')
    op.drop_column('images', 'embedding_namespace')
    op.drop_index(op.f('ix_diagram_graphs_embedding_namespace'), table_name='diagram_graphs')
    op.drop_column('diagram_graphs', 'embedding_namespace')
    op.drop_index(op.f('ix_chunks_embedding_namespace'), table_name='chunks')
    op.drop_column('chunks', 'embedding_namespace')
