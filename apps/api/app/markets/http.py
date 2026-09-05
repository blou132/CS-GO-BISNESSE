"""Bounded read-only transport with per-adapter pacing and cache stampede prevention."""

import asyncio
import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from .base import MarketAdapterError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CachedResponse:
    payload: Any
    observed_at: datetime
    expires_at: float


class ReadOnlyHTTP:
    def __init__(
        self,
        market: str,
        base_url: str,
        *,
        client: httpx.AsyncClient | None = None,
        cache_ttl: float = 60,
        min_interval: float = 1,
        max_attempts: int = 3,
        max_retry_delay: float = 5,
        timeout: float = 15,
    ) -> None:
        self.market = market
        self.base_url = base_url.rstrip("/")
        self.client = client or httpx.AsyncClient(follow_redirects=False)
        self.owns_client = client is None
        self.cache_ttl = max(0, cache_ttl)
        self.min_interval = max(0, min_interval)
        self.max_attempts = min(3, max(1, max_attempts))
        self.max_retry_delay = max(0, max_retry_delay)
        self.timeout = timeout
        self._cache: dict[str, CachedResponse] = {}
        self._lock = asyncio.Lock()
        self._next_request_at = 0.0

    async def aclose(self) -> None:
        if self.owns_client:
            await self.client.aclose()

    async def get(
        self,
        path: str,
        params: dict[str, str | int] | None = None,
        *,
        headers: dict[str, str] | None = None,
        signer: Callable[[httpx.Request], None] | None = None,
    ) -> CachedResponse:
        # Caller-controlled host or redirects could leak authorization headers.
        if not path.startswith("/") or "://" in path:
            raise ValueError("Only relative API paths are supported")
        request = self.client.build_request(
            "GET", self.base_url + path, params=params, headers=headers, timeout=self.timeout
        )
        cache_key = str(request.url)
        async with self._lock:
            cached = self._cache.get(cache_key)
            if cached and cached.expires_at > time.monotonic():
                return cached
            result = await self._fetch(request, signer)
            if len(self._cache) >= 128:
                self._cache.pop(next(iter(self._cache)))
            self._cache[cache_key] = result
            return result

    async def _fetch(
        self, request: httpx.Request, signer: Callable[[httpx.Request], None] | None
    ) -> CachedResponse:
        for attempt in range(self.max_attempts):
            remaining = self._next_request_at - time.monotonic()
            if remaining > self.max_retry_delay:
                raise MarketAdapterError(
                    "rate_limited", "Marketplace request cooldown active", remaining
                )
            if remaining > 0:
                await asyncio.sleep(remaining)
            if signer:
                signer(request)  # Renew the timestamp/signature for each retry.
            started = time.monotonic()
            self._next_request_at = started + self.min_interval
            try:
                response = await self.client.send(request, follow_redirects=False)
            except httpx.TimeoutException:
                self._log(request, "timeout", started, "timeout")
                if attempt + 1 == self.max_attempts:
                    raise MarketAdapterError("timeout", "Marketplace request timed out") from None
                await asyncio.sleep(min(0.25 * 2**attempt, self.max_retry_delay))
                continue
            except httpx.RequestError:
                self._log(request, "network_error", started, "network_error")
                raise MarketAdapterError("unavailable", "Marketplace network unavailable") from None

            status = response.status_code
            self._log(request, status, started, None if status == 200 else "upstream_http")
            if status in (401, 403):
                raise MarketAdapterError("authentication", "Marketplace access denied")
            if status == 404:
                raise MarketAdapterError("not_found", "Marketplace listing not found")
            if status == 429 or status >= 500:
                delay = retry_after_seconds(response.headers.get("Retry-After"))
                delay = delay if delay is not None else 0.5 * 2**attempt
                self._next_request_at = max(self._next_request_at, time.monotonic() + delay)
                if delay > self.max_retry_delay or attempt + 1 == self.max_attempts:
                    code = "rate_limited" if status == 429 else "unavailable"
                    raise MarketAdapterError(code, "Marketplace temporarily unavailable", delay)
                # The next iteration waits until at least Retry-After. Never truncate it.
                continue
            if status != 200:
                raise MarketAdapterError("upstream_http", "Unexpected marketplace HTTP status")
            try:
                payload = json.loads(response.content, parse_float=Decimal)
            except (ValueError, UnicodeError):
                raise MarketAdapterError("invalid_response", "Invalid marketplace JSON") from None
            return CachedResponse(
                payload=payload,
                observed_at=datetime.now(UTC),
                expires_at=time.monotonic() + self.cache_ttl,
            )
        raise AssertionError("Unreachable retry state")

    def _log(
        self, request: httpx.Request, status: int | str, started: float, error: str | None
    ) -> None:
        # Deliberately exclude URL query, headers, request/response bodies and exceptions.
        logger.info(
            json.dumps(
                {
                    "market": self.market,
                    "endpoint": request.url.path,
                    "status": status,
                    "duration_ms": round((time.monotonic() - started) * 1000, 2),
                    "error": error,
                }
            )
        )


def retry_after_seconds(value: str | None) -> float | None:
    if not value:
        return None
    try:
        number = float(value)
        if number >= 0 and number != float("inf"):
            return number
    except ValueError:
        pass
    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return max(0, (parsed - datetime.now(UTC)).total_seconds())
    except (ValueError, TypeError, OverflowError):
        return None
