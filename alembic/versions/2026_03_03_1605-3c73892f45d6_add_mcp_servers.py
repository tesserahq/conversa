"""add mcp_servers

Revision ID: 3c73892f45d6
Revises: d4e5f6a7b8c9
Create Date: 2026-03-03 16:05:25.651198

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "3c73892f45d6"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "mcp_servers",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("server_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("url", sa.String(length=512), nullable=False),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("credential_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("tool_prefix", sa.String(length=64), nullable=True),
        sa.Column(
            "tool_cache_ttl_seconds",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("300"),
        ),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
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
        "ix_mcp_servers_server_id", "mcp_servers", ["server_id"], unique=True
    )
    op.create_index(
        "ix_mcp_servers_deleted_at", "mcp_servers", ["deleted_at"], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_mcp_servers_deleted_at", table_name="mcp_servers")
    op.drop_index("ix_mcp_servers_server_id", table_name="mcp_servers")
    op.drop_table("mcp_servers")
