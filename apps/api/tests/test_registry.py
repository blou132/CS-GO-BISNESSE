from app.core.config import Settings
from app.markets.registry import SOURCES, source_catalog
from app.schemas.api import MarketStatus


def test_registry_keeps_tradeit_and_gamerpay_decisions_explicit() -> None:
    sources = {source.id: source for source in SOURCES}

    assert sources["tradeit_gg"].access_status == "RESEARCH_REQUIRED"
    assert "tradeit.app" in sources["tradeit_gg"].note
    assert sources["gamerpay"].access_status == "UNAVAILABLE"
    assert sources["gamerpay"].capabilities == ()


def test_catalog_reports_configuration_without_exposing_secrets() -> None:
    settings = Settings(
        _env_file=None,
        csfloat_api_key="private-value",
        dmarket_public_key=None,
        dmarket_secret_key=None,
    )
    skinport = MarketStatus(
        platform="skinport",
        integration_status="PARTIAL",
        status="online",
        message="ok",
    )

    catalog = {row["id"]: row for row in source_catalog(settings, [skinport], {"ecb": "online"})}

    assert catalog["csfloat"]["configured"] is True
    assert catalog["dmarket"]["configured"] is False
    assert catalog["skinport"]["runtime_status"] == "online"
    assert catalog["ecb"]["configured"] is True
    assert catalog["ecb"]["runtime_status"] == "online"
    assert "private-value" not in repr(catalog)


def test_discovery_does_not_enable_unintegrated_sources_or_skinport_feed() -> None:
    catalog = {row["id"]: row for row in source_catalog(Settings(_env_file=None), [])}
    sniper = catalog["skinsniper"]
    assert sniper["source_type"] == "AGGREGATOR"
    assert sniper["roles"] == ("AGGREGATOR", "REFERENCE_SOURCE", "MARKET_DISCOVERY_SOURCE")
    assert sniper["api_discovery_status"] == "API_NOT_FOUND"
    assert sniper["auth_required"] is None
    for name in (
        "skinsniper",
        "white_market",
        "waxpeer",
        "haloskins",
        "buff_market",
        "buff_163",
        "skinflow",
    ):
        assert catalog[name]["configured"] is False
        assert catalog[name]["runtime_status"] == "not_integrated"
        assert catalog[name]["collected_capabilities"] == ()
    assert "WEBSOCKET" in catalog["skinport"]["capabilities"]
    assert "WEBSOCKET" not in catalog["skinport"]["collected_capabilities"]
    assert len({source.id for source in SOURCES}) == len(SOURCES)
    for source in SOURCES:
        assert set(catalog[source.id]["collected_capabilities"]) <= set(source.capabilities)
