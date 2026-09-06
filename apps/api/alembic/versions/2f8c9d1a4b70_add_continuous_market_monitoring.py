"""add continuous market monitoring

Revision ID: 2f8c9d1a4b70
Revises: 7d9e1c84b2f0
Create Date: 2026-09-06
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "2f8c9d1a4b70"
down_revision: str | Sequence[str] | None = "7d9e1c84b2f0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("market_listings") as batch:
        batch.add_column(sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(
            sa.Column("status", sa.String(length=20), nullable=False, server_default="ACTIVE")
        )
        batch.create_check_constraint(
            "ck_market_listings_status",
            "status IN ('ACTIVE','INACTIVE','SOLD','UNKNOWN')",
        )
        batch.create_index("ix_market_listings_status", ["status"], unique=False)

    op.execute("UPDATE market_listings SET last_seen_at = observed_at WHERE last_seen_at IS NULL")

    with op.batch_alter_table("market_sync_states") as batch:
        batch.add_column(sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("last_duration_ms", sa.Integer(), nullable=True))
        batch.add_column(
            sa.Column("last_items_received", sa.Integer(), nullable=False, server_default="0")
        )
        batch.add_column(
            sa.Column("last_items_created", sa.Integer(), nullable=False, server_default="0")
        )
        batch.add_column(
            sa.Column("last_items_updated", sa.Integer(), nullable=False, server_default="0")
        )
        batch.add_column(sa.Column("last_error_code", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("last_error_message", sa.String(length=1024), nullable=True))
        batch.add_column(
            sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0")
        )
        batch.add_column(sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True))

    op.execute(
        "UPDATE market_sync_states "
        "SET last_success_at = last_sync_at "
        "WHERE last_success_at IS NULL AND last_sync_at IS NOT NULL"
    )
    op.execute(
        "UPDATE market_sync_states "
        "SET last_failure_at = last_error_at, last_error_message = last_error "
        "WHERE last_error_at IS NOT NULL"
    )

    op.create_table(
        "market_opportunities",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("mode", sa.String(length=8), nullable=False),
        sa.Column("listing_id", sa.String(length=36), nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("market_hash_name", sa.String(length=512), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("estimated_value_eur", sa.Numeric(precision=20, scale=8), nullable=True),
        sa.Column("potential_profit_eur", sa.Numeric(precision=20, scale=8), nullable=True),
        sa.Column("roi", sa.Numeric(precision=20, scale=8), nullable=True),
        sa.Column("reason", sa.String(length=1024), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("mode IN ('demo', 'live')"),
        sa.CheckConstraint("score >= 0 AND score <= 100"),
        sa.CheckConstraint("status IN ('ACTIVE','INACTIVE')"),
        sa.ForeignKeyConstraint(["listing_id"], ["market_listings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("mode", "listing_id", name="uq_opportunity_listing"),
    )
    op.create_index(
        "ix_market_opportunities_listing_id",
        "market_opportunities",
        ["listing_id"],
        unique=False,
    )
    op.create_index(
        "ix_market_opportunities_market_hash_name",
        "market_opportunities",
        ["market_hash_name"],
        unique=False,
    )
    op.create_index("ix_market_opportunities_mode", "market_opportunities", ["mode"], unique=False)
    op.create_index(
        "ix_market_opportunities_platform",
        "market_opportunities",
        ["platform"],
        unique=False,
    )
    op.create_index(
        "ix_market_opportunities_status_score",
        "market_opportunities",
        ["mode", "status", "score"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_market_opportunities_status_score", table_name="market_opportunities")
    op.drop_index("ix_market_opportunities_platform", table_name="market_opportunities")
    op.drop_index("ix_market_opportunities_mode", table_name="market_opportunities")
    op.drop_index("ix_market_opportunities_market_hash_name", table_name="market_opportunities")
    op.drop_index("ix_market_opportunities_listing_id", table_name="market_opportunities")
    op.drop_table("market_opportunities")

    with op.batch_alter_table("market_sync_states") as batch:
        batch.drop_column("next_run_at")
        batch.drop_column("consecutive_failures")
        batch.drop_column("last_error_message")
        batch.drop_column("last_error_code")
        batch.drop_column("last_items_updated")
        batch.drop_column("last_items_created")
        batch.drop_column("last_items_received")
        batch.drop_column("last_duration_ms")
        batch.drop_column("last_failure_at")
        batch.drop_column("last_success_at")

    with op.batch_alter_table("market_listings") as batch:
        batch.drop_index("ix_market_listings_status")
        batch.drop_constraint("ck_market_listings_status", type_="check")
        batch.drop_column("status")
        batch.drop_column("last_seen_at")
