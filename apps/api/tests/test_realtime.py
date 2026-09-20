import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
import socketio
from aiohttp import web
from sqlalchemy import func, select

from app.core.config import Settings
from app.db.session import build_engine, build_session_factory
from app.markets.skinport import normalize_sale_feed
from app.models import Base, ListingAnalysisSnapshot, MarketListing, RealizedSale, RealtimeReceipt
from app.services import realtime, realtime_storage
from app.services.analysis import build_item_detail
from app.services.realtime import SkinportRealtime, SkinportTransport, reconnect_delay
from app.services.realtime_storage import BatchStats, FeedEvent, persist_feed_batch
from app.services.scanner import ScannerQuery, build_scanner_page
from app.services.storage import aware

NAME = "AK-47 | Redline (Field-Tested)"
UNIT_SOURCE = "https://example.test/verified-synthetic-contract"


def payload(event="listed", identifier=101, price=2450, **fields):
    return {
        "eventType": event,
        "sales": [
            {
                "saleId": identifier,
                "marketHashName": NAME,
                "salePrice": price,
                "currency": "EUR",
                "appid": 730,
                "saleStatus": event,
                "wear": 0.2,
                "assetId": "internal-id",
                "assetid": "steam-asset",
                "url": "test-slug",
                **fields,
            }
        ],
    }


def event(kind="listed", identifier=101, price=2450, at=None):
    now = at or datetime.now(UTC)
    return FeedEvent(
        normalize_sale_feed(
            payload(kind, identifier, price), now, price_unit="minor", price_unit_source=UNIT_SOURCE
        ),
        now,
    )


@pytest.fixture
def database(tmp_path):
    settings = Settings(
        _env_file=None,
        environment="test",
        database_url=f"sqlite:///{tmp_path / 'feed.db'}",
        skinport_realtime_enabled=True,
        market_sync_query=NAME,
        skinport_realtime_price_unit="minor",
        skinport_realtime_price_unit_source=UNIT_SOURCE,
    )
    engine = build_engine(settings.database_url)
    Base.metadata.create_all(engine)
    yield build_session_factory(engine), settings
    engine.dispose()


def test_feed_defaults_fail_closed_and_supported_contract_is_explicit():
    now = datetime.now(UTC)
    with pytest.raises(ValueError):
        normalize_sale_feed(payload(), now)
    result = event().result.listings[0]
    assert result.price == Decimal("24.50")
    assert result.item.asset_id == "steam-asset"
    assert result.listing_url is None
    assert result.item.source_attributes["timestamp_basis"] == "feed_observed_at"
    assert result.item.tradable is None


@pytest.mark.parametrize("price", ["invalid", "1e999999999", "1000000000000", "NaN"])
def test_invalid_major_price_is_rejected_without_crashing_receiver(price):
    result = normalize_sale_feed(
        payload(price=price),
        datetime.now(UTC),
        price_unit="major",
        price_unit_source=UNIT_SOURCE,
    )
    assert result.listings == []
    assert len(result.warnings) == 1


@pytest.mark.parametrize(
    "fields",
    [
        {"saleId": None},
        {"saleId": True},
        {"currency": "USD"},
        {"appid": 440},
        {"salePrice": -1},
        {"salePrice": 24.5},
        {"salePrice": True},
        {"saleStatus": "sold"},
    ],
)
def test_feed_invalid_rows_never_become_listings(fields):
    result = normalize_sale_feed(
        payload(**fields), datetime.now(UTC), price_unit="minor", price_unit_source=UNIT_SOURCE
    )
    assert not result.listings and not result.realized_sales


@pytest.mark.parametrize("kind", ["updated", "price_changed", "canceled"])
def test_undocumented_event_is_rejected(kind):
    with pytest.raises(ValueError):
        normalize_sale_feed(
            payload(kind), datetime.now(UTC), price_unit="minor", price_unit_source=UNIT_SOURCE
        )


def test_replay_does_not_refresh_ask_and_sale_cannot_be_resurrected(database):
    factory, settings = database
    first = event()
    assert persist_feed_batch(factory, [first, first], settings) == BatchStats(1, 0, 1)
    with factory() as session:
        listing = session.scalar(select(MarketListing))
        assert listing.price_original == Decimal("24.50")
        original_time = aware(listing.observed_at)
        detail = build_item_detail(session, listing.id, "live", settings)
        assert detail.provenance.buy.external_id == "101"
        assert detail.provenance.reference[0].record_id == listing.id
        assert detail.provenance.fee_status == "UNKNOWN"
        assert detail.provenance.eligibility == "REFERENCE_ONLY"
        assert detail.item.potential_profit_eur is None
    assert persist_feed_batch(factory, [event()], settings).duplicates == 1
    with factory() as session:
        assert aware(session.scalar(select(MarketListing)).observed_at) == original_time
    assert persist_feed_batch(factory, [event(price=2200)], settings).listings == 1
    assert persist_feed_batch(factory, [event("sold"), event("sold")], settings) == BatchStats(
        0, 1, 1
    )
    assert persist_feed_batch(factory, [event(price=2100)], settings).duplicates == 1
    with factory() as session:
        assert session.scalar(select(MarketListing)).status == "SOLD"
        assert session.scalar(select(func.count()).select_from(RealizedSale)) == 1
        assert session.scalar(select(func.count()).select_from(ListingAnalysisSnapshot)) == 0
        sale = session.scalar(select(RealizedSale))
        assert sale.attributes["timestamp_basis"] == "feed_observed_at"


def test_stale_listing_is_inactive_not_sold_and_late_replay_stays_stale(database):
    factory, settings = database
    first = event(at=datetime.now(UTC) - timedelta(minutes=10))
    persist_feed_batch(factory, [first], settings)
    persist_feed_batch(factory, [event()], settings)
    with factory() as session:
        assert session.scalar(select(MarketListing)).status == "INACTIVE"
        assert session.scalar(select(func.count()).select_from(RealizedSale)) == 0


def test_stale_scanner_is_safe_even_when_collector_is_stopped(database):
    factory, settings = database
    persist_feed_batch(factory, [event()], settings)
    with factory.begin() as session:
        session.scalar(select(MarketListing)).observed_at = datetime.now(UTC) - timedelta(
            minutes=10
        )
    with factory() as session:
        assert session.scalar(select(MarketListing)).status == "ACTIVE"
        assert build_scanner_page(session, ScannerQuery(), settings).total == 0


def test_new_price_replaces_reference_snapshot(database):
    factory, settings = database
    persist_feed_batch(factory, [event()], settings)
    persist_feed_batch(factory, [event(price=1200)], settings)
    with factory() as session:
        snapshot = session.scalar(select(ListingAnalysisSnapshot))
        assert snapshot.estimated_value_eur == Decimal("12")
        assert snapshot.potential_profit_eur is None


def test_batch_rollback_includes_receipt_and_retry_can_succeed(database, monkeypatch):
    factory, settings = database
    original = realtime_storage.store_listing
    monkeypatch.setattr(realtime_storage, "store_listing", lambda *args: 1 / 0)
    with pytest.raises(ZeroDivisionError):
        persist_feed_batch(factory, [event()], settings)
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(RealtimeReceipt)) == 0
    monkeypatch.setattr(realtime_storage, "store_listing", original)
    assert persist_feed_batch(factory, [event()], settings).listings == 1


@pytest.mark.asyncio
async def test_bounded_queue_filter_unknown_events_and_disabled_lifecycle(database):
    factory, settings = database
    settings.skinport_realtime_queue_size = 1
    stream = SkinportRealtime(factory, settings)
    await stream.accept(payload())
    await stream.accept(payload(identifier=102))
    await stream.accept(payload(marketHashName="Unrelated item"))
    await stream.accept({"eventType": "updated", "sales": []})
    state = stream.snapshot()
    assert state.queue_depth == 1 and state.dropped_events == 1
    assert state.filtered_events == 1 and state.invalid_events == 1
    assert state.events_per_minute == 3
    await stream.accept({"eventType": [], "sales": []})
    assert stream.snapshot().invalid_events == 2
    settings.skinport_realtime_enabled = False
    disabled = SkinportRealtime(factory, settings)
    await disabled.start()
    assert disabled._receiver is None
    await disabled.stop()
    assert disabled.snapshot().status == "disabled"


@pytest.mark.asyncio
async def test_shutdown_drains_queue_and_retries_one_database_failure(database, monkeypatch):
    factory, settings = database
    stream = SkinportRealtime(factory, settings)
    calls = []
    original = realtime.persist_feed_batch

    def flaky(*args):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("Do not log SQL or credentials")
        return original(*args)

    monkeypatch.setattr(realtime, "persist_feed_batch", flaky)
    await stream.accept(payload())
    stream._consumer = asyncio.create_task(stream._consume())
    await stream.stop()
    assert len(calls) == 2
    assert stream.snapshot().queue_depth == 0
    assert stream.snapshot().listings_updated == 1
    assert stream.snapshot().errors == 1
    assert stream.snapshot().last_error is None


@pytest.mark.asyncio
async def test_upstream_refusal_cools_down_and_close_errors_do_not_kill_loop(database):
    factory, settings = database

    class Refused:
        http_status = 403

        async def connect(self, handler):
            raise ConnectionError("private upstream body")

        async def close(self):
            raise OSError("private error")

    stream = SkinportRealtime(factory, settings, transport_factory=Refused)
    await stream.start()
    async with asyncio.timeout(2):
        while stream.snapshot().reconnect_count == 0:
            await asyncio.sleep(0.01)
    state = stream.snapshot()
    assert state.status == "blocked" and not state.connected
    assert (state.next_retry_at - datetime.now(UTC)).total_seconds() > 295
    assert "private" not in state.model_dump_json()
    await stream.stop()


def test_backoff_is_exponential_capped_and_idle_stream_is_degraded(database):
    assert [reconnect_delay(n, 0) for n in (1, 2, 3, 100)] == [5, 10, 20, 300]
    assert reconnect_delay(1, 1) == 6
    factory, settings = database
    stream = SkinportRealtime(factory, settings)
    stream.state.connected = True
    stream.state.connected_since = datetime.now(UTC) - timedelta(minutes=10)
    assert stream.snapshot().status == "degraded"
    assert stream.snapshot().last_error == "stream_stale"


@pytest.mark.asyncio
async def test_real_messagepack_socketio_transport_against_local_server():
    server = socketio.AsyncServer(
        async_mode="aiohttp", serializer="msgpack", ping_interval=0.1, ping_timeout=1
    )
    app = web.Application()
    server.attach(app)
    joined, received = [], []

    @server.on("saleFeedJoin")
    async def join(sid, data):
        joined.append(data)
        await server.emit("saleFeed", payload(), to=sid)

    async def accept(data):
        received.append(data)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    original_connect = socketio.AsyncClient.connect

    async def local_connect(client, url, **kwargs):
        assert url == "https://skinport.com"
        return await original_connect(client, f"http://127.0.0.1:{port}", **kwargs)

    transport = SkinportTransport()
    try:
        with patch.object(socketio.AsyncClient, "connect", local_connect):
            await transport.connect(accept)
        async with asyncio.timeout(3):
            while not received:
                await asyncio.sleep(0.01)
        await asyncio.sleep(0.3)
        assert transport._client.connected
        assert joined == [{"currency": "EUR", "locale": "en", "appid": 730}]
        assert received == [payload()]
    finally:
        await transport.close()
        await server.shutdown()
        await runner.cleanup()
    assert transport._http.closed
