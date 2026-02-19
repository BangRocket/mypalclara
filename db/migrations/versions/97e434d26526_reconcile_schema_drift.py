"""reconcile schema drift

Reconciles the PostgreSQL schema with current SQLAlchemy models:
- canonical_users: add status, is_admin columns
- mcp_servers: migrate from inline-config schema to config-file-reference schema
- Drop orphan tables (deployment_events, dashboard_sessions) with no model references
- Remove duplicate indexes (idx_* vs ix_*) on proactive tables

Revision ID: 97e434d26526
Revises: 91be23d58729
Create Date: 2026-02-09 22:42:12.424232

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "97e434d26526"
down_revision: Union[str, Sequence[str], None] = "91be23d58729"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # --- Drop orphan tables (no model references these) ---
    op.drop_index(op.f("ix_deployment_events_workflow_run_id"), table_name="deployment_events")
    op.drop_table("deployment_events")
    op.drop_index(op.f("ix_dashboard_sessions_session_token"), table_name="dashboard_sessions")
    op.drop_table("dashboard_sessions")

    # --- canonical_users: add missing columns ---
    op.add_column("canonical_users", sa.Column("status", sa.String(), server_default="active", nullable=False))
    op.add_column("canonical_users", sa.Column("is_admin", sa.Boolean(), server_default="0", nullable=False))

    # --- mcp_servers: migrate to config-file-reference schema ---
    # Step 1: Add new columns (server_type as nullable first for backfill)
    op.add_column("mcp_servers", sa.Column("user_id", sa.String(), nullable=True))
    op.add_column("mcp_servers", sa.Column("server_type", sa.String(), nullable=True))
    op.add_column("mcp_servers", sa.Column("config_path", sa.String(), nullable=True))
    op.add_column("mcp_servers", sa.Column("oauth_required", sa.Boolean(), nullable=True))
    op.add_column("mcp_servers", sa.Column("oauth_token_id", sa.String(), nullable=True))
    op.add_column("mcp_servers", sa.Column("total_tool_calls", sa.Integer(), nullable=True))
    op.add_column("mcp_servers", sa.Column("last_used_at", sa.DateTime(), nullable=True))

    # Step 2: Backfill server_type from existing data
    # All existing servers use transport=stdio → they are "local" servers
    op.execute("UPDATE mcp_servers SET server_type = 'local' WHERE server_type IS NULL")

    # Step 3: Now make server_type NOT NULL
    op.alter_column("mcp_servers", "server_type", nullable=False)

    # Step 4: Alter nullable constraints to match model
    op.alter_column("mcp_servers", "source_type", existing_type=sa.VARCHAR(), nullable=True)
    op.alter_column("mcp_servers", "created_at", existing_type=postgresql.TIMESTAMP(), nullable=True)
    op.alter_column("mcp_servers", "updated_at", existing_type=postgresql.TIMESTAMP(), nullable=True)

    # Step 5: Update indexes
    op.drop_index(op.f("ix_mcp_servers_name"), table_name="mcp_servers")
    op.create_index("ix_mcp_server_enabled", "mcp_servers", ["enabled"], unique=False)
    op.create_index("ix_mcp_server_user_name", "mcp_servers", ["user_id", "name"], unique=False)
    op.create_index(op.f("ix_mcp_servers_user_id"), "mcp_servers", ["user_id"], unique=False)
    op.create_foreign_key("fk_mcp_servers_oauth_token", "mcp_servers", "mcp_oauth_tokens", ["oauth_token_id"], ["id"])

    # Step 6: Drop old inline-config columns (data stored in config files now)
    op.drop_column("mcp_servers", "args")
    op.drop_column("mcp_servers", "tools_json")
    op.drop_column("mcp_servers", "endpoint_url")
    op.drop_column("mcp_servers", "command")
    op.drop_column("mcp_servers", "cwd")
    op.drop_column("mcp_servers", "docker_config")
    op.drop_column("mcp_servers", "transport")
    op.drop_column("mcp_servers", "display_name")
    op.drop_column("mcp_servers", "env")

    # --- Remove duplicate indexes (DB has both idx_* and ix_* variants) ---
    op.drop_index("idx_proactive_assessments_created_at", table_name="proactive_assessments")
    op.drop_index("idx_proactive_assessments_user_id", table_name="proactive_assessments")
    op.drop_index("idx_proactive_notes_user_id", table_name="proactive_notes")


def downgrade() -> None:
    """Downgrade schema."""
    # --- Restore duplicate indexes on proactive tables ---
    op.create_index("idx_proactive_notes_user_id", "proactive_notes", ["user_id"], unique=False)
    op.create_index("idx_proactive_assessments_user_id", "proactive_assessments", ["user_id"], unique=False)
    op.create_index("idx_proactive_assessments_created_at", "proactive_assessments", ["created_at"], unique=False)

    # --- Restore mcp_servers old schema ---
    op.add_column("mcp_servers", sa.Column("env", sa.TEXT(), nullable=True))
    op.add_column("mcp_servers", sa.Column("display_name", sa.VARCHAR(), nullable=True))
    op.add_column("mcp_servers", sa.Column("transport", sa.VARCHAR(), nullable=False, server_default="stdio"))
    op.add_column("mcp_servers", sa.Column("docker_config", sa.TEXT(), nullable=True))
    op.add_column("mcp_servers", sa.Column("cwd", sa.VARCHAR(), nullable=True))
    op.add_column("mcp_servers", sa.Column("command", sa.VARCHAR(), nullable=True))
    op.add_column("mcp_servers", sa.Column("endpoint_url", sa.VARCHAR(), nullable=True))
    op.add_column("mcp_servers", sa.Column("tools_json", sa.TEXT(), nullable=True))
    op.add_column("mcp_servers", sa.Column("args", sa.TEXT(), nullable=True))
    op.drop_constraint("fk_mcp_servers_oauth_token", "mcp_servers", type_="foreignkey")
    op.drop_index(op.f("ix_mcp_servers_user_id"), table_name="mcp_servers")
    op.drop_index("ix_mcp_server_user_name", table_name="mcp_servers")
    op.drop_index("ix_mcp_server_enabled", table_name="mcp_servers")
    op.create_index(op.f("ix_mcp_servers_name"), "mcp_servers", ["name"], unique=True)
    op.alter_column("mcp_servers", "updated_at", existing_type=postgresql.TIMESTAMP(), nullable=False)
    op.alter_column("mcp_servers", "created_at", existing_type=postgresql.TIMESTAMP(), nullable=False)
    op.alter_column("mcp_servers", "source_type", existing_type=sa.VARCHAR(), nullable=False)
    op.drop_column("mcp_servers", "last_used_at")
    op.drop_column("mcp_servers", "total_tool_calls")
    op.drop_column("mcp_servers", "oauth_token_id")
    op.drop_column("mcp_servers", "oauth_required")
    op.drop_column("mcp_servers", "config_path")
    op.drop_column("mcp_servers", "server_type")
    op.drop_column("mcp_servers", "user_id")

    # --- Remove canonical_users columns ---
    op.drop_column("canonical_users", "is_admin")
    op.drop_column("canonical_users", "status")

    # --- Restore orphan tables ---
    op.create_table(
        "dashboard_sessions",
        sa.Column("id", sa.VARCHAR(), nullable=False),
        sa.Column("session_token", sa.VARCHAR(), nullable=False),
        sa.Column("github_user_id", sa.INTEGER(), nullable=False),
        sa.Column("github_username", sa.VARCHAR(), nullable=False),
        sa.Column("github_access_token", sa.TEXT(), nullable=False),
        sa.Column("avatar_url", sa.VARCHAR(), nullable=True),
        sa.Column("is_collaborator", sa.VARCHAR(), nullable=True),
        sa.Column("created_at", postgresql.TIMESTAMP(), nullable=True),
        sa.Column("expires_at", postgresql.TIMESTAMP(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_dashboard_sessions_session_token", "dashboard_sessions", ["session_token"], unique=True)
    op.create_table(
        "deployment_events",
        sa.Column("id", sa.VARCHAR(), nullable=False),
        sa.Column("workflow_run_id", sa.VARCHAR(), nullable=False),
        sa.Column("workflow_name", sa.VARCHAR(), nullable=False),
        sa.Column("from_branch", sa.VARCHAR(), nullable=False),
        sa.Column("to_branch", sa.VARCHAR(), nullable=False),
        sa.Column("triggered_by", sa.VARCHAR(), nullable=False),
        sa.Column("triggered_at", postgresql.TIMESTAMP(), nullable=False),
        sa.Column("status", sa.VARCHAR(), nullable=True),
        sa.Column("conclusion", sa.VARCHAR(), nullable=True),
        sa.Column("head_sha", sa.VARCHAR(), nullable=True),
        sa.Column("commits_promoted", sa.INTEGER(), nullable=True),
        sa.Column("release_tag", sa.VARCHAR(), nullable=True),
        sa.Column("completed_at", postgresql.TIMESTAMP(), nullable=True),
        sa.Column("created_at", postgresql.TIMESTAMP(), nullable=True),
        sa.Column("updated_at", postgresql.TIMESTAMP(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_deployment_events_workflow_run_id", "deployment_events", ["workflow_run_id"], unique=True)
