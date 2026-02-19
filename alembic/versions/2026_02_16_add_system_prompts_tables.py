"""add system_prompts and system_prompt_versions tables

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-02-16

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create system_prompts and system_prompt_versions; seed default prompt."""
    # Create system_prompts without current_version_id (circular FK)
    op.create_table(
        "system_prompts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")
        ),
    )
    op.create_index("ix_system_prompts_name", "system_prompts", ["name"], unique=True)

    # Create system_prompt_versions
    op.create_table(
        "system_prompt_versions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "system_prompt_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column("note", sa.String(length=512), nullable=True),
        sa.ForeignKeyConstraint(
            ["system_prompt_id"], ["system_prompts.id"], ondelete="CASCADE"
        ),
    )
    op.create_index(
        "ix_system_prompt_versions_system_prompt_id",
        "system_prompt_versions",
        ["system_prompt_id"],
        unique=False,
    )

    # Add current_version_id to system_prompts
    op.add_column(
        "system_prompts",
        sa.Column("current_version_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_system_prompts_current_version_id",
        "system_prompts",
        "system_prompt_versions",
        ["current_version_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Seed default prompt: one row in system_prompts, one version, then link
    conn = op.get_bind()
    result = conn.execute(sa.text("""
            INSERT INTO system_prompts (id, name, created_at, updated_at)
            VALUES (gen_random_uuid(), 'default', now(), now())
            RETURNING id
            """))
    prompt_id = result.scalar()

    result2 = conn.execute(
        sa.text("""
            INSERT INTO system_prompt_versions
            (id, system_prompt_id, content, version_number, created_at, note)
            VALUES (gen_random_uuid(), :prompt_id, '', 1, now(), 'Initial version')
            RETURNING id
            """),
        {"prompt_id": str(prompt_id)},
    )
    version_id = result2.scalar()

    conn.execute(
        sa.text("""
            UPDATE system_prompts SET current_version_id = :version_id, updated_at = now()
            WHERE id = :prompt_id
            """),
        {"version_id": str(version_id), "prompt_id": str(prompt_id)},
    )


def downgrade() -> None:
    """Drop system_prompts and system_prompt_versions."""
    op.drop_constraint(
        "fk_system_prompts_current_version_id",
        "system_prompts",
        type_="foreignkey",
    )
    op.drop_column("system_prompts", "current_version_id")
    op.drop_index(
        "ix_system_prompt_versions_system_prompt_id",
        table_name="system_prompt_versions",
    )
    op.drop_table("system_prompt_versions")
    op.drop_index("ix_system_prompts_name", table_name="system_prompts")
    op.drop_table("system_prompts")
