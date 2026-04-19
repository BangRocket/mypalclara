"""add obsidian_accounts table for per-user Obsidian REST API config

Revision ID: k1l2m3n4o5p6
Revises: j0k1l2m3n4o5
Create Date: 2026-04-19 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "k1l2m3n4o5p6"
down_revision: Union[str, Sequence[str], None] = "j0k1l2m3n4o5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    result = conn.execute(
        sa.text("SELECT 1 FROM information_schema.tables WHERE table_name = 'obsidian_accounts'")
    )
    if result.fetchone():
        return

    op.create_table(
        "obsidian_accounts",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("base_url", sa.String(), nullable=False),
        sa.Column("port", sa.Integer(), nullable=True),
        sa.Column("api_token", sa.Text(), nullable=False),
        sa.Column("verify_tls", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("verified_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_obsidian_accounts_user_id", "obsidian_accounts", ["user_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_obsidian_accounts_user_id", table_name="obsidian_accounts")
    op.drop_table("obsidian_accounts")
