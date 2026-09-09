from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.core.config import Settings
from app.db.session import build_engine, build_session_factory
from app.markets.base import (
    AdapterAggregateStat,
    AdapterBuyOrder,
    AdapterFeeSchedule,
    AdapterItem,
    AdapterListing,
    AdapterRealizedSale,
    AdapterResult,
)
from app.models import (
    AggregateMarketStat,
    Base,
    BuyOrderObservation,
    CanonicalItem,
    CS2Item,
    MarketListing,
    PlatformFeeSchedule,
    PriceObservation,
    RealizedSale,
)
from app.services.storage import aware, persist_result


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
        canonical_items = list(session.scalars(select(CanonicalItem)))
        canonical_item_ids = list(session.scalars(select(CS2Item.canonical_item_id)))

    assert first.listings_created == 1
    assert second.listings_updated == 1
    assert second.observations_created == 0
    assert third.listings_updated == 1
    assert third.observations_created == 1
    assert len(listings) == 2
    assert listings[0].status == "INACTIVE"
    assert listings[0].price_original == Decimal("12.00000000")
    assert aware(listings[0].first_seen_at) == now
    assert listings[1].status == "ACTIVE"
    assert len(canonical_items) == 1
    assert canonical_item_ids == [canonical_items[0].id, canonical_items[0].id]
    assert len(observations) == 3
    engine.dispose()


def test_market_facts_are_persisted_separately_and_deduplicated(tmp_path) -> None:
    now = datetime.now(UTC)
    settings = Settings(_env_file=None, database_url=f"sqlite:///{tmp_path / 'facts.db'}")
    engine = build_engine(settings.database_url)
    Base.metadata.create_all(engine)
    factory = build_session_factory(engine)
    result = AdapterResult(
        aggregates=[
            AdapterAggregateStat(
                market_hash_name="AK-47 | Redline (Field-Tested)",
                window="7D",
                median_price=Decimal("21.50"),
                volume=42,
                currency="EUR",
                observed_at=now,
            )
        ],
        realized_sales=[
            AdapterRealizedSale(
                market_hash_name="AK-47 | Redline (Field-Tested)",
                price=Decimal("20"),
                currency="EUR",
                sold_at=now - timedelta(minutes=2),
                observed_at=now,
                transaction_type="Target",
                attributes={"identity_basis": "documented_fields"},
            )
        ],
        buy_orders=[
            AdapterBuyOrder(
                market_hash_name="AK-47 | Redline (Field-Tested)",
                price=Decimal("19"),
                currency="EUR",
                quantity=3,
                observed_at=now,
                attributes={"floatPartValue": "any"},
            )
        ],
        fee_schedules=[
            AdapterFeeSchedule(
                platform="dmarket",
                fee_type="SELL",
                rate=Decimal("0.02"),
                minimum_fee=Decimal("0.02"),
                currency="EUR",
                source="https://example.test/official-test-fixture",
                verified_at=now,
                valid_from=now,
            )
        ],
    )

    with factory() as session:
        first = persist_result(session, result, "dmarket", "live", settings)
        second = persist_result(session, result, "dmarket", "live", settings)
        session.commit()
        aggregate = session.scalar(select(AggregateMarketStat))
        sale = session.scalar(select(RealizedSale))
        order = session.scalar(select(BuyOrderObservation))
        fee = session.scalar(select(PlatformFeeSchedule))

    assert first.aggregates_created == 1
    assert first.realized_sales_created == 1
    assert first.buy_orders_created == 1
    assert first.fee_schedules_created == 1
    assert second.aggregates_created == 0
    assert second.realized_sales_created == 0
    assert second.buy_orders_created == 0
    assert second.fee_schedules_created == 0
    assert aggregate is not None and aggregate.median_eur_reference == Decimal("21.50000000")
    assert sale is not None and sale.external_id is None
    assert order is not None and order.quantity == 3
    assert fee is not None and fee.minimum_fee == Decimal("0.02000000")
    engine.dispose()
