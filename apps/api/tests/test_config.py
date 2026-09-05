from app.core.config import Settings


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
