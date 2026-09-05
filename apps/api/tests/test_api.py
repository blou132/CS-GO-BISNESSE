from decimal import Decimal

from fastapi.testclient import TestClient

import app.main as main
from app.core.config import Settings, get_settings
from app.models import Base


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
            live = client.get("/api/dashboard?mode=live")
            assert live.status_code == 200
            assert live.json()["listings"] == []
            demo = client.post("/api/sync?mode=demo")
            assert demo.status_code == 200
            payload = demo.json()
            assert payload["mode"] == "demo"
            assert len(payload["listings"]) == 16
            assert all("DEMO" in " ".join(row["warnings"]) for row in payload["listings"])
            assert any(Decimal(row["potential_profit_eur"]) > 0 for row in payload["listings"])
            assert client.get("/api/dashboard?mode=live").json()["listings"] == []
            item_id = payload["listings"][0]["id"]
            detail = client.get(f"/api/items/{item_id}?mode=demo")
            assert detail.status_code == 200
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
