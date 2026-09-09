export type Mode = "live" | "demo";
export type Platform = "csfloat" | "skinport" | "dmarket";
export type LiquidityCategory = "VERY_LOW" | "LOW" | "MEDIUM" | "HIGH" | "VERY_HIGH";

export interface Sticker {
  name: string;
  slot: number | null;
  wear: string | null;
  steam_price: string | null;
  estimated_applied_value: string | null;
}

export interface ScannerRow {
  id: string;
  market_hash_name: string;
  weapon: string | null;
  skin: string | null;
  exterior: string | null;
  platform: Platform;
  price_original: string;
  currency_original: string;
  price_eur_reference: string | null;
  float_value: string | null;
  paint_seed: number | null;
  paint_index: number | null;
  doppler_phase: string | null;
  fade_percentage: string | null;
  inspect_link: string | null;
  listing_url: string | null;
  observed_at: string;
  estimated_value_eur: string | null;
  potential_profit_eur: string | null;
  roi: string | null;
  opportunity_score: number | null;
  float_score: number | null;
  liquidity: number | null;
  liquidity_category: LiquidityCategory | null;
  liquidity_evidence_completeness: number | null;
  confidence: number | null;
  reference_method: string | null;
  reference_sources: string[];
  reference_calculated_at: string | null;
  spread_eur: string | null;
  spread_percent: string | null;
  risk_score: number | null;
  risk_factors: string[];
  stickers: Sticker[];
  warnings: string[];
}

export interface MarketStatus {
  platform: Platform;
  integration_status: "OFFICIAL_API" | "SUPPORTED" | "PARTIAL" | "RESEARCH_REQUIRED" | "UNAVAILABLE";
  status: "online" | "not_configured" | "unavailable" | "error" | "stale" | "very_stale" | "demo" | "idle";
  message: string;
  freshness: "fresh" | "stale" | "very_stale" | "unknown";
  configured: boolean;
  last_sync_at: string | null;
  last_success_at: string | null;
  last_attempt_at: string | null;
  last_failure_at: string | null;
  last_duration_ms: number | null;
  last_items_received: number;
  last_items_created: number;
  last_items_updated: number;
  last_error: string | null;
  last_error_code: string | null;
  last_error_at: string | null;
  consecutive_failures: number;
  next_run_at: string | null;
}

export interface ExternalMarketHealth {
  status: MarketStatus["status"] | "unknown";
  last_attempt_at: string | null;
  last_success_at: string | null;
  last_error: string | null;
  last_error_at: string | null;
}

export interface SystemHealth {
  api: "healthy";
  database: "healthy" | "unavailable" | "unknown";
  markets: Record<Platform, ExternalMarketHealth>;
}

export interface DashboardData {
  mode: Mode;
  listings: ScannerRow[];
  markets: MarketStatus[];
  last_sync_at: string | null;
  warnings: string[];
}

export interface MarketMetrics {
  total_listings: number;
  active_listings: number;
  price_observations: number;
  aggregate_market_stats: number;
  realized_sales: number;
  buy_order_observations: number;
  active_opportunities: number;
  sync_errors_24h: number;
  average_freshness_seconds: number | null;
}

export interface MarketMonitorData {
  mode: "live";
  sync_enabled: boolean;
  sync_query_configured: boolean;
  scheduler_running: boolean;
  platforms: MarketStatus[];
  metrics: MarketMetrics;
  warnings: string[];
}

export interface MarketSourceInfo {
  id: string;
  name: string;
  source_type: "MARKETPLACE" | "TRADE" | "REFERENCE";
  access_status: "OFFICIAL_API" | "PUBLIC_API" | "REQUIRES_APPROVAL" | "RESEARCH_REQUIRED" | "UNAVAILABLE";
  auth_required: boolean;
  configured: boolean;
  runtime_status: string;
  capabilities: string[];
  official_url: string;
  documentation_url: string | null;
  note: string;
  verified_at: string;
}

export interface IntegrationCatalog {
  sources: MarketSourceInfo[];
  generated_at: string;
}

export interface FXReferenceRate {
  currency: string;
  currency_per_eur: string;
  eur_per_unit: string;
  source: string;
  observed_at: string;
  rate_type: "REFERENCE";
}

export interface FXStatus {
  sync_enabled: boolean;
  scheduler_running: boolean;
  runtime_status: string;
  last_attempt_at: string | null;
  last_success_at: string | null;
  last_error: string | null;
  next_run_at: string | null;
  rates: FXReferenceRate[];
}

export interface Comparison {
  platform: Platform;
  observation_type: string;
  lowest_eur: string | null;
  mean_eur: string | null;
  median_eur: string | null;
  median_gap_to_best_eur: string | null;
  median_gap_to_best_percent: string | null;
  sample_size: number;
}

export interface Observation {
  platform: Platform;
  observation_type: string;
  price: string;
  currency: string;
  timestamp: string;
  volume: number | null;
}

export interface CurrentMarketSnapshot {
  platform: Platform;
  ask_eur: string | null;
  bid_eur: string | null;
  median_7d_eur: string | null;
  median_30d_eur: string | null;
  volume_30d: number | null;
  currencies: string[];
  freshest_at: string | null;
  freshness: "fresh" | "stale" | "very_stale" | "unknown";
}

export interface ItemData {
  mode: Mode;
  item: ScannerRow;
  comparisons: Comparison[];
  market_snapshots: CurrentMarketSnapshot[];
  history: Observation[];
  warnings: string[];
}
