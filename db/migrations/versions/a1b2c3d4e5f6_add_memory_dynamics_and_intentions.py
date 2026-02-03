"""add memory dynamics and intentions

Revision ID: a1b2c3d4e5f6
Revises: 7fb6925e805c
Create Date: 2026-02-02 10:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '7fb6925e805c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create memory_dynamics table for FSRS-6 scheduling
    op.create_table('memory_dynamics',
        sa.Column('memory_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('stability', sa.Float(), nullable=True, default=1.0),
        sa.Column('difficulty', sa.Float(), nullable=True, default=5.0),
        sa.Column('retrieval_strength', sa.Float(), nullable=True, default=1.0),
        sa.Column('storage_strength', sa.Float(), nullable=True, default=0.5),
        sa.Column('is_key', sa.Boolean(), nullable=True, default=False),
        sa.Column('importance_weight', sa.Float(), nullable=True, default=1.0),
        sa.Column('last_accessed_at', sa.DateTime(), nullable=True),
        sa.Column('access_count', sa.Integer(), nullable=True, default=0),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('memory_id')
    )
    op.create_index(op.f('ix_memory_dynamics_user_id'), 'memory_dynamics', ['user_id'], unique=False)
    op.create_index('ix_memory_dynamics_user_accessed', 'memory_dynamics', ['user_id', 'last_accessed_at'], unique=False)

    # Create memory_access_log table for FSRS history
    op.create_table('memory_access_log',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('memory_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('grade', sa.Integer(), nullable=False),
        sa.Column('signal_type', sa.String(), nullable=True),
        sa.Column('retrievability_at_access', sa.Float(), nullable=True),
        sa.Column('context', sa.Text(), nullable=True),
        sa.Column('accessed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['memory_id'], ['memory_dynamics.memory_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_memory_access_log_memory_id'), 'memory_access_log', ['memory_id'], unique=False)
    op.create_index(op.f('ix_memory_access_log_user_id'), 'memory_access_log', ['user_id'], unique=False)
    op.create_index(op.f('ix_memory_access_log_accessed_at'), 'memory_access_log', ['accessed_at'], unique=False)
    op.create_index('ix_memory_access_user_time', 'memory_access_log', ['user_id', 'accessed_at'], unique=False)

    # Create intentions table for future triggers
    op.create_table('intentions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('agent_id', sa.String(), nullable=True, default='clara'),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('source_memory_id', sa.String(), nullable=True),
        sa.Column('trigger_conditions', sa.Text(), nullable=False),
        sa.Column('priority', sa.Integer(), nullable=True, default=0),
        sa.Column('fired', sa.Boolean(), nullable=True, default=False),
        sa.Column('fire_once', sa.Boolean(), nullable=True, default=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('fired_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_intentions_user_id'), 'intentions', ['user_id'], unique=False)
    op.create_index('ix_intention_user_unfired', 'intentions', ['user_id', 'fired'], unique=False)
    op.create_index('ix_intention_expires', 'intentions', ['expires_at'], unique=False)

    # Create memory_supersessions table for tracking replaced memories
    op.create_table('memory_supersessions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('old_memory_id', sa.String(), nullable=False),
        sa.Column('new_memory_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('reason', sa.String(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True, default=1.0),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_memory_supersessions_old_memory_id'), 'memory_supersessions', ['old_memory_id'], unique=False)
    op.create_index(op.f('ix_memory_supersessions_new_memory_id'), 'memory_supersessions', ['new_memory_id'], unique=False)
    op.create_index(op.f('ix_memory_supersessions_user_id'), 'memory_supersessions', ['user_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    # Drop memory_supersessions
    op.drop_index(op.f('ix_memory_supersessions_user_id'), table_name='memory_supersessions')
    op.drop_index(op.f('ix_memory_supersessions_new_memory_id'), table_name='memory_supersessions')
    op.drop_index(op.f('ix_memory_supersessions_old_memory_id'), table_name='memory_supersessions')
    op.drop_table('memory_supersessions')

    # Drop intentions
    op.drop_index('ix_intention_expires', table_name='intentions')
    op.drop_index('ix_intention_user_unfired', table_name='intentions')
    op.drop_index(op.f('ix_intentions_user_id'), table_name='intentions')
    op.drop_table('intentions')

    # Drop memory_access_log
    op.drop_index('ix_memory_access_user_time', table_name='memory_access_log')
    op.drop_index(op.f('ix_memory_access_log_accessed_at'), table_name='memory_access_log')
    op.drop_index(op.f('ix_memory_access_log_user_id'), table_name='memory_access_log')
    op.drop_index(op.f('ix_memory_access_log_memory_id'), table_name='memory_access_log')
    op.drop_table('memory_access_log')

    # Drop memory_dynamics
    op.drop_index('ix_memory_dynamics_user_accessed', table_name='memory_dynamics')
    op.drop_index(op.f('ix_memory_dynamics_user_id'), table_name='memory_dynamics')
    op.drop_table('memory_dynamics')
