import type { Mode, Platform } from "./types";

export interface WatchFilters {
  market_hash_name: string;
  market: Platform | null;
  max_price_eur: string | null;
  max_float: string | null;
  paint_seeds: number[];
  doppler_phase: string | null;
}

export interface WatchRuleInput {
  name: string;
  enabled: boolean;
  filters: WatchFilters;
}

export interface WatchRule extends WatchRuleInput {
  id: string;
  mode: Mode;
  created_at: string;
  updated_at: string;
}

export interface WatchlistPage {
  mode: Mode;
  items: WatchRule[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export function parsePaintSeeds(text: string): number[] {
  if (!text.trim()) return [];
  const parts = text.split(",").map((part) => part.trim());
  if (parts.length > 100 || parts.some((part) => !/^\d{1,4}$/.test(part) || Number(part) > 1000)) {
    throw new Error("Indiquez au plus 100 seeds de 0 à 1000, séparés par des virgules.");
  }
  return [...new Set(parts.map(Number))].sort((a, b) => a - b);
}
