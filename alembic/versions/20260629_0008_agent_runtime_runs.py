"""Add agent runtime run checkpoints.

Revision ID: 20260629_0008
Revises: 20260621_0007
Create Date: 2026-06-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260629_0008"
down_revision: str | None = "20260621_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_runtime_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=True),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("current_node", sa.String(length=80), nullable=False),
        sa.Column("last_completed_node", sa.String(length=80), nullable=False),
        sa.Column("resume_token_hash", sa.String(length=64), nullable=False),
        sa.Column("request_question", sa.Text(), nullable=False),
        sa.Column("canonical_task", sa.Text(), nullable=False),
        sa.Column("state_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", name="uq_agent_runtime_runs_run_id"),
    )
    op.create_index(op.f("ix_agent_runtime_runs_id"), "agent_runtime_runs", ["id"], unique=False)
    op.create_index(op.f("ix_agent_runtime_runs_conversation_id"), "agent_runtime_runs", ["conversation_id"], unique=False)
    op.create_index(op.f("ix_agent_runtime_runs_run_id"), "agent_runtime_runs", ["run_id"], unique=True)
    op.create_index(op.f("ix_agent_runtime_runs_status"), "agent_runtime_runs", ["status"], unique=False)
    op.create_index(op.f("ix_agent_runtime_runs_updated_at"), "agent_runtime_runs", ["updated_at"], unique=False)
    op.create_index(op.f("ix_agent_runtime_runs_expires_at"), "agent_runtime_runs", ["expires_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_agent_runtime_runs_expires_at"), table_name="agent_runtime_runs")
    op.drop_index(op.f("ix_agent_runtime_runs_updated_at"), table_name="agent_runtime_runs")
    op.drop_index(op.f("ix_agent_runtime_runs_status"), table_name="agent_runtime_runs")
    op.drop_index(op.f("ix_agent_runtime_runs_run_id"), table_name="agent_runtime_runs")
    op.drop_index(op.f("ix_agent_runtime_runs_conversation_id"), table_name="agent_runtime_runs")
    op.drop_index(op.f("ix_agent_runtime_runs_id"), table_name="agent_runtime_runs")
    op.drop_table("agent_runtime_runs")
