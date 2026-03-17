"""add channel_installations

Revision ID: e5f6a7b8c9d0
Revises: 3c73892f45d6
Create Date: 2026-03-17 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "3c73892f45d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "channel_installations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("channel", sa.String(length=64), nullable=False),
        sa.Column("account_id", sa.String(length=256), nullable=False),
        sa.Column("account_name", sa.String(length=256), nullable=True),
        sa.Column("bot_user_id", sa.String(length=256), nullable=True),
        sa.Column("installer_user_id", sa.String(length=256), nullable=True),
        sa.Column("scopes", sa.String(length=1024), nullable=True),
        sa.Column("encrypted_data", sa.LargeBinary(), nullable=False),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
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
        sa.UniqueConstraint(
            "channel", "account_id", name="uq_channel_installation_account"
        ),
    )
    op.create_index(
        "ix_channel_installations_channel", "channel_installations", ["channel"]
    )
    op.create_index(
        "ix_channel_installations_account_id", "channel_installations", ["account_id"]
    )
    op.create_index(
        "ix_channel_installations_deleted_at", "channel_installations", ["deleted_at"]
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_channel_installations_deleted_at", table_name="channel_installations"
    )
    op.drop_index(
        "ix_channel_installations_account_id", table_name="channel_installations"
    )
    op.drop_index(
        "ix_channel_installations_channel", table_name="channel_installations"
    )
    op.drop_table("channel_installations")
