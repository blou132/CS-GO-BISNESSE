"""track market sync errors

Revision ID: 7d9e1c84b2f0
Revises: 310b4bb61557
Create Date: 2026-09-05
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "7d9e1c84b2f0"
down_revision: str | Sequence[str] | None = "310b4bb61557"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("market_sync_states", sa.Column("last_error", sa.String(1024)))
    op.add_column("market_sync_states", sa.Column("last_error_at", sa.DateTime(timezone=True)))


def downgrade() -> None:
    op.drop_column("market_sync_states", "last_error_at")
    op.drop_column("market_sync_states", "last_error")
