"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Icon } from "@/components/icons";
import { ListingsTable } from "@/components/listings-table";
import { readJson, useMarkets } from "@/components/market-provider";
import {
  DataPrinciple,
  EmptyState,
  LoadingState,
  PageHeading,
  StatusBadge,
  SyncForm,
} from "@/components/shared";
import type { MarketMonitorData } from "@/lib/types";

function freshness(seconds: number | null | undefined) {
  if (seconds === null || seconds === undefined) return "—";
  if (seconds < 60) return `${seconds} s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)} min`;
  return `${(seconds / 3600).toLocaleString("fr-FR", { maximumFractionDigits: 1 })} h`;
}

export default function DashboardPage() {
  const { data, loading } = useMarkets();
  const [monitor, setMonitor] = useState<MarketMonitorData | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/market-monitor", { cache: "no-store", signal: controller.signal })
      .then(readJson<MarketMonitorData>)
      .then((value) => {
        if (!controller.signal.aborted) setMonitor(value);
      })
      .catch(() => undefined);
    return () => controller.abort();
  }, []);

  const rows = data?.listings ?? [];
  const available =
    data?.markets.filter((market) => ["online", "demo"].includes(market.status)).length ?? 0;
  const credentials = data?.markets.filter((market) => !market.configured).length ?? 0;
  const best = [...rows]
    .sort((a, b) => (b.opportunity_score ?? -1) - (a.opportunity_score ?? -1))
    .slice(0, 6);
  const metrics = monitor?.metrics;

  return (
    <>
      <PageHeading
        eyebrow="MARKET OVERVIEW"
        title="Tableau de bord"
        description="Surveillez les sources, la profondeur des données et les analyses qui méritent une vérification."
        action={
          <Link href="/scanner" className="button button-ghost">
            Ouvrir le scanner <Icon name="arrow" size={16} />
          </Link>
        }
      />
      <SyncForm />
      <section className="stat-grid stat-grid-six" aria-label="Indicateurs principaux">
        <article className="stat-card">
          <div className="stat-icon"><Icon name="layers" /></div>
          <span>Listings actifs</span>
          <strong>{loading && !data ? "…" : (metrics?.active_listings ?? rows.length).toLocaleString("fr-FR")}</strong>
          <small>{metrics?.total_listings.toLocaleString("fr-FR") ?? rows.length} conservés</small>
        </article>
        <article className="stat-card">
          <div className="stat-icon accent"><Icon name="target" /></div>
          <span>Ventes réalisées</span>
          <strong className="accent-text">{metrics?.realized_sales.toLocaleString("fr-FR") ?? "—"}</strong>
          <small>Transactions identifiables uniquement</small>
        </article>
        <article className="stat-card">
          <div className="stat-icon"><Icon name="activity" /></div>
          <span>Ordres d’achat</span>
          <strong>{metrics?.buy_order_observations.toLocaleString("fr-FR") ?? "—"}</strong>
          <small>Observations de demande persistées</small>
        </article>
        <article className="stat-card">
          <div className="stat-icon"><Icon name="markets" /></div>
          <span>Sources actives</span>
          <strong>{available}<em>/3</em></strong>
          <small>{credentials ? `${credentials} source(s) attendent des clés` : "Connecteurs configurés"}</small>
        </article>
        <article className="stat-card">
          <div className="stat-icon"><Icon name="clock" /></div>
          <span>Fraîcheur moyenne</span>
          <strong>{freshness(metrics?.average_freshness_seconds)}</strong>
          <small>Depuis les derniers succès marché</small>
        </article>
        <article className={`stat-card ${metrics?.sync_errors_24h ? "alert" : ""}`}>
          <div className="stat-icon"><Icon name="warning" /></div>
          <span>Scheduler</span>
          <strong>{monitor?.scheduler_running ? "Actif" : "Manuel"}</strong>
          <small>{metrics?.sync_errors_24h ?? 0} erreur(s) sur 24 h</small>
        </article>
      </section>
      <section className="panel">
        <div className="panel-heading">
          <div><span className="eyebrow">PRIORITÉ D’ANALYSE</span><h2>Meilleures observations</h2></div>
          <Link href="/scanner" className="text-link">Voir tous les filtres <Icon name="arrow" size={14} /></Link>
        </div>
        {loading && !data ? <LoadingState /> : best.length ? <ListingsTable rows={best} /> : <EmptyState />}
      </section>
      <section className="market-strip" aria-label="État des marchés">
        <div><span className="eyebrow">CONNECTEURS</span><h2>État des marchés</h2></div>
        {data?.markets.map((market) => (
          <article key={market.platform}>
            <span className={`market-letter ${market.platform}`}>{market.platform[0].toUpperCase()}</span>
            <div><strong>{market.platform === "csfloat" ? "CSFloat" : market.platform === "skinport" ? "Skinport" : "DMarket"}</strong><small>{market.integration_status.replaceAll("_", " ")}</small></div>
            <StatusBadge status={market.status} />
          </article>
        ))}
      </section>
      <DataPrinciple />
    </>
  );
}
