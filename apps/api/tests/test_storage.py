from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.core.config import Settings
from app.db.session import build_engine, build_session_factory
from app.markets.base import AdapterItem, AdapterListing, AdapterResult
from app.models import Base, MarketListing, PriceObservation
from app.services.storage import persist_result


def _listing(external_id: str, price: str, observed_at: datetime) -> AdapterListing:
    return AdapterListing(
        external_id=external_id,
        item=AdapterItem(
            market_hash_name="AK-47 | Redline (Field-Tested)",
            weapon="AK-47",
            skin="Redline",
            exterior="Field-Tested",
        ),
        price=Decimal(price),
        currency="EUR",
        observed_at=observed_at,
    )


def test_listing_upsert_tracks_counts_price_changes_and_non_destructive_prune(tmp_path) -> None:
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'storage.db'}",
        environment="test",
        max_listings=1,
        price_observation_min_interval_seconds=3600,
    )
    engine = build_engine(settings.database_url)
    Base.metadata.create_all(engine)
    factory = build_session_factory(engine)
    now = datetime.now(UTC)
    with factory() as session:
        first = persist_result(
            session,
            AdapterResult(listings=[_listing("listing-1", "10", now)]),
            "csfloat",
            "live",
            settings,
        )
        second = persist_result(
            session,
            AdapterResult(listings=[_listing("listing-1", "10", now + timedelta(minutes=10))]),
            "csfloat",
            "live",
            settings,
        )
        third = persist_result(
            session,
            AdapterResult(listings=[_listing("listing-1", "12", now + timedelta(minutes=20))]),
            "csfloat",
            "live",
            settings,
        )
        persist_result(
            session,
            AdapterResult(listings=[_listing("listing-2", "9", now + timedelta(minutes=30))]),
            "csfloat",
            "live",
            settings,
        )
        session.commit()

        listings = list(session.scalars(select(MarketListing).order_by(MarketListing.external_id)))
        observations = list(session.scalars(select(PriceObservation)))

    assert first.listings_created == 1
    assert second.listings_updated == 1
    assert second.observations_created == 0
    assert third.listings_updated == 1
    assert third.observations_created == 1
    assert len(listings) == 2
    assert listings[0].status == "INACTIVE"
    assert listings[0].price_original == Decimal("12.00000000")
    assert listings[1].status == "ACTIVE"
    assert len(observations) == 3
    engine.dispose()
