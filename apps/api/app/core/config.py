from datetime import datetime
from decimal import Decimal
from functools import lru_cache
from typing import Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../../.env", ".env"),
        env_ignore_empty=True,
        extra="ignore",
    )

    database_url: str = "postgresql+psycopg://cs2:cs2@localhost:5432/cs2"
    environment: str = "development"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    csfloat_api_key: SecretStr | None = None
    dmarket_public_key: SecretStr | None = None
    dmarket_secret_key: SecretStr | None = None
    sync_ttl_seconds: int = Field(default=300, ge=60, le=86400)
    stale_after_seconds: int = Field(default=3600, ge=60)
    max_listings: int = Field(default=500, ge=1, le=2000)
    history_retention_days: int = Field(default=30, ge=1, le=365)
    fx_usd_eur_rate: Decimal | None = Field(default=None, gt=0, allow_inf_nan=False)
    fx_rate_source: str | None = None
    fx_rate_timestamp: datetime | None = None
    fx_max_age_hours: int = Field(default=72, ge=1, le=720)

    @model_validator(mode="after")
    def validate_runtime(self) -> Self:
        if self.database_url.startswith("sqlite") and self.environment not in {
            "development",
            "test",
        }:
            raise ValueError("SQLite est réservé au développement et aux tests.")
        if self.fx_usd_eur_rate is not None:
            if not self.fx_rate_source or self.fx_rate_timestamp is None:
                raise ValueError("Un taux FX exige une source et une date explicites.")
            if self.fx_rate_timestamp.tzinfo is None:
                raise ValueError("La date FX doit inclure un fuseau horaire.")
        return self

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
