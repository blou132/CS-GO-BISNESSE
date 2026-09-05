"use client";

import { useState } from "react";
import { Icon } from "./icons";
import { useMarkets } from "./market-provider";
import { marketNames } from "@/lib/format";
import type { MarketStatus, Platform } from "@/lib/types";

export function PageHeading({ eyebrow, title, description, action }: { eyebrow: string; title: string; description: string; action?: React.ReactNode }) {
  return <div className="page-heading"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1><p>{description}</p></div>{action}</div>;
}

export function SyncForm() {
  const { mode, loading, sync } = useMarkets();
  const [query, setQuery] = useState("");
  return <form className="sync-form" onSubmit={(event) => { event.preventDefault(); sync(query.trim()); }}>
    <div className="sync-intro"><span className="icon-container"><Icon name="search" size={20} /></span><div><strong>Observer un skin</strong><span>Synchronisez son nom exact sur les marchés disponibles.</span></div></div>
    <label className="sync-input"><span className="sr-only">Nom exact du skin à synchroniser</span><input type="text" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="AK-47 | Redline (Field-Tested)" maxLength={200} required={mode === "live"} disabled={loading} /></label>
    <button className="button button-primary" disabled={loading || (mode === "live" && !query.trim())}><Icon name="refresh" className={loading ? "spin" : ""} />{loading ? "Synchronisation…" : "Synchroniser"}</button>
  </form>;
}

export function MarketBadge({ platform }: { platform: Platform }) { return <span className={`market-badge ${platform}`}><span className="market-symbol">{platform === "csfloat" ? "C" : platform === "skinport" ? "S" : "D"}</span>{marketNames[platform]}</span>; }

const statusLabels: Record<MarketStatus["status"], string> = { online: "En ligne", unavailable: "Indisponible", error: "En erreur", stale: "Données périmées", demo: "Démo", idle: "En attente" };
export function StatusBadge({ status }: { status: MarketStatus["status"] }) { return <span className={`status-badge ${status}`}><i className={`status-dot ${status}`} />{statusLabels[status]}</span>; }

export function EmptyState({ filtered = false }: { filtered?: boolean }) {
  const { mode, switchMode, loading, error } = useMarkets();
  return <div className="empty-state"><div className="empty-symbol"><Icon name={filtered ? "filter" : "scanner"} size={28} /></div><h3>{filtered ? "Aucune annonce ne correspond" : error ? "Les données ne sont pas accessibles" : "Votre prochaine analyse commence ici"}</h3><p>{filtered ? "Élargissez vos filtres. Une valeur inconnue est exclue dès qu’un filtre numérique lui est appliqué." : mode === "demo" ? "Chargez les fixtures en lançant une synchronisation de démonstration." : "Saisissez le nom exact d’un skin pour observer les marchés, ou explorez l’interface avec des données de test."}</p>{!filtered && mode === "live" ? <button className="button button-ghost" onClick={switchMode} disabled={loading}>Explorer la démo <Icon name="arrow" size={15} /></button> : null}</div>;
}

export function LoadingState() { return <div className="loading-state" role="status"><Icon name="refresh" className="spin" size={22} /><strong>Chargement des observations</strong><span>Récupération des données et du statut des marchés…</span></div>; }

export function Score({ value }: { value: number | null }) { return value === null ? <span className="unknown" title="Échantillon ou données insuffisants pour établir un score.">—</span> : <span className={`score ${value >= 70 ? "score-high" : ""}`}><span>{Math.round(value)}</span><small>/100</small></span>; }

export function DataPrinciple() { return <div className="data-principle"><Icon name="info" size={15} /><span>Un prix d’annonce n’est pas une vente réalisée. Les conversions EUR sont indicatives ; les estimations et profits dépendent des données et des frais disponibles.</span></div>; }
