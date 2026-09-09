import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.currencies.service import normalize_price
from app.markets.base import (
    AdapterAggregateStat,
    AdapterBuyOrder,
    AdapterFeeSchedule,
    AdapterItem,
    AdapterListing,
    AdapterObservation,
    AdapterRealizedSale,
    AdapterResult,
)
from app.markets.identity import canonical_identity_key
from app.models import (
    AggregateMarketStat,
    BuyOrderObservation,
    CanonicalItem,
    CS2Item,
    ItemSticker,
    MarketListing,
    PlatformFeeSchedule,
    PriceObservation,
    RealizedSale,
)
from app.schemas.api import Mode


@dataclass
class PersistenceStats:
    items_received: int = 0
    listings_created: int = 0
    listings_updated: int = 0
    observations_created: int = 0
    aggregates_created: int = 0
    realized_sales_created: int = 0
    buy_orders_created: int = 0
    fee_schedules_created: int = 0


def aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _store_item(
    session: Session,
    data: AdapterItem,
    external_id: str,
    platform: str,
    mode: Mode,
) -> CS2Item:
    identity_key = canonical_identity_key(
        data.market_hash_name,
        data.paint_index,
        data.doppler_phase,
    )
    canonical_item = session.scalar(
        select(CanonicalItem).where(
            CanonicalItem.mode == mode,
            CanonicalItem.identity_key == identity_key,
        )
    )
    if canonical_item is None:
        canonical_item = CanonicalItem(
            mode=mode,
            identity_key=identity_key,
            market_hash_name=data.market_hash_name,
            paint_index=data.paint_index,
            variant=data.doppler_phase,
        )
        session.add(canonical_item)
        session.flush()
    item = session.scalar(
        select(CS2Item).where(
            CS2Item.mode == mode,
            CS2Item.platform == platform,
            CS2Item.external_id == external_id,
        )
    )
    if item is None:
        item = CS2Item(mode=mode, platform=platform, external_id=external_id)
        session.add(item)
    item.canonical_item_id = canonical_item.id
    for name, value in data.model_dump(exclude={"stickers"}).items():
        setattr(item, name, value)
    item.stickers = [ItemSticker(**sticker.model_dump()) for sticker in data.stickers]
    session.flush()
    return item


def store_listing(
    session: Session,
    data: AdapterListing,
    platform: str,
    mode: Mode,
    settings: Settings,
) -> tuple[MarketListing, bool]:
    item = _store_item(session, data.item, data.external_id, platform, mode)
    listing = session.scalar(
        select(MarketListing).where(
            MarketListing.mode == mode,
            MarketListing.platform == platform,
            MarketListing.external_id == data.external_id,
        )
    )
    created = listing is None
    if listing is None:
        listing = MarketListing(
            mode=mode,
            platform=platform,
            external_id=data.external_id,
            item_id=item.id,
            first_seen_at=data.observed_at,
        )
        session.add(listing)
    listing.price_original = data.price
    listing.currency_original = data.currency
    listing.observed_at = data.observed_at
    listing.listed_at = data.listed_at
    listing.listing_url = data.listing_url
    listing.seller_type = data.seller_type
    listing.warnings = data.warnings
    listing.last_seen_at = data.observed_at
    listing.status = "ACTIVE"
    (
        listing.price_eur_reference,
        listing.fx_rate,
        listing.fx_rate_timestamp,
        listing.fx_rate_source,
    ) = normalize_price(data.price, data.currency, settings, datetime.now(UTC))
    return listing, created


def _fingerprint(*values: object) -> str:
    serialized = json.dumps(
        values, default=str, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(serialized.encode()).hexdigest()


def _normalized_optional(
    value: Decimal | None,
    currency: str,
    settings: Settings,
    now: datetime,
) -> tuple[Decimal | None, Decimal | None, datetime | None, str | None]:
    if value is None:
        return None, None, None, None
    return normalize_price(value, currency, settings, now)


def store_aggregate(
    session: Session,
    data: AdapterAggregateStat,
    platform: str,
    mode: Mode,
    settings: Settings,
) -> bool:
    fingerprint = _fingerprint(
        mode,
        platform,
        data.market_hash_name,
        data.window,
        data.min_price,
        data.max_price,
        data.avg_price,
        data.median_price,
        data.volume,
        data.currency,
        aware(data.observed_at).isoformat(),
    )
    if session.scalar(
        select(AggregateMarketStat.id).where(AggregateMarketStat.fingerprint == fingerprint)
    ):
        return False
    now = datetime.now(UTC)
    normalized = [
        _normalized_optional(value, data.currency, settings, now)
        for value in (data.min_price, data.max_price, data.avg_price, data.median_price)
    ]
    provenance = next((value for value in normalized if value[1] is not None), (None,) * 4)
    session.add(
        AggregateMarketStat(
            fingerprint=fingerprint,
            mode=mode,
            platform=platform,
            market_hash_name=data.market_hash_name,
            window_code=data.window,
            min_price=data.min_price,
            max_price=data.max_price,
            avg_price=data.avg_price,
            median_price=data.median_price,
            volume=data.volume,
            currency=data.currency,
            min_eur_reference=normalized[0][0],
            max_eur_reference=normalized[1][0],
            avg_eur_reference=normalized[2][0],
            median_eur_reference=normalized[3][0],
            fx_rate=provenance[1],
            fx_rate_timestamp=provenance[2],
            fx_rate_source=provenance[3],
            observed_at=data.observed_at,
        )
    )
    return True


def store_realized_sale(
    session: Session,
    data: AdapterRealizedSale,
    platform: str,
    mode: Mode,
    settings: Settings,
) -> bool:
    fingerprint = (
        _fingerprint(mode, platform, "external", data.external_id)
        if data.external_id is not None
        else _fingerprint(
            mode,
            platform,
            "documented_fields",
            data.market_hash_name,
            data.price,
            data.currency,
            aware(data.sold_at).isoformat(),
            data.transaction_type,
            data.attributes,
        )
    )
    if session.scalar(
        select(RealizedSale.id).where(
            RealizedSale.fingerprint == fingerprint,
        )
    ):
        return False
    item = (
        _store_item(session, data.item, data.external_id, platform, mode)
        if data.item is not None and data.external_id is not None
        else None
    )
    converted, rate, rate_date, source = normalize_price(
        data.price, data.currency, settings, datetime.now(UTC)
    )
    session.add(
        RealizedSale(
            fingerprint=fingerprint,
            mode=mode,
            platform=platform,
            external_id=data.external_id,
            canonical_item_id=item.canonical_item_id if item else None,
            item_id=item.id if item else None,
            market_hash_name=data.market_hash_name,
            price_original=data.price,
            currency_original=data.currency,
            price_eur_reference=converted,
            fx_rate=rate,
            fx_rate_timestamp=rate_date,
            fx_rate_source=source,
            sold_at=data.sold_at,
            observed_at=data.observed_at,
            transaction_type=data.transaction_type,
            attributes=data.attributes,
        )
    )
    return True


def store_buy_order(
    session: Session,
    data: AdapterBuyOrder,
    platform: str,
    mode: Mode,
    settings: Settings,
) -> bool:
    fingerprint = _fingerprint(
        mode,
        platform,
        data.market_hash_name,
        data.price,
        data.currency,
        data.quantity,
        data.attributes,
        aware(data.observed_at).isoformat(),
    )
    if session.scalar(
        select(BuyOrderObservation.id).where(BuyOrderObservation.fingerprint == fingerprint)
    ):
        return False
    converted, rate, rate_date, source = normalize_price(
        data.price, data.currency, settings, datetime.now(UTC)
    )
    session.add(
        BuyOrderObservation(
            fingerprint=fingerprint,
            mode=mode,
            platform=platform,
            market_hash_name=data.market_hash_name,
            price_original=data.price,
            currency_original=data.currency,
            price_eur_reference=converted,
            fx_rate=rate,
            fx_rate_timestamp=rate_date,
            fx_rate_source=source,
            quantity=data.quantity,
            attributes=data.attributes,
            observed_at=data.observed_at,
        )
    )
    return True


def store_fee_schedule(session: Session, data: AdapterFeeSchedule) -> bool:
    existing = session.scalar(
        select(PlatformFeeSchedule).where(
            PlatformFeeSchedule.platform == data.platform,
            PlatformFeeSchedule.fee_type == data.fee_type,
            PlatformFeeSchedule.rate == data.rate,
            PlatformFeeSchedule.fixed_amount == data.fixed_amount,
            PlatformFeeSchedule.minimum_fee == data.minimum_fee,
            PlatformFeeSchedule.currency == data.currency,
            PlatformFeeSchedule.applies_to == data.applies_to,
            PlatformFeeSchedule.source == data.source,
            PlatformFeeSchedule.valid_until.is_(None),
        )
    )
    if existing is not None:
        existing.verified_at = data.verified_at
        existing.details = {key: value for key, value in data.details.items()}
        return False
    session.add(PlatformFeeSchedule(**data.model_dump()))
    return True


def store_observation(
    session: Session,
    data: AdapterObservation,
    platform: str,
    mode: Mode,
    settings: Settings,
    external_id: str = "aggregate",
) -> bool:
    if _is_repeated_listing_observation(session, data, platform, mode, settings):
        return False
    fingerprint = hashlib.sha256(
        "|".join(
            [
                mode,
                platform,
                external_id,
                data.market_hash_name,
                str(data.price.normalize()),
                data.currency,
                data.observation_type,
                aware(data.timestamp).isoformat(),
                str(data.volume),
            ]
        ).encode()
    ).hexdigest()
    if session.scalar(
        select(PriceObservation.id).where(
            PriceObservation.fingerprint == fingerprint,
        )
    ):
        return False
    converted, rate, rate_date, source = normalize_price(
        data.price,
        data.currency,
        settings,
        datetime.now(UTC),
    )
    session.add(
        PriceObservation(
            fingerprint=fingerprint,
            mode=mode,
            platform=platform,
            market_hash_name=data.market_hash_name,
            price=data.price,
            currency=data.currency,
            observation_type=data.observation_type,
            timestamp=data.timestamp,
            volume=data.volume,
            price_eur_reference=converted,
            fx_rate=rate,
            fx_rate_timestamp=rate_date,
            fx_rate_source=source,
        )
    )
    return True


def _is_repeated_listing_observation(
    session: Session,
    data: AdapterObservation,
    platform: str,
    mode: Mode,
    settings: Settings,
) -> bool:
    if data.observation_type != "LISTING":
        return False
    cutoff = aware(data.timestamp) - timedelta(
        seconds=settings.price_observation_min_interval_seconds
    )
    return (
        session.scalar(
            select(PriceObservation.id)
            .where(
                PriceObservation.mode == mode,
                PriceObservation.platform == platform,
                PriceObservation.market_hash_name == data.market_hash_name,
                PriceObservation.observation_type == "LISTING",
                PriceObservation.price == data.price,
                PriceObservation.currency == data.currency,
                PriceObservation.timestamp >= cutoff,
            )
            .order_by(PriceObservation.timestamp.desc())
            .limit(1)
        )
        is not None
    )


def persist_result(
    session: Session,
    result: AdapterResult,
    platform: str,
    mode: Mode,
    settings: Settings,
) -> PersistenceStats:
    stats = PersistenceStats(
        items_received=(
            len(result.listings)
            + len(result.observations)
            + len(result.aggregates)
            + len(result.realized_sales)
            + len(result.buy_orders)
            + len(result.fee_schedules)
        ),
    )
    for data in result.listings[:50]:
        _, created = store_listing(session, data, platform, mode, settings)
        if created:
            stats.listings_created += 1
        else:
            stats.listings_updated += 1
        if store_observation(
            session,
            AdapterObservation(
                market_hash_name=data.item.market_hash_name,
                price=data.price,
                currency=data.currency,
                observation_type="LISTING",
                timestamp=data.observed_at,
                volume=None,
            ),
            platform,
            mode,
            settings,
            data.external_id,
        ):
            stats.observations_created += 1
    for observation in result.observations[:100]:
        if store_observation(session, observation, platform, mode, settings):
            stats.observations_created += 1
    for aggregate in result.aggregates[:200]:
        if store_aggregate(session, aggregate, platform, mode, settings):
            stats.aggregates_created += 1
    for sale in result.realized_sales[:200]:
        if store_realized_sale(session, sale, platform, mode, settings):
            stats.realized_sales_created += 1
    for buy_order in result.buy_orders[:200]:
        if store_buy_order(session, buy_order, platform, mode, settings):
            stats.buy_orders_created += 1
    for fee_schedule in result.fee_schedules[:100]:
        if store_fee_schedule(session, fee_schedule):
            stats.fee_schedules_created += 1
    session.flush()
    prune(session, mode, settings)
    return stats


def prune(session: Session, mode: Mode, settings: Settings) -> None:
    cutoff = datetime.now(UTC) - timedelta(days=settings.history_retention_days)
    session.execute(
        delete(PriceObservation).where(
            PriceObservation.mode == mode,
            PriceObservation.timestamp < cutoff,
        )
    )
    stale_listings = session.scalars(
        select(MarketListing)
        .where(
            MarketListing.mode == mode,
            MarketListing.status == "ACTIVE",
        )
        .order_by(MarketListing.observed_at.desc(), MarketListing.id)
        .offset(settings.max_listings)
    ).all()
    for listing in stale_listings:
        listing.status = "INACTIVE"


def decimal_string(value: Decimal | None) -> str | None:
    return format(value.normalize(), "f") if value is not None else None
