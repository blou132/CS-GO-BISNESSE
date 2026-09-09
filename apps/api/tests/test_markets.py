from datetime import UTC, datetime
from decimal import Decimal

import httpx
import pytest
from nacl.signing import SigningKey, VerifyKey

from app.markets import CSFloatAdapter, CSFloatSearch, DMarketAdapter, SkinportAdapter
from app.markets.base import ConfigurationError, MarketAdapterError, UnsupportedCapabilityError
from app.markets.http import ReadOnlyHTTP
from app.markets.skinport import normalize_sale_feed


@pytest.mark.asyncio
async def test_csfloat_normalizes_only_active_buy_now_listing() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["market_hash_name"] == "AK-47 | Redline (Field-Tested)"
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "123",
                        "type": "buy_now",
                        "state": "listed",
                        "price": 2534,
                        "created_at": "2026-09-05T10:00:00Z",
                        "item": {
                            "asset_id": "asset-123",
                            "def_index": 7,
                            "market_hash_name": "AK-47 | Redline (Field-Tested)",
                            "float_value": 0.18,
                            "paint_seed": 42,
                            "paint_index": 282,
                            "rarity": 4,
                            "quality": 4,
                            "collection": "The Phoenix Collection",
                            "tradable": 0,
                            "scm": {"price": 3000, "volume": 5},
                            "stickers": [
                                {
                                    "name": "Synthetic Sticker",
                                    "slot": 0,
                                    "wear": 0.1,
                                    "scm": {"price": 100, "volume": 2},
                                }
                            ],
                        },
                    }
                ]
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = CSFloatAdapter("synthetic-test-key", client=client)
    result = await adapter.search_items("AK-47 | Redline (Field-Tested)")
    assert result.listings[0].price == Decimal("25.34")
    assert result.listings[0].currency == "USD"
    assert result.listings[0].item.exterior == "Field-Tested"
    assert result.listings[0].item.asset_id == "asset-123"
    assert result.listings[0].item.scm_price == Decimal("30")
    assert result.listings[0].item.tradable is True
    assert result.listings[0].item.stickers[0].steam_volume == 2
    assert result.listings[0].item.stickers[0].estimated_applied_value is None
    await client.aclose()


@pytest.mark.asyncio
async def test_csfloat_missing_key_is_an_explicit_configuration_error() -> None:
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: pytest.fail("Aucune requête ne doit partir sans configuration")
        )
    )
    adapter = CSFloatAdapter(client=client)
    with pytest.raises(ConfigurationError):
        await adapter.search_items("AK-47")
    await client.aclose()


@pytest.mark.asyncio
async def test_skinport_keeps_aggregate_separate_from_listings() -> None:
    now = int(datetime.now(UTC).timestamp())

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/items"):
            return httpx.Response(
                200,
                json=[
                    {
                        "market_hash_name": "AWP | Asiimov (Field-Tested)",
                        "currency": "EUR",
                        "min_price": 120.5,
                        "quantity": 12,
                        "updated_at": now,
                    }
                ],
            )
        assert request.url.params["market_hash_name"] == "AWP | Asiimov (Field-Tested)"
        return httpx.Response(
            200,
            json=[
                {
                    "market_hash_name": "AWP | Asiimov (Field-Tested)",
                    "currency": "EUR",
                    "last_24_hours": {
                        "min": 117,
                        "max": 130,
                        "avg": 122,
                        "median": 121,
                        "volume": 8,
                    },
                    "last_7_days": {"median": 120, "volume": 40},
                    "last_30_days": {"median": 119, "volume": 155},
                    "last_90_days": {"median": 115, "volume": 430},
                }
            ],
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = SkinportAdapter(client=client, min_interval=0)
    result = await adapter.search_items("asiimov")
    assert result.listings == []
    assert result.observations[0].observation_type == "AGGREGATE"
    assert result.observations[0].volume is None
    assert [row.window for row in result.aggregates] == ["24H", "7D", "30D", "90D"]
    assert result.aggregates[0].median_price == Decimal("121")
    assert result.aggregates[0].volume == 8
    with pytest.raises(UnsupportedCapabilityError):
        await adapter.get_listing("anything")
    await client.aclose()


def test_skinport_sale_feed_keeps_listings_and_realized_sales_distinct() -> None:
    observed_at = datetime.now(UTC)
    common = {
        "currency": "EUR",
        "sales": [
            {
                "saleId": 123,
                "assetId": "asset-1",
                "marketHashName": "AK-47 | Redline (Field-Tested)",
                "salePrice": 24.5,
                "wear": 0.22,
                "pattern": 412,
                "finish": 282,
                "stattrak": False,
                "souvenir": False,
                "saleType": "public",
                "stickers": [],
            }
        ],
    }
    listed = normalize_sale_feed({"eventType": "listed", **common}, observed_at)
    sold = normalize_sale_feed({"eventType": "sold", **common}, observed_at)

    assert listed.realized_sales == []
    assert listed.listings[0].external_id == "123"
    assert sold.listings == []
    assert sold.realized_sales[0].external_id == "123"
    assert sold.realized_sales[0].attributes["timestamp_basis"] == "feed_observed_at"


def test_csfloat_search_strategies_are_bounded_and_filterable() -> None:
    filters = CSFloatSearch(
        strategy="OPPORTUNITY_SCAN",
        min_price_cents=1000,
        max_price_cents=5000,
        min_float=0.01,
        max_float=0.2,
        paint_seed=42,
        paint_index=282,
        collection="set_huntsman",
        stickers="1060|3",
    )
    params = filters.parameters()
    assert params["sort_by"] == "best_deal"
    assert params["limit"] == 50
    assert params["paint_seed"] == 42
    assert CSFloatSearch(strategy="DISCOVERY", limit=50).parameters()["limit"] == 20


@pytest.mark.asyncio
async def test_dmarket_requires_valid_matching_ed25519_keys() -> None:
    key = SigningKey.generate()
    wrong = SigningKey.generate()
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"items": []}))
    )
    adapter = DMarketAdapter(bytes(wrong.verify_key).hex(), bytes(key).hex(), client=client)
    with pytest.raises(ConfigurationError):
        await adapter.search_items("AK-47")
    await client.aclose()


@pytest.mark.asyncio
async def test_dmarket_signs_and_normalizes_official_v2_shape() -> None:
    key = SigningKey.generate()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["X-Api-Key"] == bytes(key.verify_key).hex()
        assert request.headers["X-Request-Sign"].startswith("dmar ed25519 ")
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "offerId": "f7c1b8e2-9a3d-4e6f-bb12-3a5c9d0e1f23",
                        "priceCents": "1599",
                        "createdAt": "2026-06-17T10:30:00Z",
                        "locked": False,
                        "attributes": {
                            "gameId": "a8db",
                            "title": "AK-47 | Redline (Field-Tested)",
                            "tradeLockDays": 0,
                            "cs2": {
                                "category": "CATEGORY_NORMAL",
                                "float": "0.2356",
                                "paintIndex": 282,
                                "paintSeed": 412,
                                "inspectInGameUri": "steam://run/730/example",
                                "stickers": [],
                            },
                        },
                    }
                ]
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = DMarketAdapter(bytes(key.verify_key).hex(), bytes(key).hex(), client=client)
    result = await adapter.search_items("AK-47")
    assert result.listings[0].price == Decimal("15.99")
    assert result.listings[0].item.paint_seed == 412
    await client.aclose()


def _verify_dmarket_signature(request: httpx.Request, verify_key: VerifyKey, path: str) -> None:
    timestamp = request.headers["X-Sign-Date"]
    signature = bytes.fromhex(request.headers["X-Request-Sign"].removeprefix("dmar ed25519 "))
    verify_key.verify(("GET" + path + timestamp).encode(), signature)


@pytest.mark.asyncio
async def test_dmarket_buy_orders_sign_decoded_path_and_normalize_demand() -> None:
    key = SigningKey.generate()
    title = "AK-47 | Redline (Field-Tested)"

    def handler(request: httpx.Request) -> httpx.Response:
        assert "%7C" in request.url.raw_path.decode()
        _verify_dmarket_signature(
            request,
            key.verify_key,
            f"/marketplace-api/v1/targets-by-title/a8db/{title}",
        )
        return httpx.Response(
            200,
            json={
                "orders": [
                    {
                        "amount": "2",
                        "price": "155000",
                        "title": title,
                        "attributes": {
                            "floatPartValue": "FT-2",
                            "paintSeed": "any",
                            "phase": "any",
                        },
                    }
                ]
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = DMarketAdapter(bytes(key.verify_key).hex(), bytes(key).hex(), client=client)
    orders = await adapter.get_buy_orders(title)
    assert orders[0].price == Decimal("1550")
    assert orders[0].quantity == 2
    assert orders[0].attributes["floatPartValue"] == "FT-2"
    await client.aclose()


@pytest.mark.asyncio
async def test_dmarket_last_sales_are_realized_without_invented_external_ids() -> None:
    key = SigningKey.generate()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "sales": [
                    {
                        "price": "15.99",
                        "date": "1784133449",
                        "txOperationType": "Target",
                        "offerAttributes": {
                            "floatValue": 0.2905,
                            "paintSeed": 89,
                            "phaseTitle": None,
                            "stickers": [{"name": "Synthetic Sticker"}],
                        },
                        "orderAttributes": {"isAdvanced": True},
                    }
                ]
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = DMarketAdapter(bytes(key.verify_key).hex(), bytes(key).hex(), client=client)
    sales = await adapter.get_last_sales("AK-47 | Redline (Field-Tested)")
    assert sales[0].external_id is None
    assert sales[0].price == Decimal("15.99")
    assert sales[0].transaction_type == "Target"
    assert sales[0].item is not None
    assert sales[0].item.paint_seed == 89
    await client.aclose()


@pytest.mark.asyncio
async def test_dmarket_customized_fees_preserve_default_and_reduced_terms() -> None:
    key = SigningKey.generate()
    expires_at = int(datetime(2026, 10, 1, tzinfo=UTC).timestamp())

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "defaultFee": {"fraction": "0.02", "minAmount": 2},
                "reducedFees": [
                    {
                        "title": "AK-47 | Redline (Field-Tested)",
                        "fraction": "0.015",
                        "minPrice": 100,
                        "maxPrice": 50000,
                        "expiresAt": expires_at,
                    }
                ],
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = DMarketAdapter(bytes(key.verify_key).hex(), bytes(key).hex(), client=client)
    fees = await adapter.get_fee_schedules()
    assert fees[0].rate == Decimal("0.02")
    assert fees[0].minimum_fee == Decimal("0.02")
    assert fees[1].rate == Decimal("0.015")
    assert fees[1].min_amount == Decimal("1")
    assert fees[1].valid_until == datetime(2026, 10, 1, tzinfo=UTC)
    await client.aclose()


@pytest.mark.asyncio
async def test_transport_handles_invalid_json_timeout_and_rate_limit() -> None:
    invalid_client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, content=b"{"))
    )
    invalid = ReadOnlyHTTP("test", "https://example.test", client=invalid_client, min_interval=0)
    with pytest.raises(MarketAdapterError, match="Invalid marketplace JSON"):
        await invalid.get("/items")
    await invalid_client.aclose()

    def timeout(_: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("synthetic timeout")

    timeout_client = httpx.AsyncClient(transport=httpx.MockTransport(timeout))
    transport = ReadOnlyHTTP(
        "test", "https://example.test", client=timeout_client, min_interval=0, max_attempts=1
    )
    with pytest.raises(MarketAdapterError) as timeout_error:
        await transport.get("/items")
    assert timeout_error.value.code == "timeout"
    await timeout_client.aclose()

    rate_client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(429, headers={"Retry-After": "10"})
        )
    )
    rate = ReadOnlyHTTP(
        "test", "https://example.test", client=rate_client, min_interval=0, max_retry_delay=0.01
    )
    with pytest.raises(MarketAdapterError) as rate_error:
        await rate.get("/items")
    assert rate_error.value.code == "rate_limited"
    assert rate_error.value.retry_after_seconds == 10
    await rate_client.aclose()


@pytest.mark.asyncio
async def test_transport_does_not_retry_after_429() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(429, headers={"Retry-After": "1"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    transport = ReadOnlyHTTP(
        "test",
        "https://example.test",
        client=client,
        min_interval=0,
        max_retry_delay=5,
        max_attempts=3,
    )

    with pytest.raises(MarketAdapterError) as rate_error:
        await transport.get("/items")

    assert rate_error.value.code == "rate_limited"
    assert attempts == 1
    await client.aclose()
