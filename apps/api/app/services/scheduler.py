import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.markets.base import MarketAdapter
from app.services.sync import SyncAlreadyRunning, SyncCoordinator, SyncRunSummary, set_next_run_at

logger = logging.getLogger(__name__)


class MarketSyncScheduler:
    def __init__(
        self,
        factory: sessionmaker[Session],
        adapters: dict[str, MarketAdapter],
        settings: Settings,
        coordinator: SyncCoordinator,
    ) -> None:
        self._factory = factory
        self._adapters = adapters
        self._settings = settings
        self._coordinator = coordinator
        self._stop = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        now = datetime.now(UTC)
        self._next_runs: dict[str, datetime] = {platform: now for platform in adapters}

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start(self) -> None:
        if not self._settings.market_sync_enabled or self.running:
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._run(), name="market-sync-scheduler")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._stop.set()
        try:
            await asyncio.wait_for(self._task, timeout=10)
        except TimeoutError:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
        finally:
            self._task = None

    def next_run_at(self, platform: str) -> datetime | None:
        return self._next_runs.get(platform)

    async def run_pending_once(self, now: datetime | None = None) -> list[SyncRunSummary]:
        if not self._settings.market_sync_enabled:
            return []
        query = self._settings.market_sync_query.strip()
        if len(query) < 3:
            return []
        current = now or datetime.now(UTC)
        results: list[SyncRunSummary] = []
        for platform, adapter in self._adapters.items():
            due_at = self._next_runs.get(platform, current)
            if due_at > current:
                continue
            next_run = current + timedelta(seconds=self._interval(platform))
            self._next_runs[platform] = next_run
            self._record_next_run(platform, next_run)
            try:
                results.append(
                    await self._coordinator.synchronize_platform(
                        self._factory,
                        platform,
                        adapter,
                        self._settings,
                        query,
                    )
                )
            except SyncAlreadyRunning:
                logger.info(
                    "market_sync",
                    extra={
                        "component": "market_sync",
                        "event": "sync_skipped_locked",
                        "market": platform,
                        "mode": "live",
                    },
                )
            except Exception:
                logger.warning(
                    "market_sync",
                    extra={
                        "component": "market_sync",
                        "event": "sync_scheduler_error",
                        "market": platform,
                        "mode": "live",
                        "error": "internal",
                    },
                )
        return results

    async def _run(self) -> None:
        logger.info(
            "market_sync",
            extra={
                "component": "market_sync",
                "event": "scheduler_started",
                "mode": "live",
            },
        )
        while not self._stop.is_set():
            await self.run_pending_once()
            await self._sleep_until_next_run()
        logger.info(
            "market_sync",
            extra={
                "component": "market_sync",
                "event": "scheduler_stopped",
                "mode": "live",
            },
        )

    async def _sleep_until_next_run(self) -> None:
        now = datetime.now(UTC)
        next_run = min(self._next_runs.values(), default=now + timedelta(seconds=30))
        delay = min(30.0, max(1.0, (next_run - now).total_seconds()))
        try:
            await asyncio.wait_for(self._stop.wait(), timeout=delay)
        except TimeoutError:
            return

    def _interval(self, platform: str) -> int:
        if platform == "csfloat":
            return self._settings.csfloat_sync_interval_seconds
        if platform == "skinport":
            return self._settings.skinport_sync_interval_seconds
        if platform == "dmarket":
            return self._settings.dmarket_sync_interval_seconds
        return 900

    def _record_next_run(self, platform: str, next_run: datetime) -> None:
        try:
            set_next_run_at(self._factory, platform, next_run)
        except SQLAlchemyError:
            logger.warning(
                "market_sync",
                extra={
                    "component": "market_sync",
                    "event": "sync_state_next_run_failed",
                    "market": platform,
                    "mode": "live",
                    "error": "database",
                },
            )
