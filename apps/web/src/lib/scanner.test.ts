import { describe, expect, it } from "vitest";
import { emptyFilters, filterAndSort } from "./scanner";
import type { ScannerRow } from "./types";

const base: ScannerRow = {
  id: "a", market_hash_name: "AK-47 | Redline (Field-Tested)", weapon: "AK-47",
  skin: "Redline", exterior: "Field-Tested", platform: "csfloat",
  price_original: "25", currency_original: "EUR", price_eur_reference: "25",
  float_value: "0.2", paint_seed: null, paint_index: null, doppler_phase: null,
  fade_percentage: null, inspect_link: null, listing_url: null,
  observed_at: "2026-01-01T00:00:00Z", estimated_value_eur: null,
  potential_profit_eur: null, roi: null, opportunity_score: null,
  float_score: null, liquidity: null, liquidity_category: null,
  liquidity_evidence_completeness: null, confidence: null, reference_method: null,
  reference_sources: [], reference_calculated_at: null, spread_eur: null,
  spread_percent: null, risk_score: null, risk_factors: [], stickers: [], warnings: [],
};

describe("filterAndSort", () => {
  it("exclut une valeur inconnue quand un filtre numérique est actif", () => {
    expect(filterAndSort([base], { ...emptyFilters, minProfit: "1" }, "profit")).toEqual([]);
  });

  it("trie les prix connus puis place les inconnus à la fin", () => {
    const cheap = { ...base, id: "cheap", price_eur_reference: "10" };
    const unknown = { ...base, id: "unknown", price_eur_reference: null };
    expect(filterAndSort([unknown, base, cheap], emptyFilters, "price").map((row) => row.id))
      .toEqual(["cheap", "a", "unknown"]);
  });

  it("filtre le risque et trie le discount calculé", () => {
    const strong = { ...base, id: "strong", estimated_value_eur: "40", risk_score: 20 };
    const weak = { ...base, id: "weak", estimated_value_eur: "30", risk_score: 70 };
    expect(filterAndSort([weak, strong], { ...emptyFilters, maxRisk: "50" }, "discount"))
      .toEqual([strong]);
  });
});
