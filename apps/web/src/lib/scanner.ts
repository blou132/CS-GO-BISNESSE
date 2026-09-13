import { numeric } from "./format";
import type { ScannerRow } from "./types";

export interface Filters {
  market: string;
  weapon: string;
  skin: string;
  exterior: string;
  currency: string;
  patternType: string;
  minPrice: string;
  maxPrice: string;
  minProfit: string;
  minRoi: string;
  maxFloat: string;
  paintSeed: string;
  minScore: string;
  minLiquidity: string;
  minConfidence: string;
  maxRisk: string;
  maxSpread: string;
}

export type Sort = "opportunity" | "roi" | "profit" | "price" | "float" | "liquidity" | "risk" | "confidence" | "spread" | "discount" | "recent";
export const emptyFilters: Filters = { market: "", weapon: "", skin: "", exterior: "", currency: "", patternType: "", minPrice: "", maxPrice: "", minProfit: "", minRoi: "", maxFloat: "", paintSeed: "", minScore: "", minLiquidity: "", minConfidence: "", maxRisk: "", maxSpread: "" };

function matchesBound(value: string | number | null, bound: string, minimum: boolean): boolean {
  if (bound.trim() === "") return true;
  const threshold = numeric(bound);
  const number = numeric(value);
  if (threshold === null || number === null) return false;
  return minimum ? number >= threshold : number <= threshold;
}

export function filterAndSort(rows: ScannerRow[], filters: Filters, sort: Sort): ScannerRow[] {
  const filtered = rows.filter((row) =>
    (!filters.market || row.platform === filters.market) &&
    (!filters.weapon || row.weapon === filters.weapon) &&
    (!filters.skin || (row.skin ?? row.market_hash_name).toLocaleLowerCase("fr").includes(filters.skin.toLocaleLowerCase("fr"))) &&
    (!filters.exterior || row.exterior === filters.exterior) &&
    (!filters.currency || row.currency_original === filters.currency) &&
    (!filters.patternType || (filters.patternType === "doppler" ? row.doppler_phase !== null : filters.patternType === "fade" ? row.fade_percentage !== null : row.stickers.length > 0)) &&
    matchesBound(row.price_eur_reference, filters.minPrice, true) &&
    matchesBound(row.price_eur_reference, filters.maxPrice, false) &&
    matchesBound(row.potential_profit_eur, filters.minProfit, true) &&
    matchesBound(row.roi, filters.minRoi, true) &&
    matchesBound(row.float_value, filters.maxFloat, false) &&
    (!filters.paintSeed || row.paint_seed === Number(filters.paintSeed)) &&
    matchesBound(row.opportunity_score, filters.minScore, true) &&
    matchesBound(row.liquidity, filters.minLiquidity, true) &&
    matchesBound(row.confidence, filters.minConfidence, true) &&
    matchesBound(row.risk_score, filters.maxRisk, false) &&
    matchesBound(row.spread_percent, filters.maxSpread, false)
  );
  const fields: Partial<Record<Sort, keyof ScannerRow>> = { opportunity: "opportunity_score", roi: "roi", profit: "potential_profit_eur", price: "price_eur_reference", float: "float_value", liquidity: "liquidity", risk: "risk_score", confidence: "confidence", spread: "spread_percent" };
  const ascending = sort === "price" || sort === "float" || sort === "risk" || sort === "spread";
  return filtered.sort((a, b) => {
    const left = sortValue(a, sort, fields[sort]);
    const right = sortValue(b, sort, fields[sort]);
    if (left === null) return right === null ? a.id.localeCompare(b.id) : 1;
    if (right === null) return -1;
    return (ascending ? left - right : right - left) || a.id.localeCompare(b.id);
  });
}

function sortValue(row: ScannerRow, sort: Sort, field?: keyof ScannerRow): number | null {
  if (sort === "recent") {
    const value = Date.parse(row.observed_at);
    return Number.isFinite(value) ? value : null;
  }
  if (sort === "discount") {
    const price = numeric(row.price_eur_reference);
    const reference = numeric(row.estimated_value_eur);
    return price === null || reference === null ? null : reference - price;
  }
  return field ? numeric(row[field] as string | number | null) : null;
}
