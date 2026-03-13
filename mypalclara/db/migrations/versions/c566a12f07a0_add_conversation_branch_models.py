"""add conversation branch models

Revision ID: c566a12f07a0
Revises: a8b9c0d1e2f3
Create Date: 2026-03-12 20:06:39.620559

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c566a12f07a0"
down_revision: Union[str, Sequence[str], None] = "a8b9c0d1e2f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add conversations, branches, and branch_messages tables."""
    # 1. conversations
    op.create_table(
        "conversations",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_conversations_user_id"),
        "conversations",
        ["user_id"],
        unique=True,
    )

    # 2. branches (without fork_message_id FK initially, to break circular dep)
    op.create_table(
        "branches",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("conversation_id", sa.String(), nullable=False),
        sa.Column("parent_branch_id", sa.String(), nullable=True),
        sa.Column("fork_message_id", sa.String(), nullable=True),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("merged_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
        sa.ForeignKeyConstraint(["parent_branch_id"], ["branches.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_branch_conversation_status",
        "branches",
        ["conversation_id", "status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_branches_conversation_id"),
        "branches",
        ["conversation_id"],
        unique=False,
    )

    # 3. branch_messages (references branches)
    op.create_table(
        "branch_messages",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("branch_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=True),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("attachments", sa.Text(), nullable=True),
        sa.Column("tool_calls", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_branch_message_branch_created",
        "branch_messages",
        ["branch_id", "created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_branch_messages_branch_id"),
        "branch_messages",
        ["branch_id"],
        unique=False,
    )

    # 4. Now add the FK from branches.fork_message_id -> branch_messages.id
    # SQLite does not support ALTER TABLE ADD CONSTRAINT, so we use batch mode
    with op.batch_alter_table("branches") as batch_op:
        batch_op.create_foreign_key(
            "fk_branch_fork_message",
            "branch_messages",
            ["fork_message_id"],
            ["id"],
        )


def downgrade() -> None:
    """Remove conversations, branches, and branch_messages tables."""
    # Remove FK first
    with op.batch_alter_table("branches") as batch_op:
        batch_op.drop_constraint("fk_branch_fork_message", type_="foreignkey")

    op.drop_index(op.f("ix_branch_messages_branch_id"), table_name="branch_messages")
    op.drop_index("ix_branch_message_branch_created", table_name="branch_messages")
    op.drop_table("branch_messages")

    op.drop_index(op.f("ix_branches_conversation_id"), table_name="branches")
    op.drop_index("ix_branch_conversation_status", table_name="branches")
    op.drop_table("branches")

    op.drop_index(op.f("ix_conversations_user_id"), table_name="conversations")
    op.drop_table("conversations")
