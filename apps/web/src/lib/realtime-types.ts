export interface RealtimeStatus {
  enabled: boolean;
  status: "disabled" | "connecting" | "connected" | "online" | "degraded" | "disconnected" | "stopped";
  connected: boolean;
  connected_since: string | null;
  last_event_at: string | null;
  last_success_at: string | null;
  next_retry_at: string | null;
  http_status: number | null;
  events_per_minute: number;
  events_received: number;
  reconnect_count: number;
  queue_depth: number;
  dropped_events: number;
  invalid_events: number;
  duplicate_events: number;
  listings_updated: number;
  sales_received: number;
  errors: number;
  last_error: string | null;
}

export interface EvidenceSource {
  platform: string;
  kind: string;
  value_eur: string | null;
  observed_at: string;
  volume: number | null;
  window: string | null;
  record_id: string | null;
  external_id: string | null;
  price_original: string | null;
  currency: string | null;
  fx_source: string | null;
  fx_timestamp: string | null;
  timestamp_basis: string | null;
}

export interface ValuationProvenance {
  buy: EvidenceSource;
  reference: EvidenceSource[];
  reference_sample_size: number;
  comparable_count: number;
  float_min_samples: number;
  float_status: "AVAILABLE" | "INSUFFICIENT_DATA";
  fee_status: "UNKNOWN" | "DEMO_SYNTHETIC";
  effective_fx_status: "UNKNOWN";
  eligibility: "REFERENCE_ONLY" | "DEMO";
}
