from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

Mode = Literal["demo", "live"]
Platform = Literal["csfloat", "skinport", "dmarket"]
IntegrationStatus = Literal[
    "OFFICIAL_API", "SUPPORTED", "PARTIAL", "RESEARCH_REQUIRED", "UNAVAILABLE"
]
SourceType = Literal["MARKETPLACE", "TRADE", "REFERENCE", "AGGREGATOR"]
SourceAccessStatus = Literal[
    "OFFICIAL_API",
    "PUBLIC_API",
    "REQUIRES_APPROVAL",
    "RESEARCH_REQUIRED",
    "UNAVAILABLE",
]
MarketAvailability = Literal[
    "online",
    "degraded",
    "not_configured",
    "unavailable",
    "error",
    "stale",
    "very_stale",
    "demo",
    "idle",
]
HealthAvailability = Literal["healthy", "unavailable", "unknown"]
Freshness = Literal["fresh", "stale", "very_stale", "unknown"]
LiquidityCategory = Literal["VERY_LOW", "LOW", "MEDIUM", "HIGH", "VERY_HIGH"]
Money = Annotated[Decimal, Field(ge=0, allow_inf_nan=False, max_digits=20, decimal_places=8)]
FeeType = Literal["BUY", "SELL", "DEPOSIT", "WITHDRAW", "TRADE", "PAYMENT", "FX"]
ScannerSort = Literal[
    "opportunity",
    "roi",
    "profit",
    "price",
    "float",
    "liquidity",
    "risk",
    "confidence",
    "spread",
    "discount",
    "recent",
]


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
    liquidity_category: LiquidityCategory | None = None
    liquidity_evidence_completeness: int | None = None
    confidence: int | None = None
    reference_method: str | None = None
    reference_sources: list[str] = Field(default_factory=list)
    reference_calculated_at: datetime | None = None
    spread_eur: Decimal | None = None
    spread_percent: Decimal | None = None
    risk_score: int | None = None
    risk_factors: list[str] = Field(default_factory=list)
    stickers: list[Sticker] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class MarketStatus(BaseModel):
    platform: Platform
    integration_status: IntegrationStatus
    status: MarketAvailability
    message: str
    freshness: Freshness = "unknown"
    configured: bool = True
    last_sync_at: datetime | None = None
    last_success_at: datetime | None = None
    last_attempt_at: datetime | None = None
    last_failure_at: datetime | None = None
    last_duration_ms: int | None = None
    last_items_received: int = 0
    last_items_created: int = 0
    last_items_updated: int = 0
    last_error: str | None = None
    last_error_code: str | None = None
    last_error_at: datetime | None = None
    consecutive_failures: int = 0
    next_run_at: datetime | None = None


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


class ScannerFacets(BaseModel):
    markets: list[Platform]
    weapons: list[str]
    exteriors: list[str]
    currencies: list[str]


class ScannerPage(BaseModel):
    mode: Mode
    items: list[ScannerRow]
    total: int
    page: int
    page_size: int
    pages: int
    facets: ScannerFacets
    warnings: list[str] = Field(default_factory=list)


class MarketMetrics(BaseModel):
    total_listings: int
    active_listings: int
    price_observations: int
    aggregate_market_stats: int
    realized_sales: int
    buy_order_observations: int
    active_opportunities: int
    sync_errors_24h: int
    average_freshness_seconds: int | None = None


class RealtimeStatus(BaseModel):
    enabled: bool = False
    status: Literal[
        "disabled",
        "connecting",
        "connected",
        "online",
        "degraded",
        "disconnected",
        "stopped",
        "blocked",
    ] = "disabled"
    connected: bool = False
    connected_since: datetime | None = None
    last_attempt_at: datetime | None = None
    last_success_at: datetime | None = None
    last_event_at: datetime | None = None
    next_retry_at: datetime | None = None
    http_status: int | None = None
    events_received: int = 0
    events_per_minute: int = 0
    reconnect_count: int = 0
    queue_depth: int = 0
    dropped_events: int = 0
    invalid_events: int = 0
    filtered_events: int = 0
    duplicate_events: int = 0
    listings_updated: int = 0
    sales_received: int = 0
    errors: int = 0
    last_error: str | None = None
    last_batch_duration_ms: int | None = None


class MarketMonitor(BaseModel):
    mode: Mode = "live"
    sync_enabled: bool
    sync_query_configured: bool
    scheduler_running: bool
    platforms: list[MarketStatus]
    metrics: MarketMetrics
    warnings: list[str]
    realtime: dict[str, RealtimeStatus] = Field(default_factory=dict)


class MarketSourceInfo(BaseModel):
    id: str
    name: str
    source_type: SourceType
    access_status: SourceAccessStatus
    auth_required: bool | None
    roles: tuple[str, ...]
    api_discovery_status: Literal["API_FOUND", "PARTNER_API", "API_NOT_FOUND"]
    collected_capabilities: tuple[str, ...]
    configured: bool
    runtime_status: str
    capabilities: tuple[str, ...]
    official_url: str
    documentation_url: str | None
    note: str
    verified_at: str


class IntegrationCatalog(BaseModel):
    sources: list[MarketSourceInfo]
    generated_at: datetime


class FXReferenceRate(BaseModel):
    currency: str
    currency_per_eur: Decimal
    eur_per_unit: Decimal
    source: str
    observed_at: datetime
    rate_type: Literal["REFERENCE"] = "REFERENCE"


class FXStatus(BaseModel):
    sync_enabled: bool
    scheduler_running: bool
    runtime_status: str
    last_attempt_at: datetime | None = None
    last_success_at: datetime | None = None
    last_error: str | None = None
    next_run_at: datetime | None = None
    rates: list[FXReferenceRate] = Field(default_factory=list)


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


class CurrentMarketSnapshot(BaseModel):
    platform: Platform
    ask_eur: Decimal | None = None
    bid_eur: Decimal | None = None
    median_7d_eur: Decimal | None = None
    median_30d_eur: Decimal | None = None
    volume_30d: int | None = None
    currencies: list[str] = Field(default_factory=list)
    freshest_at: datetime | None = None
    freshness: Freshness = "unknown"


class EvidenceSource(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    platform: str
    kind: str
    value_eur: Decimal | None
    observed_at: datetime
    volume: int | None = None
    window: str | None = None
    record_id: str | None = None
    external_id: str | None = None
    price_original: Decimal | None = None
    currency: str | None = None
    fx_source: str | None = None
    fx_timestamp: datetime | None = None
    timestamp_basis: str | None = None


class ValuationProvenance(BaseModel):
    buy: EvidenceSource
    reference: list[EvidenceSource]
    reference_sample_size: int
    comparable_count: int
    float_min_samples: int
    float_status: Literal["AVAILABLE", "INSUFFICIENT_DATA"]
    fee_status: Literal["UNKNOWN", "DEMO_SYNTHETIC"]
    effective_fx_status: Literal["UNKNOWN"] = "UNKNOWN"
    eligibility: Literal["REFERENCE_ONLY", "DEMO"]


class ItemDetail(BaseModel):
    mode: Mode
    item: ScannerRow
    comparisons: list[Comparison]
    market_snapshots: list[CurrentMarketSnapshot] = Field(default_factory=list)
    history: list[Observation]
    provenance: ValuationProvenance | None = None
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


class PurchaseCostRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    item_price_eur: Money
    purchase_fee_eur: Money = Decimal(0)
    payment_fee_eur: Money = Decimal(0)
    fx_fee_eur: Money = Decimal(0)
    deposit_fee_eur: Money = Decimal(0)
    trade_fee_eur: Money = Decimal(0)


class SaleRevenueRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    estimated_sale_price_eur: Money
    sale_fee_eur: Money = Decimal(0)
    withdrawal_fee_eur: Money = Decimal(0)
    fx_fee_eur: Money = Decimal(0)
    trade_fee_eur: Money = Decimal(0)


class NetProfitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    purchase: PurchaseCostRequest
    sale: SaleRevenueRequest
    estimated_holding_days: int | None = Field(default=None, ge=0)


class PurchaseCostResponse(PurchaseCostRequest):
    total_cost_eur: Decimal


class SaleRevenueResponse(SaleRevenueRequest):
    net_revenue_eur: Decimal


class NetProfitResponse(BaseModel):
    purchase: PurchaseCostResponse
    sale: SaleRevenueResponse
    net_profit_eur: Decimal
    roi_percent: Decimal | None
    roi_per_day_percent: Decimal | None
    warning: str = (
        "Simulation EUR : les montants fournis doivent provenir de taux et frais vérifiés."
    )


class FeeQuoteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    platform: str = Field(min_length=1, max_length=32)
    fee_type: FeeType
    base_amount: Money
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    item_name: str | None = Field(default=None, max_length=512)


class FeeQuoteResponse(BaseModel):
    known: bool
    platform: str
    fee_type: FeeType
    base_amount: Decimal
    fee_amount: Decimal | None = None
    currency: str
    rate: Decimal | None = None
    fixed_amount: Decimal | None = None
    minimum_fee: Decimal | None = None
    minimum_applied: bool = False
    applies_to: str | None = None
    source: str | None = None
    verified_at: datetime | None = None
    warning: str | None = None
