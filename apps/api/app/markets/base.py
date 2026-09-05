"""Read-only marketplace contract. No persistence or transaction side effects."""

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field


def utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("A timezone-aware timestamp is required")
    return value.astimezone(UTC)


UtcDatetime = Annotated[datetime, AfterValidator(utc_datetime)]
Money = Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]


class AdapterDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AdapterSticker(AdapterDTO):
    name: str = Field(min_length=1, max_length=512)
    slot: int | None = Field(default=None, ge=0)
    wear: Decimal | None = Field(default=None, ge=0, le=1)
    steam_price: Money | None = None
    estimated_applied_value: Money | None = None


class AdapterItem(AdapterDTO):
    market_hash_name: str = Field(min_length=1, max_length=512)
    weapon: str | None = None
    skin: str | None = None
    exterior: str | None = None
    stattrak: bool | None = None
    souvenir: bool | None = None
    float_value: Decimal | None = Field(default=None, ge=0, le=1)
    paint_index: int | None = Field(default=None, ge=0)
    paint_seed: int | None = Field(default=None, ge=0)
    doppler_phase: str | None = None
    fade_percentage: Decimal | None = Field(default=None, ge=0, le=100)
    inspect_link: str | None = None
    stickers: list[AdapterSticker] = Field(default_factory=list)


class AdapterListing(AdapterDTO):
    external_id: str = Field(min_length=1, max_length=200)
    item: AdapterItem
    price: Money
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    listing_url: str | None = None
    observed_at: UtcDatetime
    listed_at: UtcDatetime | None = None
    warnings: list[str] = Field(default_factory=list)


class AdapterObservation(AdapterDTO):
    market_hash_name: str = Field(min_length=1, max_length=512)
    price: Money
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    observation_type: Literal["LISTING", "SALE", "AGGREGATE"]
    timestamp: UtcDatetime
    volume: int | None = Field(default=None, ge=0)


class AdapterResult(AdapterDTO):
    listings: list[AdapterListing] = Field(default_factory=list)
    observations: list[AdapterObservation] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class MarketAdapterError(Exception):
    """Safe message/code for callers; upstream response bodies are never exposed."""

    def __init__(self, code: str, message: str, retry_after_seconds: float | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retry_after_seconds = retry_after_seconds


class ConfigurationError(MarketAdapterError):
    def __init__(self, message: str) -> None:
        super().__init__("configuration", message)


class UnsupportedCapabilityError(MarketAdapterError):
    def __init__(self, message: str) -> None:
        super().__init__("unsupported_capability", message)


class MarketAdapter(ABC):
    market: str

    @abstractmethod
    async def search_items(self, query: str) -> AdapterResult: ...

    @abstractmethod
    async def get_listing(self, external_id: str) -> AdapterListing: ...

    @abstractmethod
    async def get_market_stats(self, query: str) -> list[AdapterObservation]: ...

    @abstractmethod
    async def aclose(self) -> None: ...
