from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

import app.main as main
from app.core.config import Settings, get_settings
from app.db.session import build_engine, build_session_factory
from app.markets.base import AdapterResult, MarketAdapterError
from app.models import Base, MarketSyncState
from app.services.sync import synchronize


def test_health_demo_and_live_are_isolated(tmp_path, monkeypatch) -> None:
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        environment="test",
    )
    monkeypatch.setattr(main, "get_settings", lambda: settings)
    main.app.dependency_overrides[get_settings] = lambda: settings
    try:
        with TestClient(main.app) as client:
            Base.metadata.create_all(main.app.state.engine)
            assert client.get("/health/live").json() == {"status": "ok"}
            assert client.get("/health/ready").json() == {"status": "ok"}
            system = client.get("/health/status")
            assert system.status_code == 200
            assert system.json()["api"] == "healthy"
            assert system.json()["database"] == "healthy"
            assert system.json()["markets"]["skinport"]["status"] == "idle"
            monitor = client.get("/api/market-monitor")
            assert monitor.status_code == 200
            assert monitor.json()["sync_enabled"] is False
            assert monitor.json()["metrics"]["active_listings"] == 0
            fx = client.get("/api/fx")
            assert fx.status_code == 200
            assert fx.json()["runtime_status"] == "disabled"
            assert fx.json()["rates"] == []
            catalog = client.get("/api/integrations").json()["sources"]
            ecb = next(source for source in catalog if source["id"] == "ecb")
            assert ecb["configured"] is True
            assert ecb["runtime_status"] == "disabled"
            net_profit = client.post(
                "/api/calculations/net-profit",
                json={
                    "purchase": {"item_price_eur": "100", "payment_fee_eur": "2"},
                    "sale": {"estimated_sale_price_eur": "130", "sale_fee_eur": "5"},
                    "estimated_holding_days": 5,
                },
            )
            assert net_profit.status_code == 200
            assert Decimal(net_profit.json()["net_profit_eur"]) == Decimal("23")
            assert Decimal(net_profit.json()["purchase"]["total_cost_eur"]) == Decimal("102")
            unknown_fee = client.post(
                "/api/calculations/fee",
                json={
                    "platform": "skinport",
                    "fee_type": "SELL",
                    "base_amount": "100",
                    "currency": "EUR",
                },
            )
            assert unknown_fee.status_code == 200
            assert unknown_fee.json()["known"] is False
            assert unknown_fee.json()["fee_amount"] is None
            live = client.get("/api/dashboard?mode=live")
            assert live.status_code == 200
            assert live.json()["listings"] == []
            demo = client.post("/api/sync?mode=demo")
            assert demo.status_code == 200
            payload = demo.json()
            assert payload["mode"] == "demo"
            assert len(payload["listings"]) == 16
            assert all("DEMO" in " ".join(row["warnings"]) for row in payload["listings"])
            assert all(
                row["reference_method"] == "REALIZED_SALES_MEDIAN" for row in payload["listings"]
            )
            assert all(row["risk_score"] is not None for row in payload["listings"])
            assert any(Decimal(row["potential_profit_eur"]) > 0 for row in payload["listings"])
            assert client.get("/api/dashboard?mode=live").json()["listings"] == []
            item_id = payload["listings"][0]["id"]
            detail = client.get(f"/api/items/{item_id}?mode=demo")
            assert detail.status_code == 200
            assert len(detail.json()["market_snapshots"]) == 3
            assert {entry["platform"] for entry in detail.json()["market_snapshots"]} == {
                "csfloat",
                "skinport",
                "dmarket",
            }
            assert all(
                "ask_eur" in entry and "bid_eur" in entry
                for entry in detail.json()["market_snapshots"]
            )
            assert any(entry["observation_type"] == "SALE" for entry in detail.json()["history"])
            assert any(
                entry["platform"] == "skinport" and entry["observation_type"] == "AGGREGATE"
                for entry in detail.json()["history"]
            )
            listing_comparisons = [
                entry
                for entry in detail.json()["comparisons"]
                if entry["observation_type"] == "LISTING"
            ]
            assert any(
                Decimal(entry["median_gap_to_best_eur"]) > 0 for entry in listing_comparisons
            )
            assert all(
                entry["median_gap_to_best_percent"] is not None for entry in listing_comparisons
            )
            assert client.get(f"/api/items/{item_id}?mode=live").status_code == 404
    finally:
        main.app.dependency_overrides.clear()


def test_database_failure_changes_readiness_but_not_liveness(tmp_path, monkeypatch) -> None:
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'startup.db'}",
        environment="test",
    )
    monkeypatch.setattr(main, "get_settings", lambda: settings)
    main.app.dependency_overrides[get_settings] = lambda: settings

    class BrokenSession:
        def execute(self, _statement: object) -> None:
            raise OperationalError("SELECT 1", {}, RuntimeError("database offline"))

        def rollback(self) -> None:
            return None

    main.app.dependency_overrides[main.database_session] = lambda: BrokenSession()
    try:
        with TestClient(main.app) as client:
            assert client.get("/health/live").status_code == 200
            assert client.get("/health/ready").status_code == 503
            system = client.get("/health/status")
            assert system.status_code == 200
            assert system.json()["database"] == "unavailable"
            assert all(
                market["status"] == "unknown" for market in system.json()["markets"].values()
            )
    finally:
        main.app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_sync_keeps_last_error_after_a_later_success(tmp_path) -> None:
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'sync.db'}",
        environment="test",
    )
    engine = build_engine(settings.database_url)
    Base.metadata.create_all(engine)
    factory = build_session_factory(engine)
    adapter = AsyncMock()
    adapter.search_items.side_effect = MarketAdapterError("unavailable", "Source indisponible")

    await synchronize(factory, {"skinport": adapter}, settings, "AK-47")
    with factory() as session:
        failed = session.scalar(select(MarketSyncState))
        assert failed is not None
        assert failed.status == "error"
        assert failed.last_error == "Source indisponible"
        assert failed.last_error_at is not None
        failed_at = failed.last_error_at

    adapter.search_items.side_effect = None
    adapter.search_items.return_value = AdapterResult()
    await synchronize(factory, {"skinport": adapter}, settings, "AK-47")
    with factory() as session:
        recovered = session.scalar(select(MarketSyncState))
        assert recovered is not None
        assert recovered.status == "online"
        assert recovered.last_sync_at is not None
        assert recovered.last_error == "Source indisponible"
        assert recovered.last_error_at == failed_at

    engine.dispose()
