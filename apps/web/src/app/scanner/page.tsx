"use client";

import { useMemo, useState } from "react";
import { ListingsTable } from "@/components/listings-table";
import { useMarkets } from "@/components/market-provider";
import { DataPrinciple, EmptyState, LoadingState, PageHeading, SyncForm } from "@/components/shared";
import { Icon } from "@/components/icons";
import { emptyFilters, filterAndSort, type Filters, type Sort } from "@/lib/scanner";

function Input({ label, value, onChange, type = "text", placeholder }: { label: string; value: string; onChange: (value: string) => void; type?: string; placeholder?: string }) {
  return <label className="filter-field"><span>{label}</span><input type={type} value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} step="any" /></label>;
}

export default function ScannerPage() {
  const { data, loading } = useMarkets();
  const [filters, setFilters] = useState<Filters>(emptyFilters);
  const [sort, setSort] = useState<Sort>("opportunity");
  const rows = useMemo(() => data?.listings ?? [], [data?.listings]);
  const filtered = useMemo(() => filterAndSort(rows, filters, sort), [rows, filters, sort]);
  const weapons = [...new Set(rows.map((row) => row.weapon).filter(Boolean))] as string[];
  const exteriors = [...new Set(rows.map((row) => row.exterior).filter(Boolean))] as string[];
  const set = (key: keyof Filters, value: string) => setFilters((current) => ({ ...current, [key]: value }));

  return <>
    <PageHeading eyebrow="OPPORTUNITY SCANNER" title="Scanner les observations" description="Filtrez les exemplaires normalisés. Les valeurs inconnues restent inconnues et sont exclues des filtres numériques actifs." />
    <SyncForm />
    <section className="filter-panel">
      <div className="filter-title"><Icon name="filter" /><div><strong>Filtres d’analyse</strong><span>{filtered.length} résultat{filtered.length !== 1 ? "s" : ""} sur {rows.length}</span></div><button className="text-button" onClick={() => setFilters(emptyFilters)}>Réinitialiser</button></div>
      <div className="filter-grid">
        <label className="filter-field"><span>Marché</span><select value={filters.market} onChange={(event) => set("market", event.target.value)}><option value="">Tous</option><option value="csfloat">CSFloat</option><option value="skinport">Skinport</option><option value="dmarket">DMarket</option></select></label>
        <label className="filter-field"><span>Arme</span><select value={filters.weapon} onChange={(event) => set("weapon", event.target.value)}><option value="">Toutes</option>{weapons.map((weapon) => <option key={weapon}>{weapon}</option>)}</select></label>
        <Input label="Skin" value={filters.skin} onChange={(value) => set("skin", value)} placeholder="Nom partiel" />
        <label className="filter-field"><span>Exterior</span><select value={filters.exterior} onChange={(event) => set("exterior", event.target.value)}><option value="">Tous</option>{exteriors.map((exterior) => <option key={exterior}>{exterior}</option>)}</select></label>
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
    <section className="panel">
      <div className="panel-heading"><div><span className="eyebrow">RÉSULTATS NORMALISÉS</span><h2>Observations disponibles</h2></div><label className="sort-control"><span>Trier par</span><select value={sort} onChange={(event) => setSort(event.target.value as Sort)}><option value="opportunity">Meilleure opportunité</option><option value="profit">Profit le plus élevé</option><option value="roi">ROI le plus élevé</option><option value="risk">Risque le plus bas</option><option value="liquidity">Plus liquide</option><option value="confidence">Confiance la plus haute</option><option value="price">Prix le plus bas</option><option value="float">Float le plus bas</option><option value="spread">Spread le plus bas</option><option value="discount">Plus gros discount</option><option value="recent">Plus récent</option></select></label></div>
      {loading && !data ? <LoadingState /> : filtered.length ? <ListingsTable rows={filtered} /> : <EmptyState filtered={rows.length > 0} />}
    </section>
    <DataPrinciple />
  </>;
}
