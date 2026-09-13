from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return str(uuid4())


class Base(DeclarativeBase):
    pass


class CanonicalItem(Base):
    __tablename__ = "canonical_items"
    __table_args__ = (
        UniqueConstraint("mode", "identity_key", name="uq_canonical_item_identity"),
        CheckConstraint("mode IN ('demo', 'live')"),
        Index("ix_canonical_item_lookup", "mode", "market_hash_name"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    mode: Mapped[str] = mapped_column(String(8))
    identity_key: Mapped[str] = mapped_column(String(64))
    market_hash_name: Mapped[str] = mapped_column(String(512))
    paint_index: Mapped[int | None] = mapped_column(Integer)
    variant: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class CS2Item(Base):
    __tablename__ = "cs2_items"
    __table_args__ = (
        UniqueConstraint("mode", "platform", "external_id", name="uq_item_source"),
        CheckConstraint("float_value IS NULL OR (float_value >= 0 AND float_value <= 1)"),
        CheckConstraint("paint_seed IS NULL OR (paint_seed >= 0 AND paint_seed <= 1000)"),
        CheckConstraint(
            "fade_percentage IS NULL OR (fade_percentage >= 0 AND fade_percentage <= 100)"
        ),
        CheckConstraint("mode IN ('demo', 'live')"),
        Index("ix_cs2_item_float_value", "float_value"),
        Index("ix_cs2_item_paint_seed", "paint_seed"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    canonical_item_id: Mapped[str | None] = mapped_column(
        ForeignKey("canonical_items.id", ondelete="SET NULL"), index=True
    )
    mode: Mapped[str] = mapped_column(String(8), index=True)
    platform: Mapped[str] = mapped_column(String(32))
    external_id: Mapped[str] = mapped_column(String(256))
    asset_id: Mapped[str | None] = mapped_column(String(256))
    def_index: Mapped[int | None] = mapped_column(Integer)
    market_hash_name: Mapped[str] = mapped_column(String(512), index=True)
    weapon: Mapped[str | None] = mapped_column(String(128))
    skin: Mapped[str | None] = mapped_column(String(256))
    exterior: Mapped[str | None] = mapped_column(String(64))
    stattrak: Mapped[bool | None] = mapped_column(Boolean)
    souvenir: Mapped[bool | None] = mapped_column(Boolean)
    float_value: Mapped[Decimal | None] = mapped_column(Numeric(24, 20))
    paint_index: Mapped[int | None] = mapped_column(Integer)
    paint_seed: Mapped[int | None] = mapped_column(Integer)
    doppler_phase: Mapped[str | None] = mapped_column(String(64))
    fade_percentage: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    rarity: Mapped[str | None] = mapped_column(String(128))
    quality: Mapped[str | None] = mapped_column(String(128))
    collection: Mapped[str | None] = mapped_column(String(256))
    scm_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    scm_volume: Mapped[int | None] = mapped_column(Integer)
    source_attributes: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    inspect_link: Mapped[str | None] = mapped_column(String(2048))
    tradable: Mapped[bool | None] = mapped_column(Boolean)
    tradable_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    canonical_item: Mapped[CanonicalItem | None] = relationship()
    stickers: Mapped[list["ItemSticker"]] = relationship(cascade="all, delete-orphan")


class ItemSticker(Base):
    __tablename__ = "item_stickers"
    __table_args__ = (CheckConstraint("wear IS NULL OR (wear >= 0 AND wear <= 1)"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    item_id: Mapped[str] = mapped_column(ForeignKey("cs2_items.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(256))
    slot: Mapped[int | None] = mapped_column(Integer)
    wear: Mapped[Decimal | None] = mapped_column(Numeric(20, 12))
    steam_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    steam_volume: Mapped[int | None] = mapped_column(Integer)
    estimated_applied_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))


class MarketListing(Base):
    __tablename__ = "market_listings"
    __table_args__ = (
        UniqueConstraint("mode", "platform", "external_id", name="uq_listing_source"),
        CheckConstraint("price_original >= 0"),
        CheckConstraint("mode IN ('demo', 'live')"),
        CheckConstraint("status IN ('ACTIVE','INACTIVE','SOLD','UNKNOWN')"),
        Index("ix_market_listing_scan", "mode", "status", "observed_at"),
        Index("ix_market_listing_price", "mode", "status", "price_eur_reference"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    mode: Mapped[str] = mapped_column(String(8), index=True)
    platform: Mapped[str] = mapped_column(String(32), index=True)
    external_id: Mapped[str] = mapped_column(String(256))
    item_id: Mapped[str] = mapped_column(ForeignKey("cs2_items.id", ondelete="CASCADE"), index=True)
    price_original: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    currency_original: Mapped[str] = mapped_column(String(3))
    price_eur_reference: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    fx_rate: Mapped[Decimal | None] = mapped_column(Numeric(24, 12))
    fx_rate_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fx_rate_source: Mapped[str | None] = mapped_column(String(512))
    seller_type: Mapped[str | None] = mapped_column(String(64))
    listing_url: Mapped[str | None] = mapped_column(String(2048))
    listed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", index=True)
    warnings: Mapped[list[str]] = mapped_column(JSON, default=list)
    item: Mapped[CS2Item] = relationship()


class AggregateMarketStat(Base):
    __tablename__ = "aggregate_market_stats"
    __table_args__ = (
        UniqueConstraint("fingerprint", name="uq_aggregate_market_stat_fingerprint"),
        CheckConstraint("mode IN ('demo', 'live')"),
        CheckConstraint("window_code IN ('24H', '7D', '30D', '90D')"),
        CheckConstraint("min_price IS NULL OR min_price >= 0"),
        CheckConstraint("max_price IS NULL OR max_price >= 0"),
        CheckConstraint("avg_price IS NULL OR avg_price >= 0"),
        CheckConstraint("median_price IS NULL OR median_price >= 0"),
        CheckConstraint("volume IS NULL OR volume >= 0"),
        Index(
            "ix_aggregate_market_stat_lookup",
            "mode",
            "market_hash_name",
            "platform",
            "window_code",
            "observed_at",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    fingerprint: Mapped[str] = mapped_column(String(64))
    mode: Mapped[str] = mapped_column(String(8))
    platform: Mapped[str] = mapped_column(String(32))
    market_hash_name: Mapped[str] = mapped_column(String(512))
    window_code: Mapped[str] = mapped_column(String(8))
    min_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    max_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    avg_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    median_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    volume: Mapped[int | None] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3))
    min_eur_reference: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    max_eur_reference: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    avg_eur_reference: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    median_eur_reference: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    fx_rate: Mapped[Decimal | None] = mapped_column(Numeric(24, 12))
    fx_rate_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fx_rate_source: Mapped[str | None] = mapped_column(String(512))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RealizedSale(Base):
    __tablename__ = "realized_sales"
    __table_args__ = (
        UniqueConstraint("fingerprint", name="uq_realized_sale_fingerprint"),
        UniqueConstraint("mode", "platform", "external_id", name="uq_realized_sale_source"),
        CheckConstraint("mode IN ('demo', 'live')"),
        CheckConstraint("price_original >= 0"),
        Index("ix_realized_sale_lookup", "mode", "market_hash_name", "sold_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    fingerprint: Mapped[str] = mapped_column(String(64))
    mode: Mapped[str] = mapped_column(String(8))
    platform: Mapped[str] = mapped_column(String(32))
    external_id: Mapped[str | None] = mapped_column(String(256))
    canonical_item_id: Mapped[str | None] = mapped_column(
        ForeignKey("canonical_items.id", ondelete="SET NULL")
    )
    item_id: Mapped[str | None] = mapped_column(ForeignKey("cs2_items.id", ondelete="SET NULL"))
    market_hash_name: Mapped[str] = mapped_column(String(512))
    price_original: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    currency_original: Mapped[str] = mapped_column(String(3))
    price_eur_reference: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    fx_rate: Mapped[Decimal | None] = mapped_column(Numeric(24, 12))
    fx_rate_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fx_rate_source: Mapped[str | None] = mapped_column(String(512))
    sold_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    transaction_type: Mapped[str | None] = mapped_column(String(64))
    attributes: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)


class BuyOrderObservation(Base):
    __tablename__ = "buy_order_observations"
    __table_args__ = (
        UniqueConstraint("fingerprint", name="uq_buy_order_observation_fingerprint"),
        CheckConstraint("mode IN ('demo', 'live')"),
        CheckConstraint("price_original >= 0"),
        CheckConstraint("quantity >= 0"),
        Index("ix_buy_order_lookup", "mode", "market_hash_name", "platform", "observed_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    fingerprint: Mapped[str] = mapped_column(String(64))
    mode: Mapped[str] = mapped_column(String(8))
    platform: Mapped[str] = mapped_column(String(32))
    market_hash_name: Mapped[str] = mapped_column(String(512))
    price_original: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    currency_original: Mapped[str] = mapped_column(String(3))
    price_eur_reference: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    fx_rate: Mapped[Decimal | None] = mapped_column(Numeric(24, 12))
    fx_rate_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fx_rate_source: Mapped[str | None] = mapped_column(String(512))
    quantity: Mapped[int] = mapped_column(Integer)
    attributes: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PriceObservation(Base):
    __tablename__ = "price_observations"
    __table_args__ = (
        UniqueConstraint("fingerprint", name="uq_observation_fingerprint"),
        CheckConstraint("price >= 0"),
        CheckConstraint("volume IS NULL OR volume >= 0"),
        CheckConstraint("mode IN ('demo', 'live')"),
        CheckConstraint(
            "observation_type IN ('LISTING','SALE','BUY_ORDER','TRADE_VALUE','AGGREGATE')"
        ),
        Index("ix_observation_lookup", "mode", "market_hash_name", "timestamp"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    fingerprint: Mapped[str] = mapped_column(String(64))
    mode: Mapped[str] = mapped_column(String(8))
    market_hash_name: Mapped[str] = mapped_column(String(512))
    platform: Mapped[str] = mapped_column(String(32))
    price: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    currency: Mapped[str] = mapped_column(String(3))
    price_eur_reference: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    fx_rate: Mapped[Decimal | None] = mapped_column(Numeric(24, 12))
    fx_rate_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fx_rate_source: Mapped[str | None] = mapped_column(String(512))
    observation_type: Mapped[str] = mapped_column(String(20))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    volume: Mapped[int | None] = mapped_column(Integer)


class MarketSyncState(Base):
    __tablename__ = "market_sync_states"
    __table_args__ = (UniqueConstraint("mode", "platform", name="uq_sync_source"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    mode: Mapped[str] = mapped_column(String(8))
    platform: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(20))
    message: Mapped[str] = mapped_column(String(1024))
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(1024))
    last_error_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_duration_ms: Mapped[int | None] = mapped_column(Integer)
    last_items_received: Mapped[int] = mapped_column(Integer, default=0)
    last_items_created: Mapped[int] = mapped_column(Integer, default=0)
    last_items_updated: Mapped[int] = mapped_column(Integer, default=0)
    last_error_code: Mapped[str | None] = mapped_column(String(64))
    last_error_message: Mapped[str | None] = mapped_column(String(1024))
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MarketOpportunity(Base):
    __tablename__ = "market_opportunities"
    __table_args__ = (
        UniqueConstraint("mode", "listing_id", name="uq_opportunity_listing"),
        CheckConstraint("mode IN ('demo', 'live')"),
        CheckConstraint("status IN ('ACTIVE','INACTIVE')"),
        CheckConstraint("score >= 0 AND score <= 100"),
        Index("ix_market_opportunities_status_score", "mode", "status", "score"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    mode: Mapped[str] = mapped_column(String(8), index=True)
    listing_id: Mapped[str] = mapped_column(
        ForeignKey("market_listings.id", ondelete="CASCADE"), index=True
    )
    platform: Mapped[str] = mapped_column(String(32), index=True)
    market_hash_name: Mapped[str] = mapped_column(String(512), index=True)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")
    score: Mapped[int] = mapped_column(Integer)
    estimated_value_eur: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    potential_profit_eur: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    roi: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    reason: Mapped[str] = mapped_column(String(1024))
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    listing: Mapped[MarketListing] = relationship()


class ListingAnalysisSnapshot(Base):
    __tablename__ = "listing_analysis_snapshots"
    __table_args__ = (
        UniqueConstraint("mode", "listing_id", name="uq_listing_analysis_snapshot"),
        CheckConstraint("mode IN ('demo', 'live')"),
        CheckConstraint(
            "opportunity_score IS NULL OR (opportunity_score >= 0 AND opportunity_score <= 100)"
        ),
        CheckConstraint("float_score IS NULL OR (float_score >= 0 AND float_score <= 100)"),
        CheckConstraint(
            "liquidity_score IS NULL OR (liquidity_score >= 0 AND liquidity_score <= 100)"
        ),
        CheckConstraint(
            "liquidity_evidence_completeness IS NULL OR "
            "(liquidity_evidence_completeness >= 0 AND liquidity_evidence_completeness <= 100)"
        ),
        CheckConstraint(
            "liquidity_category IS NULL OR liquidity_category IN "
            "('VERY_LOW','LOW','MEDIUM','HIGH','VERY_HIGH')"
        ),
        CheckConstraint("confidence IS NULL OR (confidence >= 0 AND confidence <= 100)"),
        CheckConstraint("risk_score IS NULL OR (risk_score >= 0 AND risk_score <= 100)"),
        Index("ix_listing_analysis_opportunity", "mode", "opportunity_score"),
        Index("ix_listing_analysis_liquidity", "mode", "liquidity_score"),
        Index("ix_listing_analysis_risk", "mode", "risk_score"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    mode: Mapped[str] = mapped_column(String(8))
    listing_id: Mapped[str] = mapped_column(
        ForeignKey("market_listings.id", ondelete="CASCADE"), index=True
    )
    estimated_value_eur: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    potential_profit_eur: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    roi: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    opportunity_score: Mapped[int | None] = mapped_column(Integer)
    float_score: Mapped[int | None] = mapped_column(Integer)
    liquidity_score: Mapped[int | None] = mapped_column(Integer)
    liquidity_category: Mapped[str | None] = mapped_column(String(20))
    liquidity_evidence_completeness: Mapped[int | None] = mapped_column(Integer)
    confidence: Mapped[int | None] = mapped_column(Integer)
    reference_method: Mapped[str | None] = mapped_column(String(64))
    reference_sources: Mapped[list[str]] = mapped_column(JSON, default=list)
    reference_calculated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    spread_eur: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    spread_percent: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    risk_score: Mapped[int | None] = mapped_column(Integer)
    risk_factors: Mapped[list[str]] = mapped_column(JSON, default=list)
    warnings: Mapped[list[str]] = mapped_column(JSON, default=list)
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    listing: Mapped[MarketListing] = relationship()


class PatternRule(Base):
    __tablename__ = "pattern_rules"
    __table_args__ = (
        CheckConstraint("confidence >= 0 AND confidence <= 100"),
        CheckConstraint("paint_seed >= 0 AND paint_seed <= 1000"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    skin: Mapped[str] = mapped_column(String(256))
    paint_seed: Mapped[int] = mapped_column(Integer)
    category: Mapped[str] = mapped_column(String(64))
    tier: Mapped[str | None] = mapped_column(String(64))
    premium_estimate: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    confidence: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(2048))
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class FXRate(Base):
    __tablename__ = "fx_rates"
    __table_args__ = (
        UniqueConstraint(
            "base_currency",
            "quote_currency",
            "source",
            "rate_type",
            "observed_at",
            name="uq_fx_rate_observation",
        ),
        CheckConstraint("rate > 0"),
        CheckConstraint("rate_type IN ('REFERENCE', 'EFFECTIVE')"),
        Index("ix_fx_rate_lookup", "base_currency", "quote_currency", "rate_type", "observed_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    base_currency: Mapped[str] = mapped_column(String(3))
    quote_currency: Mapped[str] = mapped_column(String(3))
    rate: Mapped[Decimal] = mapped_column(Numeric(24, 12))
    source: Mapped[str] = mapped_column(String(512))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    rate_type: Mapped[str] = mapped_column(String(20))


class PlatformFeeSchedule(Base):
    __tablename__ = "platform_fee_schedules"
    __table_args__ = (
        CheckConstraint("fee_type IN ('BUY','SELL','DEPOSIT','WITHDRAW','TRADE','PAYMENT','FX')"),
        CheckConstraint("rate IS NULL OR (rate >= 0 AND rate <= 1)"),
        CheckConstraint("fixed_amount IS NULL OR fixed_amount >= 0"),
        CheckConstraint("minimum_fee IS NULL OR minimum_fee >= 0"),
        CheckConstraint("min_amount IS NULL OR min_amount >= 0"),
        CheckConstraint("max_amount IS NULL OR max_amount >= 0"),
        CheckConstraint("rate IS NOT NULL OR fixed_amount IS NOT NULL"),
        Index("ix_platform_fee_lookup", "platform", "fee_type", "valid_from"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    platform: Mapped[str] = mapped_column(String(32))
    fee_type: Mapped[str] = mapped_column(String(20))
    rate: Mapped[Decimal | None] = mapped_column(Numeric(16, 12))
    fixed_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    minimum_fee: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    currency: Mapped[str | None] = mapped_column(String(3))
    min_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    max_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    applies_to: Mapped[str | None] = mapped_column(String(256))
    source: Mapped[str] = mapped_column(String(2048))
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    details: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)


class TradeQuote(Base):
    __tablename__ = "trade_quotes"
    __table_args__ = (
        CheckConstraint("mode IN ('demo', 'live')"),
        CheckConstraint("source_quality >= 0 AND source_quality <= 100"),
        CheckConstraint("confidence >= 0 AND confidence <= 100"),
        Index("ix_trade_quote_lookup", "mode", "platform", "created_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    mode: Mapped[str] = mapped_column(String(8))
    platform: Mapped[str] = mapped_column(String(32))
    external_id: Mapped[str | None] = mapped_column(String(256))
    given_items: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    received_items: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    platform_given_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    platform_received_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    real_given_cash_value_eur: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    real_received_cash_value_eur: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    display_currency: Mapped[str] = mapped_column(String(3))
    fees: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    effective_spread: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_quality: Mapped[int] = mapped_column(Integer)
    confidence: Mapped[int] = mapped_column(Integer)


class WatchRule(Base):
    __tablename__ = "watch_rules"
    __table_args__ = (
        CheckConstraint("mode IN ('demo', 'live')"),
        Index("ix_watch_rule_enabled", "mode", "enabled", "created_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    mode: Mapped[str] = mapped_column(String(8))
    name: Mapped[str] = mapped_column(String(256))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    filters: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
