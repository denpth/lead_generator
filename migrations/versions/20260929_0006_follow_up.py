"""Record human decisions and follow-up completion."""
import sqlalchemy as sa
from alembic import op

revision = "20260929_0006"
down_revision = "20260928_0005"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("leads", sa.Column("reviewer_name", sa.String(100), nullable=True))
    op.add_column("leads", sa.Column("review_note", sa.Text(), nullable=True))
    op.add_column("leads", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("leads", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    for name in ("completed_at", "reviewed_at", "review_note", "reviewer_name"):
        op.drop_column("leads", name)
