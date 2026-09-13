"""add listing analysis snapshots

Revision ID: e6f7a8b9c0d1
Revises: c4e8a10d7b21
Create Date: 2026-09-09
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e6f7a8b9c0d1"
down_revision: str | Sequence[str] | None = "c4e8a10d7b21"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_cs2_item_float_value", "cs2_items", ["float_value"])
    op.create_index("ix_cs2_item_paint_seed", "cs2_items", ["paint_seed"])
    op.create_index(
        "ix_market_listing_scan",
        "market_listings",
        ["mode", "status", "observed_at"],
    )
    op.create_index(
        "ix_market_listing_price",
        "market_listings",
        ["mode", "status", "price_eur_reference"],
    )
    op.create_table(
        "listing_analysis_snapshots",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("mode", sa.String(length=8), nullable=False),
        sa.Column("listing_id", sa.String(length=36), nullable=False),
        sa.Column("estimated_value_eur", sa.Numeric(precision=20, scale=8), nullable=True),
        sa.Column("potential_profit_eur", sa.Numeric(precision=20, scale=8), nullable=True),
        sa.Column("roi", sa.Numeric(precision=20, scale=8), nullable=True),
        sa.Column("opportunity_score", sa.Integer(), nullable=True),
        sa.Column("float_score", sa.Integer(), nullable=True),
        sa.Column("liquidity_score", sa.Integer(), nullable=True),
        sa.Column("liquidity_category", sa.String(length=20), nullable=True),
        sa.Column("liquidity_evidence_completeness", sa.Integer(), nullable=True),
        sa.Column("confidence", sa.Integer(), nullable=True),
        sa.Column("reference_method", sa.String(length=64), nullable=True),
        sa.Column("reference_sources", sa.JSON(), nullable=False),
        sa.Column("reference_calculated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("spread_eur", sa.Numeric(precision=20, scale=8), nullable=True),
        sa.Column("spread_percent", sa.Numeric(precision=20, scale=8), nullable=True),
        sa.Column("risk_score", sa.Integer(), nullable=True),
        sa.Column("risk_factors", sa.JSON(), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("mode IN ('demo', 'live')"),
        sa.CheckConstraint(
            "opportunity_score IS NULL OR (opportunity_score >= 0 AND opportunity_score <= 100)"
        ),
        sa.CheckConstraint("float_score IS NULL OR (float_score >= 0 AND float_score <= 100)"),
        sa.CheckConstraint(
            "liquidity_score IS NULL OR (liquidity_score >= 0 AND liquidity_score <= 100)"
        ),
        sa.CheckConstraint(
            "liquidity_evidence_completeness IS NULL OR "
            "(liquidity_evidence_completeness >= 0 AND "
            "liquidity_evidence_completeness <= 100)"
        ),
        sa.CheckConstraint(
            "liquidity_category IS NULL OR liquidity_category IN "
            "('VERY_LOW','LOW','MEDIUM','HIGH','VERY_HIGH')"
        ),
        sa.CheckConstraint("confidence IS NULL OR (confidence >= 0 AND confidence <= 100)"),
        sa.CheckConstraint("risk_score IS NULL OR (risk_score >= 0 AND risk_score <= 100)"),
        sa.ForeignKeyConstraint(["listing_id"], ["market_listings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("mode", "listing_id", name="uq_listing_analysis_snapshot"),
    )
    op.create_index(
        "ix_listing_analysis_opportunity",
        "listing_analysis_snapshots",
        ["mode", "opportunity_score"],
    )
    op.create_index(
        "ix_listing_analysis_liquidity",
        "listing_analysis_snapshots",
        ["mode", "liquidity_score"],
    )
    op.create_index(
        "ix_listing_analysis_risk",
        "listing_analysis_snapshots",
        ["mode", "risk_score"],
    )
    op.create_index(
        "ix_listing_analysis_snapshots_listing_id",
        "listing_analysis_snapshots",
        ["listing_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_listing_analysis_snapshots_listing_id",
        table_name="listing_analysis_snapshots",
    )
    op.drop_index("ix_listing_analysis_risk", table_name="listing_analysis_snapshots")
    op.drop_index("ix_listing_analysis_liquidity", table_name="listing_analysis_snapshots")
    op.drop_index("ix_listing_analysis_opportunity", table_name="listing_analysis_snapshots")
    op.drop_table("listing_analysis_snapshots")
    op.drop_index("ix_market_listing_price", table_name="market_listings")
    op.drop_index("ix_market_listing_scan", table_name="market_listings")
    op.drop_index("ix_cs2_item_paint_seed", table_name="cs2_items")
    op.drop_index("ix_cs2_item_float_value", table_name="cs2_items")
