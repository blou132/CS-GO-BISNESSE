"use client";

import { useEffect, useState } from "react";
import { readJson, useMarkets } from "@/components/market-provider";
import { DataPrinciple, LoadingState, PageHeading, StatusBadge, SyncForm } from "@/components/shared";
import { dateTime, marketNames } from "@/lib/format";
import type { SystemHealth } from "@/lib/types";

export default function MarketsPage() {
  const { data, loading } = useMarkets();
  const [system, setSystem] = useState<SystemHealth | null>(null);
  const [systemUnavailable, setSystemUnavailable] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/health", { cache: "no-store", signal: controller.signal })
      .then(readJson<SystemHealth>)
      .then((value) => { if (!controller.signal.aborted) setSystem(value); })
      .catch(() => { if (!controller.signal.aborted) setSystemUnavailable(true); });
    return () => controller.abort();
  }, []);
  return <>
    <PageHeading eyebrow="DATA SOURCES" title="Marchés" description="Suivez les capacités réellement intégrées, leur fraîcheur et leurs limites documentées." />
    <section className="system-status-grid" aria-label="État des services internes">
      <article><span>API</span><strong className={system ? "health-ok" : systemUnavailable ? "health-error" : ""}>{system ? "Opérationnelle" : systemUnavailable ? "Indisponible" : "Vérification…"}</strong><small>Processus applicatif</small></article>
      <article><span>Base de données</span><strong className={system?.database === "healthy" ? "health-ok" : system?.database === "unavailable" || systemUnavailable ? "health-error" : ""}>{system?.database === "healthy" ? "Accessible" : system?.database === "unavailable" || systemUnavailable ? "Indisponible" : "Vérification…"}</strong><small>Connexion PostgreSQL</small></article>
    </section>
    <SyncForm />
    {loading && !data ? <LoadingState /> : <section className="market-cards">{data?.markets.map((market) => <article className="market-card" key={market.platform}>
      <header><span className={`market-letter ${market.platform}`}>{market.platform[0].toUpperCase()}</span><div><h2>{marketNames[market.platform]}</h2><span>{market.integration_status.replaceAll("_", " ")}</span></div><StatusBadge status={market.status} /></header>
      <p>{market.message}</p><dl><div><dt>Dernière tentative</dt><dd>{dateTime(market.last_attempt_at)}</dd></div><div><dt>Dernier succès</dt><dd>{dateTime(market.last_sync_at)}</dd></div><div><dt>Dernière erreur</dt><dd>{market.last_error ? `${dateTime(market.last_error_at)} — ${market.last_error}` : "Aucune enregistrée"}</dd></div><div><dt>Type de données</dt><dd>{market.platform === "skinport" ? "Agrégats de prix" : "Listings individuels"}</dd></div><div><dt>Mode</dt><dd>{data?.mode === "demo" ? "Fixtures DEMO" : "API officielle"}</dd></div></dl>
    </article>)}</section>}
    <div className="market-limit"><strong>Lecture et analyse uniquement</strong><p>Aucun connecteur ne passe d’ordre, n’achète d’objet ou n’accepte de trade. Skinport expose ici des agrégats : ils ne sont jamais présentés comme des annonces individuelles.</p></div>
    <DataPrinciple />
  </>;
}
