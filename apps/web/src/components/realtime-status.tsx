import { dateTime } from "@/lib/format";
import { realtimeLabel } from "@/lib/monitor";
import type { RealtimeStatus } from "@/lib/realtime-types";

export function RealtimeSummary({ state }: { state: RealtimeStatus }) {
  return <section className="evidence-section" aria-label="Skinport temps réel">
    <div className="panel-heading"><h2>Skinport temps réel</h2><strong className={state.status === "online" && state.last_success_at ? "health-ok" : ""}>{realtimeLabel(state)}</strong></div>
    <dl className="stream-metrics">
      <div><dt>Connecté depuis</dt><dd>{dateTime(state.connected_since)}</dd></div>
      <div><dt>Dernier événement</dt><dd>{dateTime(state.last_event_at)}</dd></div>
      <div><dt>Événements / min</dt><dd>{state.events_per_minute}</dd></div>
      <div><dt>Reconnexions</dt><dd>{state.reconnect_count}</dd></div>
      <div><dt>File d’attente</dt><dd>{state.queue_depth}</dd></div>
      <div><dt>Événements perdus</dt><dd>{state.dropped_events}</dd></div>
      <div><dt>Annonces / ventes ingérées</dt><dd>{state.listings_updated} / {state.sales_received}</dd></div>
      <div><dt>Doublons / invalides</dt><dd>{state.duplicate_events} / {state.invalid_events}</dd></div>
      <div><dt>Prochaine tentative</dt><dd>{dateTime(state.next_retry_at)}</dd></div>
      <div><dt>Dernière erreur</dt><dd>{state.last_error ?? "Aucune"}{state.http_status && state.http_status >= 400 ? ` (HTTP ${state.http_status})` : ""}</dd></div>
    </dl>
  </section>;
}
