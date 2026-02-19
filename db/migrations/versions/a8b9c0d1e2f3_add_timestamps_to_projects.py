"""add created_at and updated_at to projects

Revision ID: a8b9c0d1e2f3
Revises: 97e434d26526
Create Date: 2026-02-10 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a8b9c0d1e2f3"
down_revision: Union[str, None] = "97e434d26526"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("created_at", sa.DateTime(), nullable=True))
    op.add_column("projects", sa.Column("updated_at", sa.DateTime(), nullable=True))
    # Backfill existing rows so .NET EF Core (non-nullable DateTime) doesn't choke
    op.execute("UPDATE projects SET created_at = now(), updated_at = now() WHERE created_at IS NULL")


def downgrade() -> None:
    op.drop_column("projects", "updated_at")
    op.drop_column("projects", "created_at")
