"""add decision answer observability

Revision ID: 20260928_0003
Revises: 20260928_0002
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260928_0003"
down_revision: str | None = "20260928_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("leads", sa.Column("urgency_confidence", sa.Float(), nullable=True))
    op.add_column("leads", sa.Column("summary_fidelity", sa.String(length=32), nullable=True))
    op.add_column("leads", sa.Column("summary_fidelity_confidence", sa.Float(), nullable=True))
    op.add_column("leads", sa.Column("input_safety", sa.String(length=32), nullable=True))
    op.add_column("leads", sa.Column("input_safety_confidence", sa.Float(), nullable=True))


def downgrade() -> None:
    for column in (
        "input_safety_confidence",
        "input_safety",
        "summary_fidelity_confidence",
        "summary_fidelity",
        "urgency_confidence",
    ):
        op.drop_column("leads", column)
