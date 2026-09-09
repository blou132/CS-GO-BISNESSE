import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.currencies.ecb import ECBRateClient, persist_ecb_rates

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FXSyncSummary:
    attempted_at: datetime
    succeeded_at: datetime
    rates_received: int
    rates_created: int


class FXRateScheduler:
    def __init__(
        self,
        factory: sessionmaker[Session],
        settings: Settings,
        client: ECBRateClient | None = None,
    ) -> None:
        self._factory = factory
        self._settings = settings
        self._client = client or ECBRateClient()
        self._stop = asyncio.Event()
        self._lock = asyncio.Lock()
        self._task: asyncio.Task[None] | None = None
        self.last_attempt_at: datetime | None = None
        self.last_success_at: datetime | None = None
        self.last_error: str | None = None
        self.next_run_at: datetime | None = None

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    @property
    def runtime_status(self) -> str:
        if not self._settings.fx_reference_sync_enabled:
            return "disabled"
        if self.last_error and self.last_success_at is None:
            return "error"
        if self.last_error:
            return "degraded"
        if self.last_success_at:
            return "online"
        return "idle"

    async def start(self) -> None:
        if not self._settings.fx_reference_sync_enabled or self.running:
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._run(), name="fx-reference-rate-scheduler")

    async def stop(self) -> None:
        if self._task is not None:
            self._stop.set()
            try:
                await asyncio.wait_for(self._task, timeout=10)
            except TimeoutError:
                self._task.cancel()
                await asyncio.gather(self._task, return_exceptions=True)
            finally:
                self._task = None
        await self._client.aclose()

    async def run_once(self) -> FXSyncSummary:
        async with self._lock:
            attempted_at = datetime.now(UTC)
            self.last_attempt_at = attempted_at
            try:
                rates = await self._client.fetch_latest()
                with self._factory() as session:
                    created = persist_ecb_rates(session, rates)
                    session.commit()
            except Exception as error:
                self.last_error = str(error)[:512]
                logger.warning(
                    "fx_sync",
                    extra={
                        "component": "fx_sync",
                        "event": "fx_sync_failed",
                        "source": "ecb",
                        "error": type(error).__name__,
                    },
                )
                raise
            succeeded_at = datetime.now(UTC)
            self.last_success_at = succeeded_at
            self.last_error = None
            self.next_run_at = succeeded_at + timedelta(
                seconds=self._settings.fx_reference_sync_interval_seconds
            )
            logger.info(
                "fx_sync",
                extra={
                    "component": "fx_sync",
                    "event": "fx_sync_completed",
                    "source": "ecb",
                    "received": len(rates),
                    "rates_created": created,
                },
            )
            return FXSyncSummary(attempted_at, succeeded_at, len(rates), created)

    async def _run(self) -> None:
        while not self._stop.is_set():
            try:
                await self.run_once()
            except Exception:
                self.next_run_at = datetime.now(UTC) + timedelta(
                    seconds=self._settings.fx_reference_sync_interval_seconds
                )
            try:
                await asyncio.wait_for(
                    self._stop.wait(),
                    timeout=self._settings.fx_reference_sync_interval_seconds,
                )
            except TimeoutError:
                continue
