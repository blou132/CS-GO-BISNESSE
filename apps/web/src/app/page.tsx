"use client";

import Link from "next/link";
import { ListingsTable } from "@/components/listings-table";
import { useMarkets } from "@/components/market-provider";
import { DataPrinciple, EmptyState, LoadingState, PageHeading, StatusBadge, SyncForm } from "@/components/shared";
import { Icon } from "@/components/icons";
import { numeric } from "@/lib/format";

export default function DashboardPage() {
  const { data, loading } = useMarkets();
  const rows = data?.listings ?? [];
  const opportunities = rows.filter((row) => (numeric(row.potential_profit_eur) ?? 0) > 0).length;
  const available = data?.markets.filter((market) => ["online", "demo"].includes(market.status)).length ?? 0;
  const errors = data?.markets.filter((market) => ["error", "unavailable"].includes(market.status)).length ?? 0;
  const best = [...rows].sort((a, b) => (b.opportunity_score ?? -1) - (a.opportunity_score ?? -1)).slice(0, 6);

  return <>
    <PageHeading eyebrow="MARKET OVERVIEW" title="Tableau de bord" description="Surveillez les sources, la qualité des données et les écarts qui méritent une analyse." action={<Link href="/scanner" className="button button-ghost">Ouvrir le scanner <Icon name="arrow" size={16} /></Link>} />
    <SyncForm />
    <section className="stat-grid" aria-label="Indicateurs principaux">
      <article className="stat-card"><div className="stat-icon"><Icon name="layers" /></div><span>Listings observés</span><strong>{loading && !data ? "…" : rows.length.toLocaleString("fr-FR")}</strong><small>Annonces individuelles conservées</small></article>
      <article className="stat-card"><div className="stat-icon accent"><Icon name="target" /></div><span>Opportunités calculables</span><strong className="accent-text">{loading && !data ? "…" : opportunities}</strong><small>Profit positif après hypothèses disponibles</small></article>
      <article className="stat-card"><div className="stat-icon"><Icon name="activity" /></div><span>Plateformes disponibles</span><strong>{available}<em>/3</em></strong><small>État de la dernière synchronisation</small></article>
      <article className={`stat-card ${errors ? "alert" : ""}`}><div className="stat-icon"><Icon name="warning" /></div><span>Plateformes en erreur</span><strong>{errors}</strong><small>{errors ? "Consultez le détail des marchés" : "Aucune erreur enregistrée"}</small></article>
    </section>
    <section className="panel">
      <div className="panel-heading"><div><span className="eyebrow">PRIORITÉ D’ANALYSE</span><h2>Meilleures observations</h2></div><Link href="/scanner" className="text-link">Voir tous les filtres <Icon name="arrow" size={14} /></Link></div>
      {loading && !data ? <LoadingState /> : best.length ? <ListingsTable rows={best} /> : <EmptyState />}
    </section>
    <section className="market-strip" aria-label="État des marchés">
      <div><span className="eyebrow">CONNECTEURS</span><h2>État des marchés</h2></div>
      {data?.markets.map((market) => <article key={market.platform}><span className={`market-letter ${market.platform}`}>{market.platform[0].toUpperCase()}</span><div><strong>{market.platform === "csfloat" ? "CSFloat" : market.platform === "skinport" ? "Skinport" : "DMarket"}</strong><small>{market.integration_status.replaceAll("_", " ")}</small></div><StatusBadge status={market.status} /></article>)}
    </section>
    <DataPrinciple />
  </>;
}
