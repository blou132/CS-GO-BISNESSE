from collections.abc import Iterator
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

import app.main as main
from app.core.config import Settings, get_settings
from app.models import Base, MarketListing, WatchRule


@pytest.fixture
def client(tmp_path, monkeypatch) -> Iterator[TestClient]:
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'watch.db'}", environment="test")
    monkeypatch.setattr(main, "get_settings", lambda: settings)
    main.app.dependency_overrides[get_settings] = lambda: settings
    try:
        with TestClient(main.app) as value:
            Base.metadata.create_all(main.app.state.engine)
            yield value
    finally:
        main.app.dependency_overrides.clear()


def payload(**filters: object) -> dict[str, object]:
    return {
        "name": "TEST Redline",
        "enabled": True,
        "filters": {"market_hash_name": "AK-47 | Redline (Field-Tested)", **filters},
    }


def test_rule_crud_is_persistent_paginated_and_mode_scoped(client: TestClient) -> None:
    created = client.post("/api/watchlist?mode=demo", json=payload(max_price_eur="25.12345678"))
    assert created.status_code == 201
    rule = created.json()
    rule_id = rule["id"]
    with main.app.state.sessions() as session:
        saved = session.get(WatchRule, rule_id)
        assert saved is not None
        assert saved.filters["max_price_eur"] == "25.12345678"
    assert client.get("/api/watchlist?mode=live").json()["total"] == 0
    for _ in range(2):
        assert client.post("/api/watchlist?mode=demo", json=payload()).status_code == 201
    page = client.get("/api/watchlist?mode=demo&page=2&page_size=2").json()
    assert (page["total"], page["pages"], len(page["items"])) == (3, 2, 1)
    assert client.put(f"/api/watchlist/{rule_id}?mode=live", json=payload()).status_code == 404
    assert client.delete(f"/api/watchlist/{rule_id}?mode=live").status_code == 404
    changed = client.put(
        f"/api/watchlist/{rule_id}?mode=demo", json={**payload(), "enabled": False}
    )
    assert changed.status_code == 200
    assert changed.json()["enabled"] is False
    assert client.get(f"/api/watchlist/{rule_id}/matches?mode=demo").status_code == 409
    assert client.delete(f"/api/watchlist/{rule_id}?mode=demo").status_code == 204
    assert client.get(f"/api/watchlist/{rule_id}/matches?mode=demo").status_code == 404


@pytest.mark.parametrize(
    "filters",
    [
        {"max_price_eur": "-1"},
        {"max_float": "NaN"},
        {"max_float": "1.1"},
        {"paint_seeds": [True]},
        {"paint_seeds": [1001]},
        {"paint_seeds": [1.5]},
        {"doppler_phase": "invented tier"},
        {"market_hash_name": "   "},
        {"sql": "DROP TABLE watch_rules"},
    ],
)
def test_invalid_rules_are_rejected(client: TestClient, filters: dict[str, object]) -> None:
    assert client.post("/api/watchlist", json=payload(**filters)).status_code == 422
    assert client.get("/api/watchlist").json()["total"] == 0


def test_matches_use_exact_identity_and_exclude_unknown_values(client: TestClient) -> None:
    client.post("/api/sync?mode=demo")
    with main.app.state.sessions() as session:
        listings = list(session.scalars(select(MarketListing)))
        target = next(
            row for row in listings if row.item.skin == "Redline" and row.platform == "csfloat"
        )
        target.item.paint_seed = 0
        # Synthetic filter fixture, not real skin data.
        target.item.doppler_phase = "Phase 2"
        target_id = target.id
        for row in listings:
            if row.id != target_id:
                row.item.float_value = None
        session.commit()
    created = client.post(
        "/api/watchlist?mode=demo",
        json=payload(
            max_price_eur="25", max_float="0.2", paint_seeds=[0, 0], doppler_phase="Phase 2"
        ),
    )
    assert created.status_code == 201
    assert created.json()["filters"]["paint_seeds"] == [0]
    rule_id = created.json()["id"]
    matches = client.get(f"/api/watchlist/{rule_id}/matches?mode=demo").json()
    assert matches["total"] == 1
    assert matches["items"][0]["id"] == target_id
    assert Decimal(matches["items"][0]["price_eur_reference"]) <= Decimal("25")
    assert client.get(f"/api/watchlist/{rule_id}/matches?mode=live").status_code == 404
    client.put(f"/api/watchlist/{rule_id}?mode=demo", json=payload(market_hash_name="Redline"))
    assert client.get(f"/api/watchlist/{rule_id}/matches?mode=demo").json()["total"] == 0
    client.put(
        f"/api/watchlist/{rule_id}?mode=demo",
        json=payload(market_hash_name="' OR 1=1 --"),
    )
    assert client.get(f"/api/watchlist/{rule_id}/matches?mode=demo").json()["total"] == 0
