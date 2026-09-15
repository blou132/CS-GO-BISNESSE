import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_realtime_is_opt_in_bounded_and_requires_narrow_scope_and_unit_provenance():
    assert not Settings(_env_file=None).skinport_realtime_enabled
    for values in [
        {"skinport_realtime_enabled": True},
        {"skinport_realtime_queue_size": 0},
        {"skinport_realtime_queue_size": 5001},
        {"skinport_realtime_price_unit": "minor"},
        {"float_min_samples": 4},
    ]:
        with pytest.raises(ValidationError):
            Settings(_env_file=None, **values)


def test_empty_optional_environment_values_are_treated_as_absent(monkeypatch) -> None:
    monkeypatch.setenv("CSFLOAT_API_KEY", "")
    monkeypatch.setenv("DMARKET_PUBLIC_KEY", "")
    monkeypatch.setenv("DMARKET_SECRET_KEY", "")
    monkeypatch.setenv("FX_USD_EUR_RATE", "")
    monkeypatch.setenv("FX_RATE_SOURCE", "")
    monkeypatch.setenv("FX_RATE_TIMESTAMP", "")

    settings = Settings(_env_file=None)

    assert settings.csfloat_api_key is None
    assert settings.dmarket_public_key is None
    assert settings.dmarket_secret_key is None
    assert settings.fx_usd_eur_rate is None
    assert settings.fx_rate_source is None
    assert settings.fx_rate_timestamp is None


def test_production_settings_require_postgresql_real_password_and_explicit_cors() -> None:
    with pytest.raises(ValidationError, match="SQLite"):
        Settings(_env_file=None, environment="production", database_url="sqlite:///prod.db")
    with pytest.raises(ValidationError, match="mot de passe"):
        Settings(
            _env_file=None,
            environment="production",
            database_url=("postgresql+psycopg://cs2:replace-with-local-password@db:5432/cs2"),
        )
    with pytest.raises(ValidationError, match="CORS"):
        Settings(
            _env_file=None,
            environment="production",
            database_url="postgresql+psycopg://cs2:safe-test-only@db:5432/cs2",
            cors_origins="*",
        )
    settings = Settings(
        _env_file=None,
        environment="production",
        database_url="postgresql+psycopg://cs2:safe-test-only@db:5432/cs2",
        cors_origins="http://127.0.0.1:3000",
    )
    assert settings.environment == "production"


def test_market_monitoring_settings_are_validated() -> None:
    with pytest.raises(ValidationError, match="MARKET_SYNC_QUERY"):
        Settings(_env_file=None, market_sync_enabled=True, market_sync_query="")
    with pytest.raises(ValidationError, match="VERY_STALE_AFTER_SECONDS"):
        Settings(
            _env_file=None,
            stale_after_seconds=3600,
            very_stale_after_seconds=300,
        )
    settings = Settings(
        _env_file=None,
        market_sync_enabled=True,
        market_sync_query="AK-47 | Redline",
        csfloat_sync_interval_seconds=120,
        dmarket_sync_interval_seconds=120,
        skinport_sync_interval_seconds=300,
    )
    assert settings.market_sync_enabled is True
