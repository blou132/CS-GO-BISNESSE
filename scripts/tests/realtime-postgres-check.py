"""Synthetic receipt/upsert validation; only run in the disposable V0.11 stack."""

import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select, text

from app.core.config import Settings
from app.db.session import build_engine, build_session_factory
from app.markets.skinport import normalize_sale_feed
from app.models import MarketListing, RealizedSale, RealtimeReceipt
from app.services.analysis import build_item_detail
from app.services.realtime_storage import FeedEvent, persist_feed_batch
from app.services.scanner import ScannerQuery, build_scanner_page

assert os.environ.get("CS2_ISOLATED_VALIDATION") in {"cs2-v011-validation", "cs2-v012-validation"}
settings = Settings(_env_file=None, environment="test", skinport_realtime_price_unit="minor",
                    skinport_realtime_price_unit_source="https://example.test/synthetic-contract")
engine = build_engine(settings.database_url)
assert engine.dialect.name == "postgresql"
factory = build_session_factory(engine)
name = "TEST V011 | Synthetic (Field-Tested)"


def event(kind, identifier, price=2450):
    now = datetime.now(UTC)
    value = {"eventType": kind, "sales": [{"saleId": identifier, "marketHashName": name,
              "salePrice": price, "appid": 730, "currency": "EUR", "wear": 0.2}]}
    result = normalize_sale_feed(value, now, price_unit="minor",
                                price_unit_source=settings.skinport_realtime_price_unit_source)
    for row in result.listings:
        row.item.source_attributes["validation_class"] = "TEST"
    for row in result.realized_sales:
        row.attributes["validation_class"] = "TEST"
    return FeedEvent(result, now)


try:
    listed = event("listed", 90000001)
    first = persist_feed_batch(factory, [listed, listed], settings)
    assert first.listings == 1 and first.duplicates == 1
    assert persist_feed_batch(factory, [event("listed", 90000001, 2100)], settings).listings == 1
    with factory() as session:
        listing = session.scalar(select(MarketListing).where(MarketListing.external_id == "90000001"))
        detail = build_item_detail(session, listing.id, "live", settings)
        assert detail.provenance.buy.value_eur == Decimal("21")
        assert detail.provenance.reference[0].record_id == listing.id
        assert detail.item.potential_profit_eur is None
    sold = persist_feed_batch(factory, [event("sold", 90000001), event("sold", 90000001)], settings)
    assert sold.sales == 1 and sold.duplicates == 1
    assert persist_feed_batch(factory, [event("listed", 90000001, 2000)], settings).duplicates == 1
    persist_feed_batch(factory, [event("listed", 90000002)], settings)
    with factory.begin() as session:
        listing = session.scalar(select(MarketListing).where(MarketListing.external_id == "90000002"))
        listing.observed_at = datetime.now(UTC) - timedelta(minutes=10)
    with factory() as session:
        page = build_scanner_page(session, ScannerQuery(market_hash_name=name), settings)
        assert page.total == 0
    persist_feed_batch(factory, [], settings)
    with factory() as session:
        statuses = dict(session.execute(select(MarketListing.external_id, MarketListing.status).where(
            MarketListing.external_id.in_(["90000001", "90000002"]))).all())
        assert statuses == {"90000001": "SOLD", "90000002": "INACTIVE"}
        assert session.scalar(select(func.count()).select_from(RealizedSale)) == 1
        assert session.scalar(select(func.count()).select_from(RealtimeReceipt)) == 5
        size = session.scalar(text("SELECT pg_database_size(current_database())"))
        print({"postgres_receipts": "PASS", "changed_price": "PASS", "sold_replay": "PASS",
               "stale_scanner": "PASS", "provenance": "PASS", "fixture_only": True,
               "database_bytes": size})
        from app.models import Base
        print({"validation_class": "TEST", "row_counts": {
            table.name: session.scalar(select(func.count()).select_from(table))
            for table in Base.metadata.sorted_tables
        }})
        print({"table_sizes": [dict(row) for row in session.execute(text(
            "SELECT relname, pg_total_relation_size(relid) AS bytes, "
            "pg_indexes_size(relid) AS index_bytes FROM pg_catalog.pg_statio_user_tables "
            "WHERE schemaname='public' ORDER BY relname"
        )).mappings()]})
finally:
    engine.dispose()
