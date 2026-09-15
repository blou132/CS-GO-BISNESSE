"""Optional Skinport stream, bounded ingestion and independent REST health."""

import asyncio
import logging
import random
import time
from collections import deque
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

import aiohttp
import socketio  # type: ignore[import-untyped]
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.markets.http import retry_after_seconds
from app.markets.skinport import normalize_sale_feed
from app.schemas.api import RealtimeStatus
from app.services.realtime_storage import BatchStats, FeedEvent, persist_feed_batch

logger = logging.getLogger(__name__)
Handler = Callable[[Any], Awaitable[None]]


class StreamTransport(Protocol):
    http_status: int | None

    async def connect(self, handler: Handler) -> None: ...
    async def wait(self) -> None: ...
    async def close(self) -> None: ...


class SkinportTransport:
    def __init__(self) -> None:
        self.http_status: int | None = None
        self.retry_after: float | None = None
        self._http: aiohttp.ClientSession | None = None
        self._client: Any = None

    async def connect(self, handler: Handler) -> None:
        trace = aiohttp.TraceConfig()

        async def response(session: Any, context: Any, params: Any) -> None:
            self.http_status = params.response.status
            self.retry_after = retry_after_seconds(params.response.headers.get("Retry-After"))

        trace.on_request_end.append(response)
        self._http = aiohttp.ClientSession(trace_configs=[trace])
        silent = logging.Logger("skinport_protocol", level=logging.CRITICAL + 1)
        self._client = socketio.AsyncClient(
            serializer="msgpack",
            reconnection=False,
            http_session=self._http,
            logger=silent,
            engineio_logger=silent,
            websocket_extra_options={"max_msg_size": 1048576},
        )
        self._client.on("saleFeed", handler)
        await self._client.connect(
            "https://skinport.com", transports=["websocket"], wait_timeout=15
        )
        await self._client.emit("saleFeedJoin", {"currency": "EUR", "locale": "en", "appid": 730})

    async def wait(self) -> None:
        await self._client.wait()

    async def close(self) -> None:
        try:
            if self._client is not None:
                await self._client.shutdown()
        finally:
            if self._http is not None:
                await self._http.close()


def reconnect_delay(failures: int, jitter: float | None = None) -> float:
    base = min(300, 5 * 2 ** min(max(0, failures - 1), 6))
    return float(min(300, base * (1 + 0.2 * (random.random() if jitter is None else jitter))))


class SkinportRealtime:
    def __init__(
        self,
        factory: sessionmaker[Session],
        settings: Settings,
        *,
        transport_factory: Callable[[], StreamTransport] = SkinportTransport,
    ) -> None:
        self.factory = factory
        self.settings = settings
        self._transport_factory = transport_factory
        self.queue: asyncio.Queue[FeedEvent] = asyncio.Queue(settings.skinport_realtime_queue_size)
        self.state = RealtimeStatus(enabled=settings.skinport_realtime_enabled)
        self._stop = asyncio.Event()
        self._receiver: asyncio.Task[None] | None = None
        self._consumer: asyncio.Task[None] | None = None
        self._events: deque[float] = deque(maxlen=60000)

    def snapshot(self) -> RealtimeStatus:
        value = self.state.model_copy(deep=True)
        value.queue_depth = self.queue.qsize()
        value.events_per_minute = sum(
            stamp >= time.monotonic() - 60 for stamp in list(self._events)
        )
        last_seen = value.last_event_at or value.connected_since
        if (
            value.connected
            and last_seen
            and (datetime.now(UTC) - last_seen).total_seconds()
            > self.settings.skinport_realtime_stale_seconds
        ):
            value.status = "degraded"
            value.last_error = "stream_stale"
        return value

    async def start(self) -> None:
        if not self.settings.skinport_realtime_enabled or self._receiver is not None:
            return
        self._stop.clear()
        self.state.status = "connecting"
        self._receiver = asyncio.create_task(self._receive(), name="skinport-realtime")
        self._consumer = asyncio.create_task(self._consume(), name="skinport-ingestion")

    async def stop(self) -> None:
        self._stop.set()
        if self._receiver is not None:
            self._receiver.cancel()
            await asyncio.gather(self._receiver, return_exceptions=True)
        if self._consumer is not None:
            # The worker drains its bounded queue; DB statements are time-limited.
            await self._consumer
        self._receiver = self._consumer = None
        self.state.connected = False
        self.state.connected_since = None
        self.state.status = "stopped" if self.settings.skinport_realtime_enabled else "disabled"

    async def accept(self, payload: Any) -> None:
        if (
            not isinstance(payload, dict)
            or not isinstance(payload.get("eventType"), str)
            or payload.get("eventType") not in {"listed", "sold"}
            or not isinstance(payload.get("sales"), list)
        ):
            self.state.invalid_events += 1
            return
        rows = payload["sales"]
        self.state.dropped_events += max(0, len(rows) - 100)
        for row in rows[:100]:
            now = datetime.now(UTC)
            self.state.events_received += 1
            self.state.last_event_at = now
            self._events.append(time.monotonic())
            if not isinstance(row, dict):
                self.state.invalid_events += 1
                continue
            name = row.get("marketHashName")
            if (
                not isinstance(name, str)
                or self.settings.market_sync_query.casefold() not in name.casefold()
            ):
                self.state.filtered_events += 1
                continue
            try:
                result = normalize_sale_feed(
                    {"eventType": payload["eventType"], "sales": [row]},
                    now,
                    price_unit=self.settings.skinport_realtime_price_unit,
                    price_unit_source=self.settings.skinport_realtime_price_unit_source,
                )
                if not result.listings and not result.realized_sales:
                    raise ValueError("invalid_event")
            except (ValueError, TypeError, KeyError):
                self.state.invalid_events += 1
                self.state.last_error = (
                    "unverified_price_unit"
                    if self.settings.skinport_realtime_price_unit == "unverified"
                    else "invalid_event"
                )
                self.state.status = "degraded"
                continue
            try:
                self.queue.put_nowait(FeedEvent(result, now))
            except asyncio.QueueFull:
                self.state.dropped_events += 1
                self.state.last_error = "queue_full"
                self.state.status = "degraded"

    async def _receive(self) -> None:
        failures = 0
        while not self._stop.is_set():
            transport = self._transport_factory()
            self.state.last_attempt_at = datetime.now(UTC)
            self.state.status = "connecting"
            started = time.monotonic()
            try:
                await asyncio.wait_for(transport.connect(self.accept), timeout=20)
                self.state.connected = True
                self.state.connected_since = datetime.now(UTC)
                self.state.http_status = transport.http_status
                self.state.status = "connected"
                self.state.last_error = None
                self.state.next_retry_at = None
                await transport.wait()
                if time.monotonic() - started >= 60:
                    failures = 0
            except asyncio.CancelledError:
                raise
            except Exception:
                self.state.errors += 1
                self.state.last_error = "connection_failed"
            finally:
                self.state.http_status = transport.http_status
                self.state.connected = False
                self.state.connected_since = None
                try:
                    await transport.close()
                except Exception:
                    self.state.errors += 1
                    self.state.last_error = "transport_close_failed"
            failures += 1
            delay = reconnect_delay(failures)
            if self.state.http_status in {401, 403, 429}:
                delay = 300  # No bypass or fast retry after an upstream refusal.
            delay = max(delay, getattr(transport, "retry_after", None) or 0)
            self.state.status = "disconnected"
            self.state.reconnect_count += 1
            self.state.next_retry_at = datetime.now(UTC) + timedelta(seconds=delay)
            logger.warning(
                "skinport_stream",
                extra={
                    "market": "skinport",
                    "component": "realtime",
                    "event": "reconnect_scheduled",
                    "status": "disconnected",
                    "error_code": self.state.last_error,
                },
            )
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=delay)
            except TimeoutError:
                pass

    async def _consume(self) -> None:
        maintenance_at = 0.0
        while not self._stop.is_set() or not self.queue.empty():
            batch: list[FeedEvent] = []
            try:
                batch.append(await asyncio.wait_for(self.queue.get(), timeout=1))
                while len(batch) < 20 and not self.queue.empty():
                    batch.append(self.queue.get_nowait())
            except TimeoutError:
                if time.monotonic() < maintenance_at:
                    continue
            started = time.monotonic()
            try:
                try:
                    stats: BatchStats = await asyncio.to_thread(
                        persist_feed_batch, self.factory, batch, self.settings
                    )
                except Exception:
                    # Receipts and writes commit together; one retry cannot duplicate a batch.
                    self.state.errors += 1
                    await asyncio.sleep(1)
                    stats = await asyncio.to_thread(
                        persist_feed_batch, self.factory, batch, self.settings
                    )
                self.state.listings_updated += stats.listings
                self.state.sales_received += stats.sales
                self.state.duplicate_events += stats.duplicates
                self.state.last_batch_duration_ms = round((time.monotonic() - started) * 1000)
                if batch:
                    self.state.last_success_at = datetime.now(UTC)
                    self.state.last_error = None
                    self.state.status = "online" if self.state.connected else "disconnected"
            except Exception:
                self.state.errors += 1
                self.state.dropped_events += len(batch)
                self.state.last_error = "database_write_failed"
                self.state.status = "degraded" if self.state.connected else "disconnected"
                logger.warning(
                    "skinport_stream",
                    extra={
                        "market": "skinport",
                        "component": "realtime",
                        "event": "ingestion_failed",
                        "error_code": "database_write_failed",
                    },
                )
            finally:
                maintenance_at = time.monotonic() + 30
                for _ in batch:
                    self.queue.task_done()
