import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import httpx
import pytest
from nacl.exceptions import BadSignatureError
from nacl.signing import SigningKey

from app.core.config import Settings
from app.markets import smoke
from app.markets.csfloat import CSFloatAdapter
from app.markets.diagnostics import response_metadata
from app.markets.dmarket import DMarketAdapter
from app.services.realtime import SkinportRealtime


def test_http_metadata_rejects_secrets_even_in_allowlisted_header_values():
    result = response_metadata(
        {
            "Set-Cookie": "TEST_PRIVATE",
            "Authorization": "TEST_PRIVATE",
            "X-Request-ID": "TEST_PRIVATE",
            "Content-Type": "text/html; secret=TEST_PRIVATE",
            "Server": "cloudflare",
            "CF-Mitigated": "challenge",
            "Retry-After": "300",
            "X-RateLimit-Limit": "20",
            "X-RateLimit-Remaining": "TEST_PRIVATE",
        }
    )
    assert result["content_type"] == "text/html"
    assert result["cloudflare_challenge"] is True
    assert result["retry_after_seconds"] == 300
    assert result["x-ratelimit-limit"] == 20
    assert "TEST_PRIVATE" not in str(result)


@pytest.mark.asyncio
async def test_csfloat_smoke_limits_request_and_redacts_http_failure(monkeypatch):
    def handler(request):
        assert request.url.params["limit"] == "5"
        assert request.method == "GET"
        return httpx.Response(403, text="TEST_PRIVATE", headers={"Set-Cookie": "TEST_PRIVATE"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = CSFloatAdapter("TEST_PRIVATE", client=client)
        monkeypatch.setattr(smoke, "build_adapters", lambda settings: {"csfloat": adapter})
        result = await smoke.check_source(Settings(_env_file=None), "csfloat", "TEST Skin")
    assert result["authentication"] == "FAIL"
    assert result["requests"][0]["http_status"] == 403
    assert len(result["requests"]) == 1
    assert "TEST_PRIVATE" not in str(result)


@pytest.mark.asyncio
async def test_dmarket_smoke_is_one_minimal_get_without_enrichment(monkeypatch):
    key = SigningKey.generate()
    calls = []

    def handler(request):
        calls.append(request)
        assert request.url.params["limit"] == "5"
        return httpx.Response(200, json={"items": []}, headers={"X-RateLimit-Remaining": "8"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = DMarketAdapter(bytes(key.verify_key).hex(), bytes(key).hex(), client=client)
        monkeypatch.setattr(smoke, "build_adapters", lambda settings: {"dmarket": adapter})
        result = await smoke.check_source(Settings(_env_file=None), "dmarket", "TEST Skin")
    assert result["authentication"] == "OK" and result["parser"] == "OK"
    assert result["pagination"] == "UNKNOWN"
    assert len(calls) == 1


def test_dmarket_rfc8032_public_test_vector_and_signature_tampering(monkeypatch):
    # RFC 8032 section 7.1, public test-only seed. Never a marketplace credential.
    seed = "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60"
    public = "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a"
    key = SigningKey(bytes.fromhex(seed))
    assert key.sign(b"").signature.hex() == (
        "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555f"
        "b8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b"
    )
    monkeypatch.setattr("app.markets.dmarket.time.time", lambda: 1605619994)
    adapter = DMarketAdapter(public, seed)
    request = httpx.Request("GET", "https://api.dmarket.com/marketplace-api/v2/offers?limit=5")
    adapter._sign(request)
    message = b"GET/marketplace-api/v2/offers?limit=51605619994"
    signature = bytes.fromhex(request.headers["X-Request-Sign"].split()[-1])
    key.verify_key.verify(message, signature)
    for changed in (
        message.replace(b"offers", b"targets"),
        message + b"{}",
        message.replace(b"1605619994", b"1605619794"),
    ):
        with pytest.raises(BadSignatureError):
            key.verify_key.verify(changed, signature)
    with pytest.raises(BadSignatureError):
        key.verify_key.verify(message, b"\x00" * 64)
    with pytest.raises(ValueError):
        adapter._sign(httpx.Request("GET", str(request.url), content=b"{}"))
    with pytest.raises(ValueError):
        adapter._sign(httpx.Request("POST", str(request.url)))
    asyncio.run(adapter.aclose())


@pytest.mark.asyncio
async def test_recorded_provider_block_stays_disabled_without_network_or_db():
    stamp = datetime(2026, 9, 14, tzinfo=UTC)
    settings = Settings(_env_file=None, skinport_realtime_blocked_at=stamp)
    transport = AsyncMock()
    stream = SkinportRealtime(None, settings, transport_factory=transport)
    await stream.start()
    await stream.stop()
    state = stream.snapshot()
    assert not state.enabled and state.status == "blocked"
    assert state.http_status == 403 and state.last_attempt_at == stamp
    transport.assert_not_called()
    with pytest.raises(ValueError):
        Settings(
            _env_file=None,
            skinport_realtime_blocked_at=stamp,
            skinport_realtime_enabled=True,
            market_sync_query="TEST Skin",
        )
