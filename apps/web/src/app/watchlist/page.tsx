"use client";

import { type FormEvent, useEffect, useState } from "react";
import { Icon } from "@/components/icons";
import { ListingsTable } from "@/components/listings-table";
import { readJson, useMarkets } from "@/components/market-provider";
import { DataPrinciple } from "@/components/shared";
import { dateTime, marketNames } from "@/lib/format";
import type { Mode, Platform, ScannerPageData } from "@/lib/types";
import { parsePaintSeeds, type WatchlistPage, type WatchRule, type WatchRuleInput } from "@/lib/watchlist";

function useWatchResource<T>(url: string | null) {
  const [response, setResponse] = useState<{ url: string; data: T | null; error: string | null } | null>(null);
  useEffect(() => {
    if (!url) return;
    const controller = new AbortController();
    fetch(url, { cache: "no-store", signal: controller.signal })
      .then(readJson<T>)
      .then((data) => { if (!controller.signal.aborted) setResponse({ url, data, error: null }); })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) setResponse({ url, data: null, error: reason instanceof Error ? reason.message : "Chargement impossible." });
      });
    return () => controller.abort();
  }, [url]);
  return {
    data: response?.url === url ? response.data : null,
    error: response?.url === url ? response.error : null,
    loading: url !== null && response?.url !== url,
  };
}

function PageControls({ page, pages, onChange }: { page: number; pages: number; onChange: (page: number) => void }) {
  if (pages <= 1) return null;
  return <nav className="pagination" aria-label="Pagination">
    <button type="button" className="icon-button" title="Page précédente" aria-label="Page précédente" disabled={page <= 1} onClick={() => onChange(page - 1)}><Icon name="back" size={16} /></button>
    <span>Page {page} sur {pages}</span>
    <button type="button" className="icon-button" title="Page suivante" aria-label="Page suivante" disabled={page >= pages} onClick={() => onChange(page + 1)}><Icon name="chevron" size={16} /></button>
  </nav>;
}

function RuleEditor({ rule, busy, onSave, onCancel, onDelete }: {
  rule: WatchRule | null;
  busy: boolean;
  onSave: (value: WatchRuleInput) => Promise<void>;
  onCancel: () => void;
  onDelete: () => void;
}) {
  const [error, setError] = useState<string | null>(null);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const text = (key: string) => String(data.get(key) ?? "").trim();
    setError(null);
    try {
      await onSave({
        name: text("name"),
        enabled: data.get("enabled") === "on",
        filters: {
          market_hash_name: text("market_hash_name"),
          market: text("market") as Platform || null,
          max_price_eur: text("max_price_eur") || null,
          max_float: text("max_float") || null,
          paint_seeds: parsePaintSeeds(text("paint_seeds")),
          doppler_phase: text("doppler_phase") || null,
        },
      });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Enregistrement impossible.");
    }
  }
  return <section className="watch-editor" aria-labelledby="rule-editor-title">
    <h2 id="rule-editor-title">{rule ? "Modifier la règle" : "Nouvelle règle"}</h2>
    <form onSubmit={submit}>
      <fieldset disabled={busy}>
        <div className="watch-form-grid">
          <label className="filter-field"><span>Nom de la règle</span><input name="name" required maxLength={128} defaultValue={rule?.name} autoFocus /></label>
          <label className="filter-field"><span>Nom exact du skin</span><input name="market_hash_name" required minLength={3} maxLength={256} defaultValue={rule?.filters.market_hash_name} placeholder="AK-47 | Redline (Field-Tested)" /></label>
          <label className="filter-field"><span>Marché</span><select name="market" defaultValue={rule?.filters.market ?? ""}><option value="">Tous</option>{Object.entries(marketNames).map(([value, name]) => <option key={value} value={value}>{name}</option>)}</select></label>
          <label className="filter-field"><span>Prix maximal EUR (inclus)</span><input name="max_price_eur" type="number" min="0" step="any" defaultValue={rule?.filters.max_price_eur ?? ""} /></label>
          <label className="filter-field"><span>Float maximal (inclus)</span><input name="max_float" type="number" min="0" max="1" step="any" defaultValue={rule?.filters.max_float ?? ""} /></label>
          <label className="filter-field"><span>Phase Doppler</span><select name="doppler_phase" defaultValue={rule?.filters.doppler_phase ?? ""}><option value="">Toutes</option>{["Phase 1", "Phase 2", "Phase 3", "Phase 4", "Ruby", "Sapphire", "Black Pearl", "Emerald"].map((phase) => <option key={phase}>{phase}</option>)}</select></label>
          <label className="filter-field watch-seeds"><span>Paint seeds</span><input name="paint_seeds" maxLength={600} defaultValue={rule?.filters.paint_seeds.join(", ")} placeholder="0, 255, 661" /></label>
          <label className="watch-enabled"><input type="checkbox" name="enabled" defaultChecked={rule?.enabled ?? true} /><span>Règle active</span></label>
        </div>
        {error ? <p className="notice error-notice" role="alert">{error}</p> : null}
        <div className="watch-actions">
          <button className="button button-primary" type="submit"><Icon name="check" size={16} />{busy ? "Enregistrement…" : "Enregistrer"}</button>
          <button className="button button-ghost" type="button" onClick={onCancel}>Annuler</button>
          {rule ? <button className="text-button watch-delete" type="button" onClick={onDelete}>Supprimer</button> : null}
        </div>
      </fieldset>
    </form>
  </section>;
}

function WatchlistView({ mode }: { mode: Mode }) {
  const { data: marketData } = useMarkets();
  const [page, setPage] = useState(1);
  const [revision, setRevision] = useState(0);
  const [editor, setEditor] = useState<WatchRule | "new" | null>(null);
  const [selected, setSelected] = useState<WatchRule | null>(null);
  const [matchPage, setMatchPage] = useState(1);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const rules = useWatchResource<WatchlistPage>(`/api/watchlist?${new URLSearchParams({ mode, page: String(page), _revision: String(revision) })}`);
  const matches = useWatchResource<ScannerPageData>(selected?.enabled
    ? `/api/watchlist/${selected.id}/matches?${new URLSearchParams({ mode, page: String(matchPage), _revision: `${revision}|${marketData?.last_sync_at ?? ""}` })}`
    : null);

  async function save(value: WatchRuleInput) {
    setBusy(true);
    setError(null);
    try {
      const id = editor && editor !== "new" ? editor.id : null;
      const saved = await readJson<WatchRule>(await fetch(`/api/watchlist${id ? `/${id}` : ""}?mode=${mode}`, {
        method: id ? "PUT" : "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(value),
      }));
      setEditor(null);
      setPage(1);
      setSelected(saved);
      setMatchPage(1);
      setRevision((current) => current + 1);
      setMessage("Règle enregistrée.");
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!editor || editor === "new" || !window.confirm(`Supprimer la règle « ${editor.name} » ?`)) return;
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(`/api/watchlist/${editor.id}?mode=${mode}`, { method: "DELETE" });
      if (!response.ok) await readJson(response);
      if (selected?.id === editor.id) setSelected(null);
      setEditor(null);
      setPage(1);
      setRevision((current) => current + 1);
      setMessage("Règle supprimée.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Suppression impossible.");
    } finally {
      setBusy(false);
    }
  }

  return <>
    <div className="page-heading"><div><div className="eyebrow">SUIVI DES SKINS</div><h1>Watchlist</h1></div><button className="button button-primary" disabled={busy} onClick={() => { setEditor("new"); setMessage(null); }}><Icon name="target" size={16} />Nouvelle règle</button></div>
    {message ? <p className="notice" role="status">{message}</p> : null}
    {error || rules.error ? <p className="notice error-notice" role="alert">{error ?? rules.error}<button className="text-button" onClick={() => setRevision((current) => current + 1)}>Réessayer</button></p> : null}
    {editor ? <RuleEditor key={editor === "new" ? "new" : `${editor.id}|${editor.updated_at}`} rule={editor === "new" ? null : editor} busy={busy} onSave={save} onCancel={() => setEditor(null)} onDelete={() => { void remove(); }} /> : null}
    <section className="watch-rules" aria-label="Règles enregistrées" aria-busy={rules.loading}>
      <div className="watch-heading"><h2>Règles enregistrées</h2><span>{rules.data?.total ?? "—"}</span></div>
      {rules.loading ? <p role="status" className="watch-empty">Chargement des règles…</p> : rules.data?.items.length === 0 ? <p className="watch-empty">Aucune règle enregistrée en mode {mode === "demo" ? "DEMO" : "LIVE"}.</p> : null}
      {rules.data?.items.map((rule) => <article key={rule.id} className="watch-rule" aria-label={rule.name}>
        <div className="watch-rule-description">
          <h3>{rule.name} <span className={`watch-state ${rule.enabled ? "enabled" : "paused"}`}>{rule.enabled ? "Active" : "En pause"}</span></h3>
          <p className="mono">{rule.filters.market_hash_name}</p>
          <div className="watch-conditions">
            <span>{rule.filters.market ? marketNames[rule.filters.market] : "Tous les marchés"}</span>
            {rule.filters.max_price_eur !== null ? <span>Prix ≤ {rule.filters.max_price_eur} EUR</span> : null}
            {rule.filters.max_float !== null ? <span>Float ≤ {rule.filters.max_float}</span> : null}
            {rule.filters.doppler_phase ? <span>{rule.filters.doppler_phase}</span> : null}
            {rule.filters.paint_seeds.length ? <span>Seeds : {rule.filters.paint_seeds.join(", ")}</span> : null}
          </div>
          <small>Modifiée le {dateTime(rule.updated_at)}</small>
        </div>
        <div className="watch-actions">
          <button className="button button-small button-ghost" disabled={!rule.enabled || busy} onClick={() => { setSelected(rule); setMatchPage(1); setRevision((current) => current + 1); }}><Icon name="search" size={15} />Correspondances</button>
          <button className="icon-button" disabled={busy} title={`Modifier ${rule.name}`} aria-label={`Modifier ${rule.name}`} onClick={() => { setEditor(rule); setMessage(null); }}><Icon name="settings" size={16} /></button>
        </div>
      </article>)}
      {rules.data ? <PageControls page={page} pages={rules.data.pages} onChange={setPage} /> : null}
    </section>
    {selected ? <section className="watch-matches" aria-labelledby="matches-title" aria-busy={matches.loading}>
      <div className="watch-heading"><h2 id="matches-title">Correspondances : {selected.name}</h2><span>{matches.data?.total ?? "—"}</span></div>
      {!selected.enabled ? <p className="watch-empty">Cette règle est en pause.</p> : matches.loading ? <p className="watch-empty" role="status">Chargement des correspondances…</p> : matches.error ? <p className="notice error-notice" role="alert">{matches.error}</p> : matches.data?.items.length ? <ListingsTable rows={matches.data.items} /> : <p className="watch-empty">Aucune annonce observée ne correspond à cette règle.</p>}
      {matches.data?.warnings.length ? <p className="market-limit">{matches.data.warnings.join(" ")}</p> : null}
      {matches.data ? <PageControls page={matchPage} pages={matches.data.pages} onChange={setMatchPage} /> : null}
    </section> : null}
    <DataPrinciple />
  </>;
}

export default function Watchlist() {
  const { mode } = useMarkets();
  return <WatchlistView key={mode} mode={mode} />;
}
