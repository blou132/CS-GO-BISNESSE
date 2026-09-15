"""Transactional stream receipts and reuse of the existing normalized storage."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.markets.base import AdapterObservation, AdapterResult
from app.models import (
    ListingAnalysisSnapshot,
    MarketListing,
    MarketOpportunity,
    RealizedSale,
    RealtimeReceipt,
)
from app.services.analysis import refresh_opportunities
from app.services.storage import (
    _fingerprint,
    prune,
    store_listing,
    store_observation,
    store_realized_sale,
)


@dataclass(frozen=True)
class FeedEvent:
    result: AdapterResult
    received_at: datetime


@dataclass
class BatchStats:
    listings: int = 0
    sales: int = 0
    duplicates: int = 0


def expire_stream_listings(session: Session, settings: Settings) -> int:
    cutoff = datetime.now(UTC) - timedelta(seconds=settings.skinport_realtime_stale_seconds)
    ids = select(MarketListing.id).where(
        MarketListing.mode == "live",
        MarketListing.platform == "skinport",
        MarketListing.status == "ACTIVE",
        MarketListing.observed_at < cutoff,
    )
    # Invalidate dependent snapshots before changing the predicate used by the subquery.
    session.execute(
        update(MarketOpportunity)
        .where(MarketOpportunity.listing_id.in_(ids))
        .values(status="INACTIVE")
    )
    session.execute(
        delete(ListingAnalysisSnapshot).where(ListingAnalysisSnapshot.listing_id.in_(ids))
    )
    changed = session.execute(
        update(MarketListing).where(MarketListing.id.in_(ids)).values(status="INACTIVE")
    )
    return int(getattr(changed, "rowcount", 0))


def persist_feed_batch(
    factory: sessionmaker[Session], batch: list[FeedEvent], settings: Settings
) -> BatchStats:
    stats = BatchStats()
    with factory.begin() as session:
        if session.get_bind().dialect.name == "postgresql":
            session.execute(text("SET LOCAL statement_timeout = '5s'"))
            session.execute(text("SET LOCAL lock_timeout = '3s'"))
        names: set[str] = set()
        for event in batch:
            result = event.result
            listed = result.listings[0] if result.listings else None
            sale = result.realized_sales[0] if result.realized_sales else None
            record = listed or sale
            if record is None or record.external_id is None:
                continue
            event_type = "listed" if listed else "sold"
            name = listed.item.market_hash_name if listed else sale.market_hash_name  # type: ignore[union-attr]
            key = _fingerprint(
                "live", "skinport", event_type, record.external_id, record.price, record.currency
            )
            insert = pg_insert if session.get_bind().dialect.name == "postgresql" else sqlite_insert
            statement = (
                insert(RealtimeReceipt)
                .values(
                    event_key=key,
                    platform="skinport",
                    event_type=event_type,
                    external_id=record.external_id,
                    received_at=event.received_at,
                )
                .on_conflict_do_nothing(index_elements=["event_key"])
                .returning(RealtimeReceipt.event_key)
            )
            if session.scalar(statement) is None:
                stats.duplicates += 1
                continue
            previous = session.scalar(
                select(MarketListing).where(
                    MarketListing.mode == "live",
                    MarketListing.platform == "skinport",
                    MarketListing.external_id == record.external_id,
                )
            )
            if listed:
                sold = session.scalar(
                    select(RealizedSale.id).where(
                        RealizedSale.mode == "live",
                        RealizedSale.platform == "skinport",
                        RealizedSale.external_id == listed.external_id,
                    )
                )
                # Late replay must never resurrect a proven sale or refresh the same ask.
                if sold or (
                    previous is not None
                    and previous.price_original == listed.price
                    and previous.currency_original == listed.currency
                ):
                    stats.duplicates += 1
                    continue
                store_listing(session, listed, "skinport", "live", settings)
                store_observation(
                    session,
                    AdapterObservation(
                        market_hash_name=name,
                        price=listed.price,
                        currency=listed.currency,
                        observation_type="LISTING",
                        timestamp=event.received_at,
                    ),
                    "skinport",
                    "live",
                    settings,
                    listed.external_id,
                )
                stats.listings += 1
            elif sale:
                if store_realized_sale(session, sale, "skinport", "live", settings):
                    stats.sales += 1
                if previous is not None:
                    previous.status = "SOLD"
                    previous.last_seen_at = event.received_at
                    session.execute(
                        delete(ListingAnalysisSnapshot).where(
                            ListingAnalysisSnapshot.listing_id == previous.id
                        )
                    )
            names.add(name)
        session.flush()
        expire_stream_listings(session, settings)
        if batch:
            prune(session, "live", settings)
            session.execute(
                delete(RealtimeReceipt).where(
                    RealtimeReceipt.received_at
                    < datetime.now(UTC) - timedelta(days=settings.history_retention_days)
                )
            )
        if names:
            refresh_opportunities(session, "live", settings, market_hash_names=names)
    return stats
