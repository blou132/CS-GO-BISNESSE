import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.markets import CSFloatAdapter, DMarketAdapter, SkinportAdapter
from app.markets.base import MarketAdapter, MarketAdapterError
from app.models import MarketSyncState
from app.services.analysis import refresh_opportunities
from app.services.storage import persist_result

logger = logging.getLogger(__name__)


class SyncAlreadyRunning(Exception):
    def __init__(self, platform: str | None = None) -> None:
        self.platform = platform
        message = (
            f"Une synchronisation {platform} est déjà en cours."
            if platform
            else "Une synchronisation est déjà en cours."
        )
        super().__init__(message)


@dataclass(frozen=True)
class SyncRunSummary:
    platform: str
    status: str
    message: str
    duration_ms: int
    items_received: int
    items_created: int
    items_updated: int


class SyncCoordinator:
    def __init__(self) -> None:
        self._locks: dict[str, asyncio.Lock] = {}

    def _lock(self, platform: str) -> asyncio.Lock:
        lock = self._locks.get(platform)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[platform] = lock
        return lock

    def any_running(self, platforms: list[str] | tuple[str, ...]) -> bool:
        return any(self._lock(platform).locked() for platform in platforms)

    def is_running(self, platform: str) -> bool:
        return self._lock(platform).locked()

    async def synchronize_platform(
        self,
        factory: sessionmaker[Session],
        platform: str,
        adapter: MarketAdapter,
        settings: Settings,
        query: str,
    ) -> SyncRunSummary:
        lock = self._lock(platform)
        if lock.locked():
            raise SyncAlreadyRunning(platform)
        async with lock:
            return await _synchronize_platform(factory, platform, adapter, settings, query)


def build_adapters(settings: Settings) -> dict[str, MarketAdapter]:
    return {
        "csfloat": CSFloatAdapter(
            settings.csfloat_api_key.get_secret_value() if settings.csfloat_api_key else None
        ),
        "skinport": SkinportAdapter(),
        "dmarket": DMarketAdapter(
            settings.dmarket_public_key.get_secret_value() if settings.dmarket_public_key else None,
            settings.dmarket_secret_key.get_secret_value() if settings.dmarket_secret_key else None,
        ),
    }


def _state(session: Session, platform: str) -> MarketSyncState:
    value = session.scalar(
        select(MarketSyncState).where(
            MarketSyncState.mode == "live",
            MarketSyncState.platform == platform,
        )
    )
    if value is None:
        value = MarketSyncState(
            mode="live", platform=platform, status="idle", message="Synchronisation non exécutée."
        )
        session.add(value)
    return value


def set_next_run_at(
    factory: sessionmaker[Session],
    platform: str,
    next_run_at: datetime,
) -> None:
    with factory() as session:
        state = _state(session, platform)
        state.next_run_at = next_run_at
        session.commit()


async def synchronize(
    factory: sessionmaker[Session],
    adapters: dict[str, MarketAdapter],
    settings: Settings,
    query: str,
    coordinator: SyncCoordinator | None = None,
) -> list[SyncRunSummary]:
    active = coordinator or SyncCoordinator()
    platforms = tuple(adapters)
    if active.any_running(platforms):
        raise SyncAlreadyRunning()
    return list(
        await asyncio.gather(
            *(
                active.synchronize_platform(factory, name, adapter, settings, query)
                for name, adapter in adapters.items()
            )
        )
    )


async def _synchronize_platform(
    factory: sessionmaker[Session],
    platform: str,
    adapter: MarketAdapter,
    settings: Settings,
    query: str,
) -> SyncRunSummary:
    started_at = datetime.now(UTC)
    started = time.perf_counter()
    logger.info(
        "market_sync",
        extra={
            "component": "market_sync",
            "event": "sync_started",
            "market": platform,
            "mode": "live",
        },
    )
    try:
        result = await adapter.search_items(query)
    except Exception as error:
        duration_ms = _duration_ms(started)
        status, code, message = _safe_error(error)
        completed_at = datetime.now(UTC)
        with factory() as session:
            state = _state(session, platform)
            state.last_attempt_at = started_at
            state.status = status
            state.message = message
            state.last_failure_at = completed_at
            state.last_duration_ms = duration_ms
            state.last_error = message
            state.last_error_at = completed_at
            state.last_error_code = code
            state.last_error_message = message
            state.consecutive_failures = (state.consecutive_failures or 0) + 1
            session.commit()
        logger.warning(
            "market_sync",
            extra={
                "component": "market_sync",
                "event": "sync_failed",
                "market": platform,
                "mode": "live",
                "status": status,
                "duration_ms": duration_ms,
                "error_code": code,
                "error": code,
            },
        )
        return SyncRunSummary(platform, status, message, duration_ms, 0, 0, 0)

    completed_at = datetime.now(UTC)
    duration_ms = _duration_ms(started)
    with factory() as session:
        state = _state(session, platform)
        state.last_attempt_at = started_at
        stats = persist_result(session, result, platform, "live", settings)
        refresh_opportunities(session, "live", settings)
        state.status = "online"
        state.message = "; ".join(result.warnings) or "Synchronisation réussie."
        state.last_sync_at = completed_at
        state.last_success_at = completed_at
        state.last_duration_ms = duration_ms
        state.last_items_received = stats.items_received
        state.last_items_created = stats.listings_created
        state.last_items_updated = stats.listings_updated
        state.consecutive_failures = 0
        session.commit()
    logger.info(
        "market_sync",
        extra={
            "component": "market_sync",
            "event": "sync_completed",
            "market": platform,
            "mode": "live",
            "status": "online",
            "duration_ms": duration_ms,
            "items_received": stats.items_received,
            "items_created": stats.listings_created,
            "items_updated": stats.listings_updated,
        },
    )
    return SyncRunSummary(
        platform=platform,
        status="online",
        message="Synchronisation réussie.",
        duration_ms=duration_ms,
        items_received=stats.items_received,
        items_created=stats.listings_created,
        items_updated=stats.listings_updated,
    )


def _safe_error(error: Exception) -> tuple[str, str, str]:
    if isinstance(error, MarketAdapterError):
        status = "not_configured" if error.code == "configuration" else "error"
        if error.code == "rate_limited":
            status = "unavailable"
        return status, error.code, error.message
    return "error", "internal", "Erreur interne pendant la synchronisation."


def _duration_ms(started: float) -> int:
    return max(0, int((time.perf_counter() - started) * 1000))


async def close_adapters(adapters: dict[str, MarketAdapter]) -> None:
    await asyncio.gather(*(adapter.aclose() for adapter in adapters.values()))
