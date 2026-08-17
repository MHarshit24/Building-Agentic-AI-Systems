"""add archived to conversation_status enum

Revision ID: f431f2dfa901
Revises: 4314520ade09
Create Date: 2026-07-31 19:22:08.546928

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f431f2dfa901'
down_revision: Union[str, Sequence[str], None] = '4314520ade09'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    Alembic has no native "add enum value" op — every prior migration in
    this project only ever CREATE TYPEs fresh (see
    conversation_status_enum's own model comment), so this raw-SQL ALTER
    TYPE is a new pattern here, documented as such (production-readiness
    gap analysis, deletion item 2 plan).
    """
    op.execute("ALTER TYPE conversation_status ADD VALUE 'archived'")


def downgrade() -> None:
    """Downgrade schema.

    Postgres cannot drop a single enum value without recreating the
    whole type (and re-pointing every column/constraint that uses it) —
    documented as a known, accepted one-way migration rather than
    silently pretended to be reversible.
    """
    raise NotImplementedError(
        "Removing 'archived' from conversation_status requires recreating the enum type; not supported."
    )
