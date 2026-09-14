"""Read-only marketplace contract. No persistence or transaction side effects."""

from abc import ABC, abstractmethod
from collections.abc import Awaitable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, JsonValue, model_validator


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
    steam_volume: int | None = Field(default=None, ge=0)
    estimated_applied_value: Money | None = None


class AdapterItem(AdapterDTO):
    market_hash_name: str = Field(min_length=1, max_length=512)
    asset_id: str | None = Field(default=None, max_length=256)
    def_index: int | None = Field(default=None, ge=0)
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
    rarity: str | None = Field(default=None, max_length=128)
    quality: str | None = Field(default=None, max_length=128)
    collection: str | None = Field(default=None, max_length=256)
    scm_price: Money | None = None
    scm_volume: int | None = Field(default=None, ge=0)
    source_attributes: dict[str, JsonValue] = Field(default_factory=dict)
    inspect_link: str | None = None
    tradable: bool | None = None
    tradable_at: UtcDatetime | None = None
    stickers: list[AdapterSticker] = Field(default_factory=list)


class AdapterListing(AdapterDTO):
    external_id: str = Field(min_length=1, max_length=200)
    item: AdapterItem
    price: Money
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    listing_url: str | None = None
    seller_type: str | None = Field(default=None, max_length=64)
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


MarketWindow = Literal["24H", "7D", "30D", "90D"]


class AdapterAggregateStat(AdapterDTO):
    market_hash_name: str = Field(min_length=1, max_length=512)
    window: MarketWindow
    min_price: Money | None = None
    max_price: Money | None = None
    avg_price: Money | None = None
    median_price: Money | None = None
    volume: int | None = Field(default=None, ge=0)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    observed_at: UtcDatetime

    @model_validator(mode="after")
    def require_statistic(self) -> "AdapterAggregateStat":
        if all(
            value is None
            for value in (
                self.min_price,
                self.max_price,
                self.avg_price,
                self.median_price,
                self.volume,
            )
        ):
            raise ValueError("An aggregate statistic requires at least one value")
        return self


class AdapterRealizedSale(AdapterDTO):
    external_id: str | None = Field(default=None, min_length=1, max_length=256)
    market_hash_name: str = Field(min_length=1, max_length=512)
    item: AdapterItem | None = None
    price: Money
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    sold_at: UtcDatetime
    observed_at: UtcDatetime
    transaction_type: str | None = Field(default=None, max_length=64)
    attributes: dict[str, JsonValue] = Field(default_factory=dict)


class AdapterBuyOrder(AdapterDTO):
    market_hash_name: str = Field(min_length=1, max_length=512)
    price: Money
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    quantity: int = Field(ge=0)
    observed_at: UtcDatetime
    attributes: dict[str, JsonValue] = Field(default_factory=dict)


class AdapterFeeSchedule(AdapterDTO):
    platform: str = Field(min_length=1, max_length=32)
    fee_type: Literal["BUY", "SELL", "DEPOSIT", "WITHDRAW", "TRADE", "PAYMENT", "FX"]
    rate: Decimal | None = Field(default=None, ge=0, le=1)
    fixed_amount: Money | None = None
    minimum_fee: Money | None = None
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    min_amount: Money | None = None
    max_amount: Money | None = None
    applies_to: str | None = Field(default=None, max_length=256)
    source: str = Field(min_length=1, max_length=2048)
    verified_at: UtcDatetime
    valid_from: UtcDatetime
    valid_until: UtcDatetime | None = None
    details: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def require_fee_value(self) -> "AdapterFeeSchedule":
        if self.rate is None and self.fixed_amount is None:
            raise ValueError("A fee requires a rate or a fixed amount")
        return self


class AdapterResult(AdapterDTO):
    listings: list[AdapterListing] = Field(default_factory=list)
    observations: list[AdapterObservation] = Field(default_factory=list)
    aggregates: list[AdapterAggregateStat] = Field(default_factory=list)
    realized_sales: list[AdapterRealizedSale] = Field(default_factory=list)
    buy_orders: list[AdapterBuyOrder] = Field(default_factory=list)
    fee_schedules: list[AdapterFeeSchedule] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    partial_errors: dict[str, str] = Field(default_factory=dict)


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


async def optional_enrichment[T](
    result: AdapterResult, capability: str, request: Awaitable[list[T]]
) -> list[T]:
    try:
        return await request
    except (MarketAdapterError, ValueError, KeyError, TypeError) as error:
        code = error.code if isinstance(error, MarketAdapterError) else "invalid_response"
        result.partial_errors[capability] = code
        result.warnings.append(f"Enrichissement {capability} indisponible ({code}).")
        return []


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
