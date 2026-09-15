"""Add compact realtime deduplication receipts, no changes to market tables."""

import sqlalchemy as sa

from alembic import op

revision = "f8a2b6c0d4e1"
down_revision = "e6f7a8b9c0d1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "realtime_receipts",
        sa.Column("event_key", sa.String(64), primary_key=True),
        sa.Column("platform", sa.String(32), nullable=False),
        sa.Column("event_type", sa.String(16), nullable=False),
        sa.Column("external_id", sa.String(256), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_realtime_receipts_received_at", "realtime_receipts", ["received_at"])


def downgrade() -> None:
    op.drop_index("ix_realtime_receipts_received_at", table_name="realtime_receipts")
    op.drop_table("realtime_receipts")
