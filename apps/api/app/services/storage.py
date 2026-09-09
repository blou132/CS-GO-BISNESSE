import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.currencies.service import normalize_price
from app.markets.base import AdapterListing, AdapterObservation, AdapterResult
from app.markets.identity import canonical_identity_key
from app.models import CanonicalItem, CS2Item, ItemSticker, MarketListing, PriceObservation
from app.schemas.api import Mode


@dataclass
class PersistenceStats:
    items_received: int = 0
    listings_created: int = 0
    listings_updated: int = 0
    observations_created: int = 0


def aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def store_listing(
    session: Session,
    data: AdapterListing,
    platform: str,
    mode: Mode,
    settings: Settings,
) -> tuple[MarketListing, bool]:
    identity_key = canonical_identity_key(
        data.item.market_hash_name,
        data.item.paint_index,
        data.item.doppler_phase,
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
            market_hash_name=data.item.market_hash_name,
            paint_index=data.item.paint_index,
            variant=data.item.doppler_phase,
        )
        session.add(canonical_item)
        session.flush()
    item = session.scalar(
        select(CS2Item).where(
            CS2Item.mode == mode,
            CS2Item.platform == platform,
            CS2Item.external_id == data.external_id,
        )
    )
    if item is None:
        item = CS2Item(mode=mode, platform=platform, external_id=data.external_id)
        session.add(item)
    item.canonical_item_id = canonical_item.id
    for name, value in data.item.model_dump(exclude={"stickers"}).items():
        setattr(item, name, value)
    item.stickers = [ItemSticker(**sticker.model_dump()) for sticker in data.item.stickers]
    session.flush()
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
        items_received=len(result.listings) + len(result.observations),
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
