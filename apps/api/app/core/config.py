from datetime import UTC, datetime, timedelta
from decimal import Decimal
from functools import lru_cache
from typing import Literal, Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../../.env", ".env"),
        env_ignore_empty=True,
        extra="ignore",
    )

    database_url: str = "postgresql+psycopg://cs2:cs2@localhost:5432/cs2"
    environment: Literal["development", "test", "production"] = "development"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    csfloat_api_key: SecretStr | None = None
    dmarket_public_key: SecretStr | None = None
    dmarket_secret_key: SecretStr | None = None
    sync_ttl_seconds: int = Field(default=300, ge=60, le=86400)
    stale_after_seconds: int = Field(default=3600, ge=60)
    very_stale_after_seconds: int = Field(default=86400, ge=300)
    price_observation_min_interval_seconds: int = Field(default=3600, ge=60, le=86400)
    market_sync_enabled: bool = False
    market_sync_query: str = Field(default="", max_length=512)
    csfloat_sync_interval_seconds: int = Field(default=900, ge=60)
    skinport_sync_interval_seconds: int = Field(default=900, ge=300)
    dmarket_sync_interval_seconds: int = Field(default=900, ge=60)
    skinport_realtime_enabled: bool = False
    skinport_realtime_blocked_at: datetime | None = None
    skinport_realtime_queue_size: int = Field(default=256, ge=1, le=5000)
    skinport_realtime_price_unit: Literal["unverified", "minor", "major"] = "unverified"
    skinport_realtime_price_unit_source: str = Field(default="", max_length=2048)
    skinport_realtime_stale_seconds: int = Field(default=300, ge=60, le=3600)
    float_min_samples: int = Field(default=5, ge=5, le=1000)
    max_listings: int = Field(default=500, ge=1, le=2000)
    history_retention_days: int = Field(default=30, ge=1, le=365)
    fx_usd_eur_rate: Decimal | None = Field(default=None, gt=0, allow_inf_nan=False)
    fx_rate_source: str | None = None
    fx_rate_timestamp: datetime | None = None
    fx_max_age_hours: int = Field(default=120, ge=1, le=720)
    fx_reference_sync_enabled: bool = False
    fx_reference_sync_interval_seconds: int = Field(default=21600, ge=3600, le=86400)

    @model_validator(mode="after")
    def validate_runtime(self) -> Self:
        if self.skinport_realtime_blocked_at:
            if self.skinport_realtime_enabled:
                raise ValueError("Clear the documented access block before enabling realtime")
            if (
                self.skinport_realtime_blocked_at.tzinfo is None
                or self.skinport_realtime_blocked_at > datetime.now(UTC) + timedelta(minutes=5)
            ):
                raise ValueError("The access block requires a non-future timestamp with timezone")
        if self.database_url.startswith("sqlite") and self.environment not in {
            "development",
            "test",
        }:
            raise ValueError("SQLite est réservé au développement et aux tests.")
        if self.environment == "production":
            if not self.database_url.startswith("postgresql+psycopg://"):
                raise ValueError("La production exige PostgreSQL avec le pilote psycopg.")
            if "replace-with-local-password" in self.database_url:
                raise ValueError("Le mot de passe PostgreSQL d'exemple doit être remplacé.")
            if not self.allowed_origins or "*" in self.allowed_origins:
                raise ValueError("La production exige une liste CORS explicite sans wildcard.")
        if self.very_stale_after_seconds < self.stale_after_seconds:
            raise ValueError("VERY_STALE_AFTER_SECONDS doit être supérieur à STALE_AFTER_SECONDS.")
        if self.market_sync_query and any(ord(char) < 32 for char in self.market_sync_query):
            raise ValueError("MARKET_SYNC_QUERY contient un caractère de contrôle.")
        if (self.market_sync_enabled or self.skinport_realtime_enabled) and len(
            self.market_sync_query.strip()
        ) < 3:
            raise ValueError(
                "MARKET_SYNC_QUERY doit contenir au moins 3 caractères "
                "quand MARKET_SYNC_ENABLED=true."
            )
        if (
            self.skinport_realtime_price_unit != "unverified"
            and not self.skinport_realtime_price_unit_source.startswith("https://")
        ):
            raise ValueError("Une unite de prix feed exige une source HTTPS verifiee.")
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
