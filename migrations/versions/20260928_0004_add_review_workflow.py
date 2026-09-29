"""add human review workflow state

Revision ID: 20260928_0004
Revises: 20260928_0003
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260928_0004"
down_revision: str | None = "20260928_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "leads",
        sa.Column(
            "review_status",
            sa.Enum("PENDING", "ACCEPTED", "DISCARDED", name="review_status", native_enum=False, length=32),
            nullable=True,
        ),
    )
    op.create_index("ix_leads_review_status", "leads", ["review_status"])
    op.execute(
        "UPDATE leads SET review_status = 'pending' WHERE response_priority = 'review'"
    )


def downgrade() -> None:
    op.drop_index("ix_leads_review_status", table_name="leads")
    op.drop_column("leads", "review_status")
