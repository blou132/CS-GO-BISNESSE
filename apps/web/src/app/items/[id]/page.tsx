"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";
import { Icon } from "@/components/icons";
import { readJson, useMarkets } from "@/components/market-provider";
import { DataPrinciple, LoadingState, MarketBadge, Score } from "@/components/shared";
import { dateTime, money, observationLabel, percent, safeExternalUrl } from "@/lib/format";
import type { ItemData } from "@/lib/types";

export default function ItemPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { mode } = useMarkets();
  const requestKey = `${id}:${mode}`;
  const [result, setResult] = useState<{ key: string; data: ItemData | null; error: string | null } | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    fetch(`/api/items/${encodeURIComponent(id)}?mode=${mode}`, { cache: "no-store", signal: controller.signal })
      .then(readJson<ItemData>)
      .then((data) => { if (!controller.signal.aborted) setResult({ key: requestKey, data, error: null }); })
      .catch((reason: unknown) => { if (!controller.signal.aborted) setResult({ key: requestKey, data: null, error: reason instanceof Error ? reason.message : "Erreur inattendue." }); });
    return () => controller.abort();
  }, [id, mode, requestKey]);
  const data = result?.key === requestKey ? result.data : null;
  const error = result?.key === requestKey ? result.error : null;
  if (error) return <div className="empty-state"><Icon name="warning" size={28} /><h1>Objet inaccessible</h1><p>{error}</p><Link href="/scanner" className="button button-ghost">Retour au scanner</Link></div>;
  if (!data) return <LoadingState />;
  const item = data.item;
  const listingUrl = safeExternalUrl(item.listing_url);
  const inspectUrl = safeExternalUrl(item.inspect_link, true);
  return <>
    <Link href="/scanner" className="back-link"><Icon name="back" size={15} /> Retour au scanner</Link>
    <section className="item-hero"><div className="item-token large">{(item.weapon ?? "CS2").slice(0, 3)}</div><div className="item-title"><span className="eyebrow">ANALYSE D’EXEMPLAIRE</span><h1>{item.weapon && item.skin ? `${item.weapon} | ${item.skin}` : item.market_hash_name}</h1><p>{item.exterior ?? "Exterior inconnu"} · observé le {dateTime(item.observed_at)}</p><MarketBadge platform={item.platform} /></div><div className="item-price"><span>Prix affiché</span><strong>{money(item.price_eur_reference)}</strong><small>{money(item.price_original, item.currency_original)} à la source</small></div></section>
    <section className="item-kpis"><article><span>Float</span><strong>{item.float_value ? Number(item.float_value).toFixed(6) : "—"}</strong><small>Score {item.float_score ?? "inconnu"}/100</small></article><article><span>Valeur estimée</span><strong>{money(item.estimated_value_eur)}</strong><small>Confiance {item.confidence ?? "inconnue"}{item.confidence !== null ? " %" : ""}</small></article><article><span>Profit potentiel</span><strong className="positive">{money(item.potential_profit_eur)}</strong><small>ROI {percent(item.roi)}</small></article><article><span>Opportunity Score</span><Score value={item.opportunity_score} /><small>Estimation non garantie</small></article></section>
    <div className="detail-grid"><section className="panel detail-panel"><div className="panel-heading"><div><span className="eyebrow">IDENTITÉ NORMALISÉE</span><h2>Caractéristiques</h2></div></div><dl className="spec-list"><div><dt>Market hash name</dt><dd>{item.market_hash_name}</dd></div><div><dt>Paint seed</dt><dd>{item.paint_seed ?? "—"}</dd></div><div><dt>Paint index</dt><dd>{item.paint_index ?? "—"}</dd></div><div><dt>Phase Doppler</dt><dd>{item.doppler_phase ?? "—"}</dd></div><div><dt>Fade</dt><dd>{item.fade_percentage ? `${item.fade_percentage} %` : "—"}</dd></div></dl><div className="link-row">{listingUrl ? <a href={listingUrl} target="_blank" rel="noreferrer" className="button button-ghost">Voir l’annonce <Icon name="arrow" size={15} /></a> : null}{inspectUrl ? <a href={inspectUrl} className="button button-ghost">Inspecter en jeu</a> : null}</div></section>
      <section className="panel detail-panel"><div className="panel-heading"><div><span className="eyebrow">STICKERS APPLIQUÉS</span><h2>Stickers</h2></div></div>{item.stickers.length ? <ul className="sticker-list">{item.stickers.map((sticker, index) => <li key={`${sticker.name}-${index}`}><strong>{sticker.name}</strong><span>Slot {sticker.slot ?? "—"}</span><small>Valeur appliquée estimée : {money(sticker.estimated_applied_value)}</small></li>)}</ul> : <p className="panel-empty">Aucun sticker renseigné. Le prix d’un sticker non appliqué n’est jamais repris comme premium.</p>}</section></div>
    <section className="panel"><div className="panel-heading"><div><span className="eyebrow">MARKET COMPARISON</span><h2>Comparaison des observations</h2></div></div><div className="comparison-grid">{data.comparisons.map((entry) => <article key={`${entry.platform}-${entry.observation_type}`}><MarketBadge platform={entry.platform} /><span>{observationLabel(entry.observation_type)}</span><strong>{money(entry.median_eur)}</strong><small>Min. {money(entry.lowest_eur)} · moyenne {money(entry.mean_eur)} · n={entry.sample_size}</small><small>{entry.median_gap_to_best_eur === null ? "Aucun marché comparable pour ce type" : `Écart médian vs meilleur : ${money(entry.median_gap_to_best_eur)} (${percent(entry.median_gap_to_best_percent)})`}</small></article>)}</div></section>
    <section className="panel"><div className="panel-heading"><div><span className="eyebrow">PRICE HISTORY</span><h2>Historique</h2></div></div><div className="history-list">{data.history.slice(0, 18).map((entry, index) => <div key={`${entry.platform}-${entry.timestamp}-${index}`}><span>{dateTime(entry.timestamp)}</span><MarketBadge platform={entry.platform} /><span>{observationLabel(entry.observation_type)}</span><strong>{money(entry.price, entry.currency)}</strong><small>{entry.volume === null ? "Volume inconnu" : `Volume ${entry.volume}`}</small></div>)}</div></section>
    {item.warnings.length ? <div className="warning-list"><strong>Limites de cette analyse</strong><ul>{item.warnings.map((warning, index) => <li key={`${warning}-${index}`}>{warning}</li>)}</ul></div> : null}
    <DataPrinciple />
  </>;
}
