"""add sessions tables

Revision ID: 1315b45ccd4b
Revises: initialize_database
Create Date: 2026-02-13 23:26:14.771281

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "1315b45ccd4b"
down_revision: Union[str, None] = "initialize_database"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: sessions and session_messages tables."""
    op.create_table(
        "sessions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("session_key", sa.String(length=512), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("channel", sa.String(length=64), nullable=False),
        sa.Column("account_id", sa.String(length=256), nullable=True),
        sa.Column("chat_id", sa.String(length=256), nullable=False),
        sa.Column("thread_id", sa.String(length=256), nullable=True),
        sa.Column("display_name", sa.String(length=256), nullable=True),
        sa.Column("origin", postgresql.JSONB(), nullable=True),
        sa.Column(
            "last_message_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_sessions_session_key", "sessions", ["session_key"], unique=True)
    op.create_index(
        "ix_sessions_last_message_at", "sessions", ["last_message_at"], unique=False
    )
    op.create_index("ix_sessions_deleted_at", "sessions", ["deleted_at"], unique=False)

    op.create_table(
        "session_messages",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("direction", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("provider_message_id", sa.String(length=256), nullable=True),
        sa.Column("reply_to", sa.String(length=256), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_session_messages_session_id_created_at",
        "session_messages",
        ["session_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    """Drop sessions and session_messages tables."""
    op.drop_index(
        "ix_session_messages_session_id_created_at", table_name="session_messages"
    )
    op.drop_table("session_messages")
    op.drop_index("ix_sessions_deleted_at", table_name="sessions")
    op.drop_index("ix_sessions_last_message_at", table_name="sessions")
    op.drop_index("ix_sessions_session_key", table_name="sessions")
    op.drop_table("sessions")
