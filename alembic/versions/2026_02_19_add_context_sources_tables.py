"""add credentials, context_sources, and context_source_state tables

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-02-19

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create credentials, context_sources, and context_source_state tables."""
    # credentials (referenced by context_sources)
    op.create_table(
        "credentials",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("encrypted_data", sa.LargeBinary(), nullable=False),
        sa.Column(
            "created_by_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
    )
    op.create_index("ix_credentials_type", "credentials", ["type"], unique=False)
    op.create_index(
        "ix_credentials_deleted_at", "credentials", ["deleted_at"], unique=False
    )

    # context_sources
    op.create_table(
        "context_sources",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("source_id", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=256), nullable=False),
        sa.Column("base_url", sa.String(length=512), nullable=False),
        sa.Column(
            "credential_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("capabilities", postgresql.JSONB(), nullable=True),
        sa.Column(
            "poll_interval_seconds",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("3600"),
        ),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["credential_id"],
            ["credentials.id"],
            ondelete="SET NULL",
        ),
    )
    op.create_index(
        "ix_context_sources_source_id",
        "context_sources",
        ["source_id"],
        unique=True,
    )
    op.create_index(
        "ix_context_sources_deleted_at",
        "context_sources",
        ["deleted_at"],
        unique=False,
    )

    # context_source_state
    op.create_table(
        "context_source_state",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("last_success_at", sa.DateTime(), nullable=True),
        sa.Column("last_attempt_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("etag", sa.String(length=256), nullable=True),
        sa.Column("since_cursor", sa.Text(), nullable=True),
        sa.Column("next_run_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["context_sources.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "source_id", "user_id", name="uq_context_source_state_source_user"
        ),
    )
    op.create_index(
        "ix_context_source_state_source_id",
        "context_source_state",
        ["source_id"],
        unique=False,
    )
    op.create_index(
        "ix_context_source_state_user_id",
        "context_source_state",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop context_source_state, context_sources, and credentials tables."""
    op.drop_index(
        "ix_context_source_state_user_id",
        table_name="context_source_state",
    )
    op.drop_index(
        "ix_context_source_state_source_id",
        table_name="context_source_state",
    )
    op.drop_table("context_source_state")

    op.drop_index("ix_context_sources_deleted_at", table_name="context_sources")
    op.drop_index("ix_context_sources_source_id", table_name="context_sources")
    op.drop_table("context_sources")

    op.drop_index("ix_credentials_deleted_at", table_name="credentials")
    op.drop_index("ix_credentials_type", table_name="credentials")
    op.drop_table("credentials")
