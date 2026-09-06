from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

Mode = Literal["demo", "live"]
Platform = Literal["csfloat", "skinport", "dmarket"]
IntegrationStatus = Literal[
    "OFFICIAL_API", "SUPPORTED", "PARTIAL", "RESEARCH_REQUIRED", "UNAVAILABLE"
]
MarketAvailability = Literal["online", "unavailable", "error", "stale", "demo", "idle"]
HealthAvailability = Literal["healthy", "unavailable", "unknown"]
Money = Annotated[Decimal, Field(ge=0, allow_inf_nan=False, max_digits=20, decimal_places=8)]


class Sticker(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: str
    slot: int | None = None
    wear: Decimal | None = None
    steam_price: Decimal | None = None
    estimated_applied_value: Decimal | None = None


class ScannerRow(BaseModel):
    id: str
    market_hash_name: str
    weapon: str | None
    skin: str | None
    exterior: str | None
    platform: Platform
    price_original: Decimal
    currency_original: str
    price_eur_reference: Decimal | None
    float_value: Decimal | None
    paint_seed: int | None
    paint_index: int | None
    doppler_phase: str | None
    fade_percentage: Decimal | None
    inspect_link: str | None
    listing_url: str | None
    observed_at: datetime
    estimated_value_eur: Decimal | None = None
    potential_profit_eur: Decimal | None = None
    roi: Decimal | None = None
    opportunity_score: int | None = None
    float_score: int | None = None
    liquidity: int | None = None
    confidence: int | None = None
    stickers: list[Sticker] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class MarketStatus(BaseModel):
    platform: Platform
    integration_status: IntegrationStatus
    status: MarketAvailability
    message: str
    last_sync_at: datetime | None = None
    last_attempt_at: datetime | None = None
    last_error: str | None = None
    last_error_at: datetime | None = None


class ExternalMarketHealth(BaseModel):
    status: MarketAvailability | Literal["unknown"]
    last_attempt_at: datetime | None = None
    last_success_at: datetime | None = None
    last_error: str | None = None
    last_error_at: datetime | None = None


class SystemHealth(BaseModel):
    api: Literal["healthy"] = "healthy"
    database: HealthAvailability
    markets: dict[Platform, ExternalMarketHealth]


class Dashboard(BaseModel):
    mode: Mode
    listings: list[ScannerRow]
    markets: list[MarketStatus]
    last_sync_at: datetime | None
    warnings: list[str]


class Comparison(BaseModel):
    platform: Platform
    observation_type: str
    lowest_eur: Decimal | None
    mean_eur: Decimal | None
    median_eur: Decimal | None
    median_gap_to_best_eur: Decimal | None
    median_gap_to_best_percent: Decimal | None
    sample_size: int


class Observation(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    platform: Platform
    observation_type: str
    price: Decimal
    currency: str
    timestamp: datetime
    volume: int | None


class ItemDetail(BaseModel):
    mode: Mode
    item: ScannerRow
    comparisons: list[Comparison]
    history: list[Observation]
    warnings: list[str]


class ProfitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    purchase_price: Money
    sale_price: Money
    purchase_fee: Money = Decimal(0)
    payment_fee: Money = Decimal(0)
    fx_fee: Money = Decimal(0)
    trade_fee: Money = Decimal(0)
    sale_fee: Money = Decimal(0)
    withdrawal_fee: Money = Decimal(0)


class ProfitResponse(BaseModel):
    total_cost: Decimal
    net_revenue: Decimal
    net_profit: Decimal
    roi: Decimal | None
    warning: str = "Simulation EUR basée uniquement sur les montants de frais fournis."
