"""Add phase 47 shared schema.

Revision ID: 20260621_0005
Revises: 20260620_0004
Create Date: 2026-06-20
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260621_0005"
down_revision: str | None = "20260620_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("chunks", sa.Column("content_bbox_json", sa.Text(), nullable=True))
    op.create_table(
        "qa_feedback",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("question_answer_log_id", sa.Integer(), nullable=True),
        sa.Column("conversation_id", sa.Integer(), nullable=True),
        sa.Column("message_id", sa.Integer(), nullable=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("rating", sa.String(length=10), nullable=False),
        sa.Column("reason", sa.String(length=50), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["question_answer_log_id"], ["qa_logs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_qa_feedback_id"), "qa_feedback", ["id"], unique=False)
    op.create_index(
        op.f("ix_qa_feedback_question_answer_log_id"),
        "qa_feedback",
        ["question_answer_log_id"],
        unique=False,
    )
    op.create_index(op.f("ix_qa_feedback_conversation_id"), "qa_feedback", ["conversation_id"], unique=False)
    op.create_index(op.f("ix_qa_feedback_message_id"), "qa_feedback", ["message_id"], unique=False)
    op.create_index(op.f("ix_qa_feedback_rating"), "qa_feedback", ["rating"], unique=False)
    op.create_index(op.f("ix_qa_feedback_reason"), "qa_feedback", ["reason"], unique=False)
    op.create_index(op.f("ix_qa_feedback_created_at"), "qa_feedback", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_qa_feedback_created_at"), table_name="qa_feedback")
    op.drop_index(op.f("ix_qa_feedback_reason"), table_name="qa_feedback")
    op.drop_index(op.f("ix_qa_feedback_rating"), table_name="qa_feedback")
    op.drop_index(op.f("ix_qa_feedback_message_id"), table_name="qa_feedback")
    op.drop_index(op.f("ix_qa_feedback_conversation_id"), table_name="qa_feedback")
    op.drop_index(op.f("ix_qa_feedback_question_answer_log_id"), table_name="qa_feedback")
    op.drop_index(op.f("ix_qa_feedback_id"), table_name="qa_feedback")
    op.drop_table("qa_feedback")
    op.drop_column("chunks", "content_bbox_json")
