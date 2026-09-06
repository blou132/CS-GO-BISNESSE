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
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    mode: Mapped[str] = mapped_column(String(8), index=True)
    platform: Mapped[str] = mapped_column(String(32))
    external_id: Mapped[str] = mapped_column(String(256))
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
    inspect_link: Mapped[str | None] = mapped_column(String(2048))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
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
    estimated_applied_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))


class MarketListing(Base):
    __tablename__ = "market_listings"
    __table_args__ = (
        UniqueConstraint("mode", "platform", "external_id", name="uq_listing_source"),
        CheckConstraint("price_original >= 0"),
        CheckConstraint("mode IN ('demo', 'live')"),
        CheckConstraint("status IN ('ACTIVE','INACTIVE','SOLD','UNKNOWN')"),
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
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", index=True)
    warnings: Mapped[list[str]] = mapped_column(JSON, default=list)
    item: Mapped[CS2Item] = relationship()


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
