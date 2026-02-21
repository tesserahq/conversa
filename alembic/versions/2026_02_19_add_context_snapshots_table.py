"""add context_snapshots table

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-02-19

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create context_snapshots table."""
    op.create_table(
        "context_snapshots",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("schema_version", sa.String(length=32), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("payload_hash", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_context_snapshots_user_generated",
        "context_snapshots",
        ["user_id", "generated_at"],
        unique=False,
        postgresql_ops={"generated_at": "DESC"},
    )
    op.create_index(
        "ix_context_snapshots_user_schema",
        "context_snapshots",
        ["user_id", "schema_version"],
        unique=False,
    )


def downgrade() -> None:
    """Drop context_snapshots table."""
    op.drop_index(
        "ix_context_snapshots_user_schema",
        table_name="context_snapshots",
    )
    op.drop_index(
        "ix_context_snapshots_user_generated",
        table_name="context_snapshots",
    )
    op.drop_table("context_snapshots")
