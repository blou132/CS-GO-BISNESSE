import { describe, expect, it } from "vitest";
import { hasBlockingMarketFailure, marketOperationalLabel, monitorSummary, realtimeLabel, sourceOperationalLabel } from "./monitor";
import type { RealtimeStatus } from "./realtime-types";
import type { MarketMonitorData, MarketStatus } from "./types";

const market: MarketStatus = {
  platform: "skinport",
  integration_status: "PARTIAL",
  status: "online",
  message: "Synchronisation réussie.",
  freshness: "fresh",
  configured: true,
  last_sync_at: "2026-09-06T10:00:00Z",
  last_success_at: "2026-09-06T10:00:00Z",
  last_attempt_at: "2026-09-06T10:00:00Z",
  last_failure_at: null,
  last_duration_ms: 120,
  last_items_received: 10,
  last_items_created: 2,
  last_items_updated: 8,
  last_error: null,
  last_error_code: null,
  last_error_at: null,
  consecutive_failures: 0,
  next_run_at: "2026-09-06T10:15:00Z",
};

const monitor: MarketMonitorData = {
  mode: "live",
  sync_enabled: true,
  sync_query_configured: true,
  scheduler_running: true,
  platforms: [market],
  metrics: {
    total_listings: 20,
    active_listings: 12,
    price_observations: 240,
    aggregate_market_stats: 18,
    realized_sales: 4,
    buy_order_observations: 11,
    active_opportunities: 3,
    sync_errors_24h: 0,
    average_freshness_seconds: 120,
  },
  warnings: [],
};

describe("market monitor helpers", () => {
  it("distinguishes disabled collection from provider refusal without breaking REST readiness", () => {
    const stream = { enabled: false, status: "blocked", http_status: 403 } as RealtimeStatus;
    expect(realtimeLabel(stream)).toBe("Bloqué, collecte désactivée");
    expect(realtimeLabel({ ...stream, enabled: true })).toBe("Bloqué par le fournisseur");
    expect(sourceOperationalLabel(market, stream)).toBe("Source dégradée : REST en ligne, temps réel bloqué");
    expect(hasBlockingMarketFailure({ ...monitor, realtime: { skinport: stream } })).toBe(false);
  });
  it("keeps REST healthy when the optional stream is disconnected", () => {
    const stream = { enabled: true, status: "disconnected", last_success_at: null } as RealtimeStatus;
    expect(realtimeLabel(stream)).toBe("Déconnecté");
    expect(hasBlockingMarketFailure({ ...monitor, realtime: { skinport: stream } })).toBe(false);
  });

  it("requires an ingestion success before showing online", () => {
    const stream = { enabled: true, status: "online", last_success_at: null } as RealtimeStatus;
    expect(realtimeLabel(stream)).toBe("En attente de données");
    expect(realtimeLabel({ ...stream, enabled: false })).toBe("Désactivé");
    expect(realtimeLabel({ ...stream, last_success_at: "2026-09-14T12:00:00Z" })).toBe("En ligne");
  });
  it("résume l'état système et les métriques principales", () => {
    expect(monitorSummary(monitor)).toMatchObject({
      scheduler: "Actif",
      query: "Configurée",
      listings: 12,
      observations: 240,
      opportunities: 3,
      syncErrors24h: 0,
    });
  });

  it("distingue les marchés non configurés, périmés, très périmés et démo", () => {
    expect(marketOperationalLabel({ ...market, status: "not_configured" })).toBe("Option désactivée");
    expect(marketOperationalLabel({ ...market, freshness: "stale" })).toBe("Données périmées");
    expect(marketOperationalLabel({ ...market, freshness: "very_stale" })).toBe("Données très périmées");
    expect(marketOperationalLabel({ ...market, status: "demo" })).toBe("Fixtures DEMO");
  });

  it("ne considère pas not_configured comme une panne bloquante", () => {
    expect(
      hasBlockingMarketFailure({
        ...monitor,
        platforms: [{ ...market, status: "not_configured" }],
      }),
    ).toBe(false);
    expect(
      hasBlockingMarketFailure({
        ...monitor,
        platforms: [{ ...market, status: "error" }],
        metrics: { ...monitor.metrics, sync_errors_24h: 1 },
      }),
    ).toBe(true);
  });

  it("affiche une collecte partielle même si ses données principales sont fraîches", () => {
    expect(marketOperationalLabel({ ...market, status: "degraded", freshness: "fresh" })).toBe("Collecte partielle");
  });
});
