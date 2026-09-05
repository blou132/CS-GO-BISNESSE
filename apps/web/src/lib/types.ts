export type Mode = "live" | "demo";
export type Platform = "csfloat" | "skinport" | "dmarket";

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
  confidence: number | null;
  stickers: Sticker[];
  warnings: string[];
}

export interface MarketStatus {
  platform: Platform;
  integration_status: "OFFICIAL_API" | "SUPPORTED" | "PARTIAL" | "RESEARCH_REQUIRED" | "UNAVAILABLE";
  status: "online" | "unavailable" | "error" | "stale" | "demo" | "idle";
  message: string;
  last_sync_at: string | null;
}

export interface DashboardData {
  mode: Mode;
  listings: ScannerRow[];
  markets: MarketStatus[];
  last_sync_at: string | null;
  warnings: string[];
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

export interface ItemData {
  mode: Mode;
  item: ScannerRow;
  comparisons: Comparison[];
  history: Observation[];
  warnings: string[];
}
