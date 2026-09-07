"use client";

import { useEffect, useState } from "react";
import { readJson } from "@/components/market-provider";
import { DataPrinciple, LoadingState, PageHeading, StatusBadge } from "@/components/shared";
import { dateTime, marketNames } from "@/lib/format";
import { marketOperationalLabel, monitorSummary } from "@/lib/monitor";
import type { MarketMonitorData, SystemHealth } from "@/lib/types";

export default function MarketsPage() {
  const [monitor, setMonitor] = useState<MarketMonitorData | null>(null);
  const [loading, setLoading] = useState(true);
  const [system, setSystem] = useState<SystemHealth | null>(null);
  const [systemUnavailable, setSystemUnavailable] = useState(false);
  const [monitorUnavailable, setMonitorUnavailable] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/health", { cache: "no-store", signal: controller.signal })
      .then(readJson<SystemHealth>)
      .then((value) => { if (!controller.signal.aborted) setSystem(value); })
      .catch(() => { if (!controller.signal.aborted) setSystemUnavailable(true); });
    fetch("/api/market-monitor", { cache: "no-store", signal: controller.signal })
      .then(readJson<MarketMonitorData>)
      .then((value) => { if (!controller.signal.aborted) setMonitor(value); })
      .catch(() => { if (!controller.signal.aborted) setMonitorUnavailable(true); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, []);
  const summary = monitorSummary(monitor);
  return <>
    <PageHeading eyebrow="MARKET MONITOR" title="Marchés" description="État opérationnel des collectes périodiques et des données persistées." />
    <section className="system-status-grid" aria-label="État des services internes">
      <article><span>API</span><strong className={system ? "health-ok" : systemUnavailable ? "health-error" : ""}>{system ? "Opérationnelle" : systemUnavailable ? "Indisponible" : "Vérification…"}</strong><small>Processus applicatif</small></article>
      <article><span>Base de données</span><strong className={system?.database === "healthy" ? "health-ok" : system?.database === "unavailable" || systemUnavailable ? "health-error" : ""}>{system?.database === "healthy" ? "Accessible" : system?.database === "unavailable" || systemUnavailable ? "Indisponible" : "Vérification…"}</strong><small>Connexion PostgreSQL</small></article>
      <article><span>Scheduler</span><strong className={monitor?.scheduler_running ? "health-ok" : ""}>{summary.scheduler}</strong><small>{monitor?.sync_enabled ? "Monitoring activé" : "Monitoring manuel"}</small></article>
      <article><span>Requête 24/7</span><strong>{summary.query}</strong><small>Variable MARKET_SYNC_QUERY</small></article>
    </section>
    {monitor?.warnings.length ? <div className={`market-limit ${monitorUnavailable ? "alert" : ""}`}><strong>État du monitoring</strong><p>{monitor.warnings.join(" ")}</p></div> : null}
    <section className="stat-grid" aria-label="Métriques du monitoring marché">
      <article className="stat-card"><span>Listings actifs</span><strong>{loading ? "…" : summary.listings.toLocaleString("fr-FR")}</strong><small>{monitor?.metrics.total_listings.toLocaleString("fr-FR") ?? "0"} conservés au total</small></article>
      <article className="stat-card"><span>Observations de prix</span><strong>{loading ? "…" : summary.observations.toLocaleString("fr-FR")}</strong><small>Historique persisté</small></article>
      <article className="stat-card"><span>Opportunités actives</span><strong>{loading ? "…" : summary.opportunities.toLocaleString("fr-FR")}</strong><small>Scores recalculés après succès</small></article>
      <article className={`stat-card ${summary.syncErrors24h ? "alert" : ""}`}><span>Erreurs 24 h</span><strong>{loading ? "…" : summary.syncErrors24h.toLocaleString("fr-FR")}</strong><small>Dernières tentatives marché</small></article>
    </section>
    {loading && !monitor ? <LoadingState /> : <section className="market-cards">{monitor?.platforms.map((market) => <article className="market-card" key={market.platform}>
      <header><span className={`market-letter ${market.platform}`}>{market.platform[0].toUpperCase()}</span><div><h2>{marketNames[market.platform]}</h2><span>{market.integration_status.replaceAll("_", " ")}</span></div><StatusBadge status={market.status} /></header>
      <p>{market.message}</p><dl><div><dt>État des données</dt><dd>{marketOperationalLabel(market)}</dd></div><div><dt>Dernière tentative</dt><dd>{dateTime(market.last_attempt_at)}</dd></div><div><dt>Dernier succès</dt><dd>{dateTime(market.last_success_at)}</dd></div><div><dt>Prochaine exécution</dt><dd>{dateTime(market.next_run_at)}</dd></div><div><dt>Durée</dt><dd>{market.last_duration_ms === null ? "Jamais" : `${market.last_duration_ms} ms`}</dd></div><div><dt>Reçus / créés / mis à jour</dt><dd>{market.last_items_received} / {market.last_items_created} / {market.last_items_updated}</dd></div><div><dt>Échecs consécutifs</dt><dd>{market.consecutive_failures}</dd></div><div><dt>Dernière erreur</dt><dd>{market.last_error ? `${dateTime(market.last_error_at)} — ${market.last_error}` : "Aucune enregistrée"}</dd></div><div><dt>Type de données</dt><dd>{market.platform === "skinport" ? "Agrégats de prix" : "Listings individuels"}</dd></div></dl>
    </article>)}</section>}
    <div className="market-limit"><strong>Lecture et analyse uniquement</strong><p>Aucun connecteur ne passe d’ordre, n’achète d’objet ou n’accepte de trade. Skinport expose ici des agrégats : ils ne sont jamais présentés comme des annonces individuelles.</p></div>
    <DataPrinciple />
  </>;
}
