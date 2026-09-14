import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.db.session import build_engine, build_session_factory
from app.markets.base import AdapterListing, AdapterObservation, AdapterResult, MarketAdapter
from app.models import Base, MarketOpportunity, MarketSyncState
from app.services.analysis import market_statuses
from app.services.demo import ensure_demo
from app.services.monitoring import build_market_monitor
from app.services.scheduler import MarketSyncScheduler
from app.services.sync import SyncAlreadyRunning, SyncCoordinator


class StubAdapter(MarketAdapter):
    market = "STUB"

    def __init__(self, delay: float = 0) -> None:
        self.calls = 0
        self.delay = delay

    async def search_items(self, query: str) -> AdapterResult:
        self.calls += 1
        if self.delay:
            await asyncio.sleep(self.delay)
        return AdapterResult()

    async def get_listing(self, external_id: str) -> AdapterListing:
        raise NotImplementedError

    async def get_market_stats(self, query: str) -> list[AdapterObservation]:
        return []

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_partial_sync_persists_primary_data_and_exposes_degraded_health(tmp_path):
    from decimal import Decimal

    from app.models import PriceObservation
    from app.services.health import system_health

    class PartialAdapter(StubAdapter):
        async def search_items(self, query: str) -> AdapterResult:
            return AdapterResult(
                observations=[
                    AdapterObservation(
                        market_hash_name="TEST Skin",
                        price=Decimal("10"),
                        currency="EUR",
                        observation_type="AGGREGATE",
                        timestamp=datetime.now(UTC),
                    )
                ],
                warnings=["Enrichissement sales_history indisponible (rate_limited)."],
                partial_errors={"sales_history": "rate_limited"},
            )

    settings, engine, factory = _factory(tmp_path)
    summary = await SyncCoordinator().synchronize_platform(
        factory, "skinport", PartialAdapter(), settings, "TEST Skin"
    )
    assert summary.status == "degraded"
    with factory() as session:
        assert session.scalar(select(PriceObservation)) is not None
        market = system_health(session, settings).markets["skinport"]
        assert market.status == "degraded"
        assert market.last_success_at is not None
        assert "sales_history" in market.last_error
        monitor = build_market_monitor(session, settings, scheduler_running=False)
        assert any("partielle" in warning for warning in monitor.warnings)
    await SyncCoordinator().synchronize_platform(
        factory, "skinport", StubAdapter(), settings, "TEST Skin"
    )
    with factory() as session:
        assert system_health(session, settings).markets["skinport"].status == "online"
    engine.dispose()


def _factory(tmp_path: Path) -> tuple[Settings, Engine, sessionmaker[Session]]:
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'monitoring.db'}", environment="test")
    engine = build_engine(settings.database_url)
    Base.metadata.create_all(engine)
    return settings, engine, build_session_factory(engine)


def test_market_statuses_distinguish_not_configured_and_very_stale(tmp_path) -> None:
    settings, engine, factory = _factory(tmp_path)
    with factory() as session:
        session.add(
            MarketSyncState(
                mode="live",
                platform="skinport",
                status="online",
                message="Ancien succès",
                last_sync_at=datetime.now(UTC) - timedelta(days=3),
                last_success_at=datetime.now(UTC) - timedelta(days=3),
                last_attempt_at=datetime.now(UTC) - timedelta(days=3),
            )
        )
        session.commit()
        statuses = {
            status.platform: status for status in market_statuses(session, "live", settings)
        }

    assert statuses["csfloat"].status == "not_configured"
    assert statuses["dmarket"].status == "not_configured"
    assert statuses["skinport"].status == "very_stale"
    assert statuses["skinport"].freshness == "very_stale"
    engine.dispose()


@pytest.mark.asyncio
async def test_sync_coordinator_blocks_concurrent_runs_for_same_market(tmp_path) -> None:
    settings, engine, factory = _factory(tmp_path)
    adapter = StubAdapter(delay=0.05)
    coordinator = SyncCoordinator()
    first = asyncio.create_task(
        coordinator.synchronize_platform(factory, "skinport", adapter, settings, "AK-47")
    )
    await asyncio.sleep(0)
    with pytest.raises(SyncAlreadyRunning):
        await coordinator.synchronize_platform(factory, "skinport", adapter, settings, "AK-47")
    await first
    assert adapter.calls == 1
    engine.dispose()


@pytest.mark.asyncio
async def test_scheduler_is_optional_and_records_next_run(tmp_path) -> None:
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'scheduler.db'}",
        environment="test",
        market_sync_enabled=True,
        market_sync_query="AK-47",
        skinport_sync_interval_seconds=300,
    )
    engine = build_engine(settings.database_url)
    Base.metadata.create_all(engine)
    factory = build_session_factory(engine)
    adapter = StubAdapter()
    scheduler = MarketSyncScheduler(
        factory,
        {"skinport": adapter},
        settings,
        SyncCoordinator(),
    )
    now = datetime.now(UTC)

    await scheduler.run_pending_once(now)
    await scheduler.run_pending_once(now)

    with factory() as session:
        state = session.scalar(
            select(MarketSyncState).where(MarketSyncState.platform == "skinport")
        )

    assert adapter.calls == 1
    assert state is not None
    assert state.next_run_at is not None
    assert state.last_success_at is not None
    engine.dispose()


def test_market_monitor_metrics_do_not_count_demo_rows(tmp_path) -> None:
    settings, engine, factory = _factory(tmp_path)
    with factory() as session:
        ensure_demo(session, settings)
        active_demo_opportunities = list(
            session.scalars(
                select(MarketOpportunity).where(
                    MarketOpportunity.mode == "demo",
                    MarketOpportunity.status == "ACTIVE",
                )
            )
        )
        monitor = build_market_monitor(session, settings)

    assert active_demo_opportunities
    assert monitor.metrics.total_listings == 0
    assert monitor.metrics.active_listings == 0
    assert monitor.metrics.price_observations == 0
    assert monitor.metrics.active_opportunities == 0
    assert monitor.sync_enabled is False
    engine.dispose()
