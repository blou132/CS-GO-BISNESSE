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
