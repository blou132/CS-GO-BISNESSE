from datetime import UTC, datetime
from decimal import Decimal

import httpx
import pytest
from nacl.signing import SigningKey

from app.markets import CSFloatAdapter, DMarketAdapter, SkinportAdapter
from app.markets.base import ConfigurationError, MarketAdapterError, UnsupportedCapabilityError
from app.markets.http import ReadOnlyHTTP


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
                            "market_hash_name": "AK-47 | Redline (Field-Tested)",
                            "float_value": 0.18,
                            "paint_seed": 42,
                            "paint_index": 282,
                            "stickers": [{"name": "Synthetic Sticker", "slot": 0, "wear": 0.1}],
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
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
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
        )
    )
    adapter = SkinportAdapter(client=client)
    result = await adapter.search_items("asiimov")
    assert result.listings == []
    assert result.observations[0].observation_type == "AGGREGATE"
    assert result.observations[0].volume is None
    with pytest.raises(UnsupportedCapabilityError):
        await adapter.get_listing("anything")
    await client.aclose()


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
