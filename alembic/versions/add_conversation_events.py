"""Add conversation_events table

Revision ID: add_conversation_events
Revises: initialize_database
Create Date: 2025-02-01

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "add_conversation_events"
down_revision: Union[str, None] = "initialize_database"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "conversation_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("direction", sa.String(16), nullable=False),
        sa.Column("channel", sa.String(32), nullable=False),
        sa.Column("external_user_id", sa.String(255), nullable=False),
        sa.Column("message_id", sa.String(255), nullable=True),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column(
            "attachments", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("platform_message_id", sa.String(255), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_conversation_events_channel_external_user_created",
        "conversation_events",
        ["channel", "external_user_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_conversation_events_channel_external_user_created",
        table_name="conversation_events",
    )
    op.drop_table("conversation_events")
