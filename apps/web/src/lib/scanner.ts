import { numeric } from "./format";
import type { ScannerRow } from "./types";

export interface Filters {
  market: string;
  weapon: string;
  skin: string;
  exterior: string;
  minPrice: string;
  maxPrice: string;
  minProfit: string;
  minRoi: string;
  maxFloat: string;
  minScore: string;
}

export type Sort = "opportunity" | "roi" | "profit" | "price" | "float" | "liquidity";
export const emptyFilters: Filters = { market: "", weapon: "", skin: "", exterior: "", minPrice: "", maxPrice: "", minProfit: "", minRoi: "", maxFloat: "", minScore: "" };

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
    matchesBound(row.price_eur_reference, filters.minPrice, true) &&
    matchesBound(row.price_eur_reference, filters.maxPrice, false) &&
    matchesBound(row.potential_profit_eur, filters.minProfit, true) &&
    matchesBound(row.roi, filters.minRoi, true) &&
    matchesBound(row.float_value, filters.maxFloat, false) &&
    matchesBound(row.opportunity_score, filters.minScore, true)
  );
  const field = { opportunity: "opportunity_score", roi: "roi", profit: "potential_profit_eur", price: "price_eur_reference", float: "float_value", liquidity: "liquidity" }[sort] as keyof ScannerRow;
  const ascending = sort === "price" || sort === "float";
  return filtered.sort((a, b) => {
    const left = numeric(a[field] as string | number | null);
    const right = numeric(b[field] as string | number | null);
    if (left === null) return right === null ? a.id.localeCompare(b.id) : 1;
    if (right === null) return -1;
    return (ascending ? left - right : right - left) || a.id.localeCompare(b.id);
  });
}
