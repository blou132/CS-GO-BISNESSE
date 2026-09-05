import hashlib
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.currencies.service import normalize_price
from app.markets.base import AdapterListing, AdapterObservation, AdapterResult
from app.models import CS2Item, ItemSticker, MarketListing, PriceObservation
from app.schemas.api import Mode


def aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def store_listing(
    session: Session,
    data: AdapterListing,
    platform: str,
    mode: Mode,
    settings: Settings,
) -> MarketListing:
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
    if listing is None:
        listing = MarketListing(
            mode=mode,
            platform=platform,
            external_id=data.external_id,
            item_id=item.id,
        )
        session.add(listing)
    listing.price_original = data.price
    listing.currency_original = data.currency
    listing.observed_at = data.observed_at
    listing.listed_at = data.listed_at
    listing.listing_url = data.listing_url
    listing.warnings = data.warnings
    (
        listing.price_eur_reference,
        listing.fx_rate,
        listing.fx_rate_timestamp,
        listing.fx_rate_source,
    ) = normalize_price(data.price, data.currency, settings, datetime.now(UTC))
    return listing


def store_observation(
    session: Session,
    data: AdapterObservation,
    platform: str,
    mode: Mode,
    settings: Settings,
    external_id: str = "aggregate",
) -> None:
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
        return
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


def persist_result(
    session: Session,
    result: AdapterResult,
    platform: str,
    mode: Mode,
    settings: Settings,
) -> None:
    for data in result.listings[:50]:
        store_listing(session, data, platform, mode, settings)
        store_observation(
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
        )
    for observation in result.observations[:100]:
        store_observation(session, observation, platform, mode, settings)
    session.flush()
    prune(session, mode, settings)


def prune(session: Session, mode: Mode, settings: Settings) -> None:
    cutoff = datetime.now(UTC) - timedelta(days=settings.history_retention_days)
    session.execute(
        delete(PriceObservation).where(
            PriceObservation.mode == mode,
            PriceObservation.timestamp < cutoff,
        )
    )
    stale = session.scalars(
        select(MarketListing)
        .where(
            MarketListing.mode == mode,
        )
        .order_by(MarketListing.observed_at.desc(), MarketListing.id)
        .offset(settings.max_listings)
    ).all()
    for listing in stale:
        item = listing.item
        session.delete(listing)
        session.flush()
        session.delete(item)


def decimal_string(value: Decimal | None) -> str | None:
    return format(value.normalize(), "f") if value is not None else None
