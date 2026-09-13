"use client";

import { useEffect, useMemo, useState } from "react";
import { Icon } from "@/components/icons";
import { ListingsTable } from "@/components/listings-table";
import { readJson, useMarkets } from "@/components/market-provider";
import { DataPrinciple, EmptyState, LoadingState, PageHeading, SyncForm } from "@/components/shared";
import { emptyFilters, type Filters, type Sort } from "@/lib/scanner";
import type { ScannerPageData } from "@/lib/types";

const queryNames: Record<keyof Filters, string> = {
  market: "market",
  weapon: "weapon",
  skin: "skin",
  exterior: "exterior",
  currency: "currency",
  patternType: "pattern_type",
  minPrice: "min_price",
  maxPrice: "max_price",
  minProfit: "min_profit",
  minRoi: "min_roi",
  maxFloat: "max_float",
  paintSeed: "paint_seed",
  minScore: "min_score",
  minLiquidity: "min_liquidity",
  minConfidence: "min_confidence",
  maxRisk: "max_risk",
  maxSpread: "max_spread",
};

function Input({ label, value, onChange, type = "text", placeholder }: { label: string; value: string; onChange: (value: string) => void; type?: string; placeholder?: string }) {
  return <label className="filter-field"><span>{label}</span><input type={type} value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} step="any" /></label>;
}

export default function ScannerPage() {
  const { mode, data } = useMarkets();
  const [filters, setFilters] = useState<Filters>(emptyFilters);
  const [sort, setSort] = useState<Sort>("opportunity");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const queryString = useMemo(() => {
    const params = new URLSearchParams({ mode, page: String(page), page_size: String(pageSize), sort });
    for (const [key, value] of Object.entries(filters) as [keyof Filters, string][]) {
      if (value.trim()) params.set(queryNames[key], value.trim());
    }
    return params.toString();
  }, [filters, mode, page, pageSize, sort]);
  const requestKey = `${queryString}|${data?.last_sync_at ?? ""}`;
  const [response, setResponse] = useState<{ key: string; result: ScannerPageData | null; error: string | null } | null>(null);
  const loading = response?.key !== requestKey;
  const error = response?.key === requestKey ? response.error : null;

  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      fetch(`/api/scanner?${queryString}`, { cache: "no-store", signal: controller.signal })
        .then(readJson<ScannerPageData>)
        .then((value) => {
          if (controller.signal.aborted) return;
          if (value.pages > 0 && value.page > value.pages) {
            setPage(value.pages);
            return;
          }
          setResponse({ key: requestKey, result: value, error: null });
        })
        .catch((reason: unknown) => {
          if (!controller.signal.aborted) {
            setResponse({
              key: requestKey,
              result: null,
              error: reason instanceof Error ? reason.message : "Erreur inattendue.",
            });
          }
        });
    }, 250);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [queryString, requestKey]);

  const set = (key: keyof Filters, value: string) => {
    setPage(1);
    setFilters((current) => ({ ...current, [key]: value }));
  };
  const reset = () => {
    setPage(1);
    setFilters(emptyFilters);
  };
  const currentResult = response?.key === requestKey && response.result?.mode === mode ? response.result : null;
  const facets = currentResult?.facets;
  const rows = currentResult?.items ?? [];

  return <>
    <PageHeading eyebrow="OPPORTUNITY SCANNER" title="Scanner les observations" description="Filtrez les exemplaires normalisés. Les valeurs inconnues restent inconnues et sont exclues des filtres numériques actifs." />
    <SyncForm />
    <section className="filter-panel">
      <div className="filter-title"><Icon name="filter" /><div><strong>Filtres d’analyse</strong><span>{loading ? "—" : currentResult?.total.toLocaleString("fr-FR") ?? "—"} résultat{currentResult?.total === 1 ? "" : "s"}</span></div><button className="text-button" onClick={reset}>Réinitialiser</button></div>
      <div className="filter-grid">
        <label className="filter-field"><span>Marché</span><select value={filters.market} onChange={(event) => set("market", event.target.value)}><option value="">Tous</option>{facets?.markets.map((market) => <option key={market} value={market}>{market === "csfloat" ? "CSFloat" : market === "skinport" ? "Skinport" : "DMarket"}</option>)}</select></label>
        <label className="filter-field"><span>Arme</span><select value={filters.weapon} onChange={(event) => set("weapon", event.target.value)}><option value="">Toutes</option>{facets?.weapons.map((weapon) => <option key={weapon}>{weapon}</option>)}</select></label>
        <Input label="Skin" value={filters.skin} onChange={(value) => set("skin", value)} placeholder="Nom partiel" />
        <label className="filter-field"><span>Exterior</span><select value={filters.exterior} onChange={(event) => set("exterior", event.target.value)}><option value="">Tous</option>{facets?.exteriors.map((exterior) => <option key={exterior}>{exterior}</option>)}</select></label>
        <label className="filter-field"><span>Devise</span><select value={filters.currency} onChange={(event) => set("currency", event.target.value)}><option value="">Toutes</option>{facets?.currencies.map((currency) => <option key={currency}>{currency}</option>)}</select></label>
        <label className="filter-field"><span>Motif</span><select value={filters.patternType} onChange={(event) => set("patternType", event.target.value)}><option value="">Tous</option><option value="doppler">Doppler</option><option value="fade">Fade</option><option value="sticker">Avec stickers</option></select></label>
        <Input label="Prix min. EUR" type="number" value={filters.minPrice} onChange={(value) => set("minPrice", value)} />
        <Input label="Prix max. EUR" type="number" value={filters.maxPrice} onChange={(value) => set("maxPrice", value)} />
        <Input label="Profit min. EUR" type="number" value={filters.minProfit} onChange={(value) => set("minProfit", value)} />
        <Input label="ROI min. %" type="number" value={filters.minRoi} onChange={(value) => set("minRoi", value)} />
        <Input label="Float max." type="number" value={filters.maxFloat} onChange={(value) => set("maxFloat", value)} />
        <Input label="Paint seed" type="number" value={filters.paintSeed} onChange={(value) => set("paintSeed", value)} />
        <Input label="Score min." type="number" value={filters.minScore} onChange={(value) => set("minScore", value)} />
        <Input label="Liquidité min." type="number" value={filters.minLiquidity} onChange={(value) => set("minLiquidity", value)} />
        <Input label="Confiance min." type="number" value={filters.minConfidence} onChange={(value) => set("minConfidence", value)} />
        <Input label="Risque max." type="number" value={filters.maxRisk} onChange={(value) => set("maxRisk", value)} />
        <Input label="Spread max. %" type="number" value={filters.maxSpread} onChange={(value) => set("maxSpread", value)} />
      </div>
    </section>
    {error ? <div className="notice error-notice" role="alert"><strong>Scanner indisponible.</strong> {error}</div> : null}
    {!loading && currentResult?.warnings.length ? <div className="market-limit"><strong>Analyse partielle</strong><p>{currentResult.warnings.join(" ")}</p></div> : null}
    <section className="panel">
      <div className="panel-heading"><div><span className="eyebrow">RÉSULTATS NORMALISÉS</span><h2>Observations disponibles</h2></div><div className="results-controls"><label className="sort-control"><span>Trier par</span><select value={sort} onChange={(event) => { setPage(1); setSort(event.target.value as Sort); }}><option value="opportunity">Meilleure opportunité</option><option value="profit">Profit le plus élevé</option><option value="roi">ROI le plus élevé</option><option value="risk">Risque le plus bas</option><option value="liquidity">Plus liquide</option><option value="confidence">Confiance la plus haute</option><option value="price">Prix le plus bas</option><option value="float">Float le plus bas</option><option value="spread">Spread le plus bas</option><option value="discount">Plus gros discount</option><option value="recent">Plus récent</option></select></label><label className="sort-control page-size-control"><span>Par page</span><select value={pageSize} onChange={(event) => { setPage(1); setPageSize(Number(event.target.value)); }}><option value={25}>25</option><option value={50}>50</option><option value={100}>100</option></select></label></div></div>
      {loading ? <LoadingState /> : rows.length ? <ListingsTable rows={rows} /> : <EmptyState filtered={Boolean(Object.values(filters).some(Boolean))} />}
      {!loading && currentResult && currentResult.pages > 1 ? <nav className="pagination" aria-label="Pagination du scanner"><button className="icon-button" title="Page précédente" aria-label="Page précédente" disabled={page <= 1} onClick={() => setPage((current) => Math.max(1, current - 1))}><Icon name="back" size={15} /></button><span>Page <strong>{currentResult.page}</strong> sur <strong>{currentResult.pages}</strong></span><button className="icon-button" title="Page suivante" aria-label="Page suivante" disabled={page >= currentResult.pages} onClick={() => setPage((current) => current + 1)}><Icon name="arrow" size={15} /></button></nav> : null}
    </section>
    <DataPrinciple />
  </>;
}
