"""add lead decision fields

Revision ID: 20260928_0002
Revises: 20260927_0001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260928_0002"
down_revision: str | None = "20260927_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("leads", sa.Column("summary", sa.Text(), nullable=True))
    op.add_column(
        "leads",
        sa.Column(
            "response_priority",
            sa.Enum(
                "IMMEDIATE",
                "PRIORITY",
                "STANDARD",
                "LOW",
                "REVIEW",
                name="response_priority",
                native_enum=False,
                length=32,
            ),
            nullable=True,
        ),
    )
    op.add_column("leads", sa.Column("response_window_minutes", sa.Integer(), nullable=True))
    op.add_column("leads", sa.Column("response_due_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("leads", sa.Column("decision_confidence", sa.Float(), nullable=True))
    op.add_column("leads", sa.Column("decision_model", sa.String(length=100), nullable=True))
    op.add_column("leads", sa.Column("decision_error", sa.Text(), nullable=True))
    op.add_column("leads", sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_leads_response_priority", "leads", ["response_priority"])


def downgrade() -> None:
    op.drop_index("ix_leads_response_priority", table_name="leads")
    for column in (
        "decided_at",
        "decision_error",
        "decision_model",
        "decision_confidence",
        "response_due_at",
        "response_window_minutes",
        "response_priority",
        "summary",
    ):
        op.drop_column("leads", column)
