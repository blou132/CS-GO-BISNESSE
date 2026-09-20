from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from nacl.signing import SigningKey

from app.markets import CSFloatAdapter, CSFloatSearch, DMarketAdapter, SkinportAdapter
from app.markets import http as market_http
from app.markets.base import MarketAdapterError
from app.markets.http import ReadOnlyHTTP


@pytest.mark.asyncio
@pytest.mark.parametrize("platform", ["csfloat", "dmarket"])
@pytest.mark.parametrize(
    "status,code",
    [
        (401, "authentication"),
        (403, "authentication"),
        (404, "not_found"),
        (429, "rate_limited"),
        (500, "unavailable"),
        (502, "unavailable"),
        (503, "unavailable"),
        (200, "invalid_response"),
        (0, "timeout"),
    ],
)
async def test_authenticated_adapters_fail_closed_without_leaking_payload(platform, status, code):
    calls = []

    def handler(request):
        calls.append(request)
        assert request.method == "GET"
        if status == 0:
            raise httpx.ReadTimeout("TEST_PRIVATE", request=request)
        return httpx.Response(status, text="TEST_PRIVATE", headers={"Retry-After": "600"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        key = SigningKey.generate()
        adapter = (
            CSFloatAdapter("TEST_ONLY", client=client)
            if platform == "csfloat"
            else DMarketAdapter(bytes(key.verify_key).hex(), bytes(key).hex(), client=client)
        )
        adapter._http.max_attempts = 1
        with pytest.raises(MarketAdapterError) as error:
            await adapter.search_items("TEST Skin")
    assert error.value.code == code
    assert "TEST_PRIVATE" not in str(error.value)
    assert len(calls) == 1


def test_csfloat_cursor_is_explicit_bounded_and_not_auto_paginated():
    assert (
        CSFloatSearch(cursor="documented-opaque-cursor").parameters()["cursor"]
        == "documented-opaque-cursor"
    )
    with pytest.raises(ValueError):
        CSFloatSearch(cursor="x" * 513)


@pytest.mark.asyncio
async def test_skinport_default_pacing_reaches_history_without_local_429(monkeypatch) -> None:
    clock = [1000.0]
    waits = []

    async def sleep(seconds):
        waits.append(seconds)
        clock[0] += seconds

    monkeypatch.setattr(market_http, "time", SimpleNamespace(monotonic=lambda: clock[0]))
    monkeypatch.setattr(market_http.asyncio, "sleep", sleep)
    calls = []

    def handler(request):
        calls.append(request.url.path)
        assert request.method == "GET"
        if request.url.path.endswith("/items"):
            return httpx.Response(
                200,
                json=[
                    {
                        "market_hash_name": "TEST Skin",
                        "min_price": 10,
                        "quantity": 3,
                        "currency": "EUR",
                        "updated_at": 1789290000,
                    }
                ],
            )
        return httpx.Response(
            200,
            json=[
                {
                    "market_hash_name": "TEST Skin",
                    "currency": "EUR",
                    "last_7_days": {"median": 9, "volume": 2},
                }
            ],
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await SkinportAdapter(client=client).search_items("TEST Skin")
    assert calls == ["/v1/items", "/v1/sales/history"]
    assert waits == [38]
    assert len(result.observations) == 1
    assert len(result.aggregates) == 1


@pytest.mark.asyncio
async def test_skinport_history_failure_keeps_primary_aggregates() -> None:
    def handler(request):
        if request.url.path.endswith("/items"):
            return httpx.Response(
                200,
                json=[
                    {
                        "market_hash_name": "TEST Skin",
                        "min_price": 10,
                        "quantity": 3,
                        "currency": "EUR",
                        "updated_at": 1789290000,
                    }
                ],
            )
        return httpx.Response(429, headers={"Retry-After": "300"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await SkinportAdapter(client=client, min_interval=0).search_items("TEST Skin")
    assert len(result.observations) == 1
    assert result.aggregates == []
    assert result.partial_errors == {"sales_history": "rate_limited"}


@pytest.mark.asyncio
async def test_server_retry_after_still_blocks_next_request_without_truncation(monkeypatch):
    sleep = AsyncMock()
    monkeypatch.setattr(market_http.asyncio, "sleep", sleep)
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(429, headers={"Retry-After": "300"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        transport = ReadOnlyHTTP("test", "https://example.test", client=client, min_interval=38)
        with pytest.raises(MarketAdapterError):
            await transport.get("/items")
        with pytest.raises(MarketAdapterError) as blocked:
            await transport.get("/history")
    assert blocked.value.code == "rate_limited"
    assert blocked.value.retry_after_seconds > 290
    assert len(calls) == 1
    sleep.assert_not_called()


@pytest.mark.parametrize(
    "values",
    [
        {"min_float": 0.8, "max_float": 0.1},
        {"min_price_cents": 100, "max_price_cents": 10},
        {"min_price_cents": True},
        {"category": "anything"},
    ],
)
def test_csfloat_rejects_invalid_filter_ranges(values):
    with pytest.raises(ValueError):
        CSFloatSearch(**values)


@pytest.mark.asyncio
async def test_dmarket_keeps_offers_when_supplementary_routes_fail():
    key = SigningKey.generate()
    calls = []

    def handler(request):
        calls.append(request.url.path)
        assert request.method == "GET"
        if request.url.path.endswith("/offers"):
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "offerId": "test-offer",
                            "priceCents": "1234",
                            "locked": False,
                            "attributes": {
                                "gameId": "a8db",
                                "title": "TEST Skin",
                                "cs2": {"float": 0},
                            },
                        }
                    ]
                },
            )
        if "/targets-by-title/" in request.url.path:
            return httpx.Response(403, text="private upstream data must not escape")
        if request.url.path.endswith("/last-sales"):
            return httpx.Response(200, json={"sales": []})
        return httpx.Response(200, json={"unexpected": "malformed fee schedule"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = DMarketAdapter(bytes(key.verify_key).hex(), bytes(key).hex(), client=client)
        adapter._http.min_interval = 0
        result = await adapter.search_items("TEST Skin")
    assert len(calls) == 4
    assert len(result.listings) == 1
    assert result.listings[0].item.float_value == 0
    assert result.partial_errors == {"buy_orders": "authentication", "fees": "invalid_response"}
    assert "private upstream" not in result.model_dump_json()


@pytest.mark.asyncio
async def test_skinport_history_rejects_wrong_item_currency_and_oversized_batch():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(
            200,
            json=[
                {
                    "market_hash_name": "WRONG Skin",
                    "currency": "USD",
                    "last_7_days": {"median": 100, "volume": 10},
                }
            ],
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = SkinportAdapter(client=client, min_interval=0)
        with pytest.raises(MarketAdapterError):
            await adapter.get_sales_history([f"TEST Skin {i}" for i in range(21)])
        assert calls == []
        with pytest.raises(MarketAdapterError):
            await adapter.get_sales_history("TEST Skin")


@pytest.mark.asyncio
async def test_transport_never_follows_redirect_with_authorization():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(302, headers={"Location": "https://untrusted.example/collect"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        transport = ReadOnlyHTTP("test", "https://example.test", client=client)
        with pytest.raises(MarketAdapterError):
            await transport.get("/items", headers={"Authorization": "TEST_ONLY"})
    assert len(calls) == 1
    assert calls[0].url.host == "example.test"
