"""backfill pending status for existing review leads

Revision ID: 20260928_0005
Revises: 20260928_0004
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260928_0005"
down_revision: str | None = "20260928_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "UPDATE leads SET review_status = 'PENDING' "
        "WHERE response_priority = 'REVIEW' AND review_status IS NULL"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE leads SET review_status = NULL WHERE response_priority = 'REVIEW'"
    )
