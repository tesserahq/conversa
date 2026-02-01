"""Initialize the database

Revision ID: initialize_database
Revises:
Create Date: 2024-03-21

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "initialize_database"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "app_settings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("key", sa.String(length=50), nullable=False),
        sa.Column("value", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "users",
        sa.Column(
            "id",
            sa.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("email", sa.String, unique=True, nullable=True),
        sa.Column("username", sa.String, unique=True, nullable=True),
        sa.Column("avatar_url", sa.String, nullable=True),
        sa.Column("first_name", sa.String, nullable=False),
        sa.Column("last_name", sa.String, nullable=False),
        sa.Column("provider", sa.String, nullable=True),
        sa.Column("confirmed_at", sa.DateTime, nullable=True),
        sa.Column("verified", sa.Boolean, default=False),
        sa.Column("verified_at", sa.DateTime, nullable=True),
        sa.Column("external_id", sa.String, nullable=True),
        sa.Column("service_account", sa.Boolean, default=False),
        sa.Column(
            "created_at", sa.DateTime, nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "updated_at", sa.DateTime, nullable=False, server_default=sa.text("now()")
        ),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("source", sa.String, nullable=False),
        sa.Column("spec_version", sa.String, nullable=False),
        sa.Column("event_type", sa.String, nullable=False),
        sa.Column(
            "event_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("data_content_type", sa.String, nullable=False),
        sa.Column("subject", sa.String, nullable=False),
        sa.Column("time", sa.DateTime, nullable=False),
        sa.Column("tags", sa.ARRAY(sa.String), nullable=True),
        sa.Column("labels", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("privy", sa.Boolean, nullable=False, default=False),
        sa.Column(
            "created_at", sa.DateTime, nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "updated_at", sa.DateTime, nullable=False, server_default=sa.text("now()")
        ),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table("events")
    op.drop_table("users")
    op.drop_table("app_settings")
