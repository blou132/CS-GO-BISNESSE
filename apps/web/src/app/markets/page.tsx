"use client";

import { useMarkets } from "@/components/market-provider";
import { DataPrinciple, LoadingState, PageHeading, StatusBadge, SyncForm } from "@/components/shared";
import { dateTime, marketNames } from "@/lib/format";

export default function MarketsPage() {
  const { data, loading } = useMarkets();
  return <>
    <PageHeading eyebrow="DATA SOURCES" title="Marchés" description="Suivez les capacités réellement intégrées, leur fraîcheur et leurs limites documentées." />
    <SyncForm />
    {loading && !data ? <LoadingState /> : <section className="market-cards">{data?.markets.map((market) => <article className="market-card" key={market.platform}>
      <header><span className={`market-letter ${market.platform}`}>{market.platform[0].toUpperCase()}</span><div><h2>{marketNames[market.platform]}</h2><span>{market.integration_status.replaceAll("_", " ")}</span></div><StatusBadge status={market.status} /></header>
      <p>{market.message}</p><dl><div><dt>Dernière synchronisation</dt><dd>{dateTime(market.last_sync_at)}</dd></div><div><dt>Type de données</dt><dd>{market.platform === "skinport" ? "Agrégats de prix" : "Listings individuels"}</dd></div><div><dt>Mode</dt><dd>{data?.mode === "demo" ? "Fixtures DEMO" : "API officielle"}</dd></div></dl>
    </article>)}</section>}
    <div className="market-limit"><strong>Lecture et analyse uniquement</strong><p>Aucun connecteur ne passe d’ordre, n’achète d’objet ou n’accepte de trade. Skinport expose ici des agrégats : ils ne sont jamais présentés comme des annonces individuelles.</p></div>
    <DataPrinciple />
  </>;
}
