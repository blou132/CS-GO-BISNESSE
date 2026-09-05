"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import type { DashboardData, Mode } from "@/lib/types";

interface MarketContextValue {
  mode: Mode;
  data: DashboardData | null;
  loading: boolean;
  error: string | null;
  switchMode: () => void;
  refresh: () => void;
  sync: (query: string) => void;
}

const MarketContext = createContext<MarketContextValue | null>(null);

export async function readJson<T>(response: Response): Promise<T> {
  const payload: unknown = await response.json();
  if (!response.ok) {
    const detail = payload && typeof payload === "object" && "detail" in payload ? payload.detail : undefined;
    throw new Error(typeof detail === "string" ? detail : "Impossible de récupérer les données.");
  }
  return payload as T;
}

export function MarketProvider({ children }: { children: React.ReactNode }) {
  const [mode, setMode] = useState<Mode>("live");
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const controller = useRef<AbortController | null>(null);

  const load = useCallback(async (nextMode: Mode, sync = false, query = "") => {
    controller.current?.abort();
    const current = new AbortController();
    controller.current = current;
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({ mode: nextMode });
      if (query) params.set("query", query);
      const response = await fetch(`/api/${sync ? "sync" : "dashboard"}?${params}`, { method: sync ? "POST" : "GET", signal: current.signal, cache: "no-store" });
      const next = await readJson<DashboardData>(response);
      if (next.mode !== nextMode || !Array.isArray(next.listings) || !Array.isArray(next.markets) || !Array.isArray(next.warnings)) throw new Error("Réponse API incompatible. Aucune donnée de remplacement n’a été chargée.");
      if (!current.signal.aborted) setData(next);
    } catch (reason) {
      if (!current.signal.aborted) setError(reason instanceof Error ? reason.message : "Une erreur inattendue est survenue.");
    } finally {
      if (!current.signal.aborted) setLoading(false);
    }
  }, []);

  useEffect(() => {
    const current = new AbortController();
    controller.current = current;
    const params = new URLSearchParams({ mode: "live" });
    fetch(`/api/dashboard?${params}`, { signal: current.signal, cache: "no-store" })
      .then(readJson<DashboardData>)
      .then((next) => {
        if (next.mode !== "live" || !Array.isArray(next.listings) || !Array.isArray(next.markets)) {
          throw new Error("Réponse API incompatible.");
        }
        if (!current.signal.aborted) setData(next);
      })
      .catch((reason: unknown) => {
        if (!current.signal.aborted) setError(reason instanceof Error ? reason.message : "Une erreur inattendue est survenue.");
      })
      .finally(() => { if (!current.signal.aborted) setLoading(false); });
    return () => current.abort();
  }, []);

  function switchMode() {
    const nextMode = mode === "live" ? "demo" : "live";
    setMode(nextMode);
    setData(null);
    void load(nextMode, nextMode === "demo");
  }

  return <MarketContext.Provider value={{ mode, data, loading, error, switchMode, refresh: () => { void load(mode); }, sync: (query) => { void load(mode, true, query); } }}>{children}</MarketContext.Provider>;
}

export function useMarkets() {
  const value = useContext(MarketContext);
  if (!value) throw new Error("MarketProvider manquant.");
  return value;
}
