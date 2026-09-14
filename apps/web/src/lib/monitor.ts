import type { MarketMonitorData, MarketStatus } from "./types";

export function monitorSummary(monitor: MarketMonitorData | null) {
  const metrics = monitor?.metrics;
  return {
    scheduler: monitor?.scheduler_running ? "Actif" : "Inactif",
    query: monitor?.sync_query_configured ? "Configurée" : "Non configurée",
    listings: metrics?.active_listings ?? 0,
    observations: metrics?.price_observations ?? 0,
    opportunities: metrics?.active_opportunities ?? 0,
    syncErrors24h: metrics?.sync_errors_24h ?? 0,
  };
}

export function marketOperationalLabel(market: MarketStatus): string {
  if (market.status === "not_configured") return "Option désactivée";
  if (market.status === "demo") return "Fixtures DEMO";
  if (market.status === "degraded") return "Collecte partielle";
  if (market.freshness === "fresh") return "Données fraîches";
  if (market.freshness === "stale") return "Données périmées";
  if (market.freshness === "very_stale") return "Données très périmées";
  return "Aucun succès enregistré";
}

export function hasBlockingMarketFailure(monitor: MarketMonitorData): boolean {
  return monitor.platforms.some((market) => market.status === "error" || market.status === "unavailable" || market.status === "very_stale");
}
