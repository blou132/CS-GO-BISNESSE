"use client";

import { useEffect, useState } from "react";
import { readJson } from "@/components/market-provider";
import { DataPrinciple, LoadingState, PageHeading } from "@/components/shared";
import type { IntegrationCatalog, MarketSourceInfo } from "@/lib/types";

const accessLabels: Record<MarketSourceInfo["access_status"], string> = {
  OFFICIAL_API: "API officielle",
  PUBLIC_API: "API publique",
  REQUIRES_APPROVAL: "Approbation requise",
  RESEARCH_REQUIRED: "Recherche requise",
  UNAVAILABLE: "Indisponible",
};

function runtimeLabel(source: MarketSourceInfo) {
  if (source.runtime_status === "not_integrated") return "Non intégré";
  if (source.runtime_status === "not_configured") return "Clé requise";
  return source.runtime_status.replaceAll("_", " ");
}

export default function IntegrationsPage() {
  const [catalog, setCatalog] = useState<IntegrationCatalog | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/integrations", { cache: "no-store", signal: controller.signal })
      .then(readJson<IntegrationCatalog>)
      .then((value) => { if (!controller.signal.aborted) setCatalog(value); })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : "Erreur inattendue.");
      });
    return () => controller.abort();
  }, []);

  return <>
    <PageHeading eyebrow="SOURCE REGISTRY" title="Intégrations" description="Capacités vérifiées, accès requis et état opérationnel des sources de données." />
    {error ? <div className="notice error-notice" role="alert"><strong>Registre indisponible.</strong> {error}</div> : null}
    {!catalog && !error ? <LoadingState /> : <section className="source-registry" aria-label="Registre des sources">
      {catalog?.sources.map((source) => <article className="source-card" key={source.id}>
        <header><div><span className="source-type">{source.source_type}</span><h2>{source.name}</h2></div><span className={`source-access ${source.access_status.toLowerCase()}`}>{accessLabels[source.access_status]}</span></header>
        <p>{source.note}</p>
        <dl><div><dt>État</dt><dd>{runtimeLabel(source)}</dd></div><div><dt>Authentification</dt><dd>{source.auth_required ? "Requise" : "Non requise"}</dd></div><div><dt>Configuration</dt><dd>{source.configured ? "Prête" : "Absente / non applicable"}</dd></div><div><dt>Vérification</dt><dd>{source.verified_at}</dd></div></dl>
        <div className="capability-list">{source.capabilities.length ? source.capabilities.map((capability) => <span key={capability}>{capability.replaceAll("_", " ")}</span>) : <span>Aucune capacité autorisée</span>}</div>
        <div className="source-links"><a href={source.official_url} target="_blank" rel="noreferrer">Site officiel</a>{source.documentation_url ? <a href={source.documentation_url} target="_blank" rel="noreferrer">Documentation</a> : null}</div>
      </article>)}
    </section>}
    <DataPrinciple />
  </>;
}
