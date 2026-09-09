"""add market data v2 models

Revision ID: 9b7c6d5e4f30
Revises: 2f8c9d1a4b70
Create Date: 2026-09-08
"""

import hashlib
from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa

from alembic import op

revision: str = "9b7c6d5e4f30"
down_revision: str | Sequence[str] | None = "2f8c9d1a4b70"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _identity_key(market_hash_name: str, paint_index: int | None, variant: str | None) -> str:
    raw = f"{market_hash_name.strip()}|{paint_index or ''}|{(variant or '').strip().lower()}"
    return hashlib.sha256(raw.encode()).hexdigest()


def upgrade() -> None:
    op.create_table(
        "canonical_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("mode", sa.String(length=8), nullable=False),
        sa.Column("identity_key", sa.String(length=64), nullable=False),
        sa.Column("market_hash_name", sa.String(length=512), nullable=False),
        sa.Column("paint_index", sa.Integer(), nullable=True),
        sa.Column("variant", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("mode IN ('demo', 'live')"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("mode", "identity_key", name="uq_canonical_item_identity"),
    )
    op.create_index(
        "ix_canonical_item_lookup",
        "canonical_items",
        ["mode", "market_hash_name"],
        unique=False,
    )

    with op.batch_alter_table("cs2_items") as batch:
        batch.add_column(sa.Column("canonical_item_id", sa.String(length=36), nullable=True))
        batch.add_column(sa.Column("asset_id", sa.String(length=256), nullable=True))
        batch.add_column(sa.Column("def_index", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("rarity", sa.String(length=128), nullable=True))
        batch.add_column(sa.Column("quality", sa.String(length=128), nullable=True))
        batch.add_column(sa.Column("collection", sa.String(length=256), nullable=True))
        batch.add_column(sa.Column("tradable", sa.Boolean(), nullable=True))
        batch.add_column(sa.Column("tradable_at", sa.DateTime(timezone=True), nullable=True))
        batch.create_foreign_key(
            "fk_cs2_items_canonical_item_id",
            "canonical_items",
            ["canonical_item_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_index("ix_cs2_items_canonical_item_id", ["canonical_item_id"], unique=False)

    with op.batch_alter_table("market_listings") as batch:
        batch.add_column(sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE market_listings SET first_seen_at = observed_at WHERE first_seen_at IS NULL")
    with op.batch_alter_table("market_listings") as batch:
        batch.alter_column(
            "first_seen_at", existing_type=sa.DateTime(timezone=True), nullable=False
        )

    _backfill_canonical_items()
    _create_market_fact_tables()
    _create_financial_tables()


def _backfill_canonical_items() -> None:
    bind = op.get_bind()
    items = sa.table(
        "cs2_items",
        sa.column("id", sa.String),
        sa.column("mode", sa.String),
        sa.column("market_hash_name", sa.String),
        sa.column("paint_index", sa.Integer),
        sa.column("doppler_phase", sa.String),
        sa.column("canonical_item_id", sa.String),
    )
    canonical = sa.table(
        "canonical_items",
        sa.column("id", sa.String),
        sa.column("mode", sa.String),
        sa.column("identity_key", sa.String),
        sa.column("market_hash_name", sa.String),
        sa.column("paint_index", sa.Integer),
        sa.column("variant", sa.String),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    rows = bind.execute(
        sa.select(
            items.c.id,
            items.c.mode,
            items.c.market_hash_name,
            items.c.paint_index,
            items.c.doppler_phase,
        )
    ).mappings()
    now = datetime.now(UTC)
    identities: dict[tuple[str, str], str] = {}
    for row in rows:
        key = _identity_key(row.market_hash_name, row.paint_index, row.doppler_phase)
        identity = (row.mode, key)
        canonical_id = identities.get(identity)
        if canonical_id is None:
            canonical_id = str(uuid4())
            identities[identity] = canonical_id
            bind.execute(
                canonical.insert().values(
                    id=canonical_id,
                    mode=row.mode,
                    identity_key=key,
                    market_hash_name=row.market_hash_name,
                    paint_index=row.paint_index,
                    variant=row.doppler_phase,
                    created_at=now,
                    updated_at=now,
                )
            )
        bind.execute(
            items.update().where(items.c.id == row.id).values(canonical_item_id=canonical_id)
        )


def _create_market_fact_tables() -> None:
    op.create_table(
        "aggregate_market_stats",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("mode", sa.String(length=8), nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("market_hash_name", sa.String(length=512), nullable=False),
        sa.Column("window_code", sa.String(length=8), nullable=False),
        sa.Column("min_price", sa.Numeric(precision=20, scale=8), nullable=True),
        sa.Column("max_price", sa.Numeric(precision=20, scale=8), nullable=True),
        sa.Column("avg_price", sa.Numeric(precision=20, scale=8), nullable=True),
        sa.Column("median_price", sa.Numeric(precision=20, scale=8), nullable=True),
        sa.Column("volume", sa.Integer(), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("min_eur_reference", sa.Numeric(precision=20, scale=8), nullable=True),
        sa.Column("max_eur_reference", sa.Numeric(precision=20, scale=8), nullable=True),
        sa.Column("avg_eur_reference", sa.Numeric(precision=20, scale=8), nullable=True),
        sa.Column("median_eur_reference", sa.Numeric(precision=20, scale=8), nullable=True),
        sa.Column("fx_rate", sa.Numeric(precision=24, scale=12), nullable=True),
        sa.Column("fx_rate_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fx_rate_source", sa.String(length=512), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("mode IN ('demo', 'live')"),
        sa.CheckConstraint("window_code IN ('24H', '7D', '30D', '90D')"),
        sa.CheckConstraint("min_price IS NULL OR min_price >= 0"),
        sa.CheckConstraint("max_price IS NULL OR max_price >= 0"),
        sa.CheckConstraint("avg_price IS NULL OR avg_price >= 0"),
        sa.CheckConstraint("median_price IS NULL OR median_price >= 0"),
        sa.CheckConstraint("volume IS NULL OR volume >= 0"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fingerprint", name="uq_aggregate_market_stat_fingerprint"),
    )
    op.create_index(
        "ix_aggregate_market_stat_lookup",
        "aggregate_market_stats",
        ["mode", "market_hash_name", "platform", "window_code", "observed_at"],
        unique=False,
    )
    op.create_table(
        "realized_sales",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("mode", sa.String(length=8), nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("external_id", sa.String(length=256), nullable=False),
        sa.Column("canonical_item_id", sa.String(length=36), nullable=True),
        sa.Column("item_id", sa.String(length=36), nullable=True),
        sa.Column("market_hash_name", sa.String(length=512), nullable=False),
        sa.Column("price_original", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("currency_original", sa.String(length=3), nullable=False),
        sa.Column("price_eur_reference", sa.Numeric(precision=20, scale=8), nullable=True),
        sa.Column("fx_rate", sa.Numeric(precision=24, scale=12), nullable=True),
        sa.Column("fx_rate_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fx_rate_source", sa.String(length=512), nullable=True),
        sa.Column("sold_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("transaction_type", sa.String(length=64), nullable=True),
        sa.Column("attributes", sa.JSON(), nullable=False),
        sa.CheckConstraint("mode IN ('demo', 'live')"),
        sa.CheckConstraint("price_original >= 0"),
        sa.ForeignKeyConstraint(["canonical_item_id"], ["canonical_items.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["item_id"], ["cs2_items.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("mode", "platform", "external_id", name="uq_realized_sale_source"),
    )
    op.create_index(
        "ix_realized_sale_lookup",
        "realized_sales",
        ["mode", "market_hash_name", "sold_at"],
        unique=False,
    )
    op.create_table(
        "buy_order_observations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("mode", sa.String(length=8), nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("market_hash_name", sa.String(length=512), nullable=False),
        sa.Column("price_original", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("currency_original", sa.String(length=3), nullable=False),
        sa.Column("price_eur_reference", sa.Numeric(precision=20, scale=8), nullable=True),
        sa.Column("fx_rate", sa.Numeric(precision=24, scale=12), nullable=True),
        sa.Column("fx_rate_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fx_rate_source", sa.String(length=512), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("attributes", sa.JSON(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("mode IN ('demo', 'live')"),
        sa.CheckConstraint("price_original >= 0"),
        sa.CheckConstraint("quantity >= 0"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fingerprint", name="uq_buy_order_observation_fingerprint"),
    )
    op.create_index(
        "ix_buy_order_lookup",
        "buy_order_observations",
        ["mode", "market_hash_name", "platform", "observed_at"],
        unique=False,
    )


def _create_financial_tables() -> None:
    op.create_table(
        "fx_rates",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("base_currency", sa.String(length=3), nullable=False),
        sa.Column("quote_currency", sa.String(length=3), nullable=False),
        sa.Column("rate", sa.Numeric(precision=24, scale=12), nullable=False),
        sa.Column("source", sa.String(length=512), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rate_type", sa.String(length=20), nullable=False),
        sa.CheckConstraint("rate > 0"),
        sa.CheckConstraint("rate_type IN ('REFERENCE', 'EFFECTIVE')"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "base_currency",
            "quote_currency",
            "source",
            "rate_type",
            "observed_at",
            name="uq_fx_rate_observation",
        ),
    )
    op.create_index(
        "ix_fx_rate_lookup",
        "fx_rates",
        ["base_currency", "quote_currency", "rate_type", "observed_at"],
        unique=False,
    )
    op.create_table(
        "platform_fee_schedules",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("fee_type", sa.String(length=20), nullable=False),
        sa.Column("rate", sa.Numeric(precision=16, scale=12), nullable=True),
        sa.Column("fixed_amount", sa.Numeric(precision=20, scale=8), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("min_amount", sa.Numeric(precision=20, scale=8), nullable=True),
        sa.Column("max_amount", sa.Numeric(precision=20, scale=8), nullable=True),
        sa.Column("applies_to", sa.String(length=256), nullable=True),
        sa.Column("source", sa.String(length=2048), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.CheckConstraint(
            "fee_type IN ('BUY','SELL','DEPOSIT','WITHDRAW','TRADE','PAYMENT','FX')"
        ),
        sa.CheckConstraint("rate IS NULL OR (rate >= 0 AND rate <= 1)"),
        sa.CheckConstraint("fixed_amount IS NULL OR fixed_amount >= 0"),
        sa.CheckConstraint("min_amount IS NULL OR min_amount >= 0"),
        sa.CheckConstraint("max_amount IS NULL OR max_amount >= 0"),
        sa.CheckConstraint("rate IS NOT NULL OR fixed_amount IS NOT NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_platform_fee_lookup",
        "platform_fee_schedules",
        ["platform", "fee_type", "valid_from"],
        unique=False,
    )
    op.create_table(
        "trade_quotes",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("mode", sa.String(length=8), nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("external_id", sa.String(length=256), nullable=True),
        sa.Column("given_items", sa.JSON(), nullable=False),
        sa.Column("received_items", sa.JSON(), nullable=False),
        sa.Column("platform_given_value", sa.Numeric(precision=20, scale=8), nullable=True),
        sa.Column("platform_received_value", sa.Numeric(precision=20, scale=8), nullable=True),
        sa.Column("real_given_cash_value_eur", sa.Numeric(precision=20, scale=8), nullable=True),
        sa.Column("real_received_cash_value_eur", sa.Numeric(precision=20, scale=8), nullable=True),
        sa.Column("display_currency", sa.String(length=3), nullable=False),
        sa.Column("fees", sa.JSON(), nullable=False),
        sa.Column("effective_spread", sa.Numeric(precision=20, scale=8), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_quality", sa.Integer(), nullable=False),
        sa.Column("confidence", sa.Integer(), nullable=False),
        sa.CheckConstraint("mode IN ('demo', 'live')"),
        sa.CheckConstraint("source_quality >= 0 AND source_quality <= 100"),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 100"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_trade_quote_lookup",
        "trade_quotes",
        ["mode", "platform", "created_at"],
        unique=False,
    )
    op.create_table(
        "watch_rules",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("mode", sa.String(length=8), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("filters", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("mode IN ('demo', 'live')"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_watch_rule_enabled",
        "watch_rules",
        ["mode", "enabled", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_watch_rule_enabled", table_name="watch_rules")
    op.drop_table("watch_rules")
    op.drop_index("ix_trade_quote_lookup", table_name="trade_quotes")
    op.drop_table("trade_quotes")
    op.drop_index("ix_platform_fee_lookup", table_name="platform_fee_schedules")
    op.drop_table("platform_fee_schedules")
    op.drop_index("ix_fx_rate_lookup", table_name="fx_rates")
    op.drop_table("fx_rates")
    op.drop_index("ix_buy_order_lookup", table_name="buy_order_observations")
    op.drop_table("buy_order_observations")
    op.drop_index("ix_realized_sale_lookup", table_name="realized_sales")
    op.drop_table("realized_sales")
    op.drop_index("ix_aggregate_market_stat_lookup", table_name="aggregate_market_stats")
    op.drop_table("aggregate_market_stats")

    with op.batch_alter_table("market_listings") as batch:
        batch.drop_column("first_seen_at")
    with op.batch_alter_table("cs2_items") as batch:
        batch.drop_index("ix_cs2_items_canonical_item_id")
        batch.drop_constraint("fk_cs2_items_canonical_item_id", type_="foreignkey")
        batch.drop_column("tradable_at")
        batch.drop_column("tradable")
        batch.drop_column("collection")
        batch.drop_column("quality")
        batch.drop_column("rarity")
        batch.drop_column("def_index")
        batch.drop_column("asset_id")
        batch.drop_column("canonical_item_id")
    op.drop_index("ix_canonical_item_lookup", table_name="canonical_items")
    op.drop_table("canonical_items")
