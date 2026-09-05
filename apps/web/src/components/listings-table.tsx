"use client";

import Link from "next/link";
import { money, numeric, percent } from "@/lib/format";
import type { ScannerRow } from "@/lib/types";
import { Icon } from "./icons";
import { MarketBadge, Score } from "./shared";

export function ListingsTable({ rows }: { rows: ScannerRow[] }) {
  return <div className="table-scroll" tabIndex={0} role="region" aria-label="Annonces observées, tableau défilant"><table className="listings-table"><thead><tr><th scope="col">Skin / Exterior</th><th scope="col">Marché</th><th scope="col" className="numeric-cell">Prix original</th><th scope="col" className="numeric-cell">Prix EUR <span>référence</span></th><th scope="col" className="numeric-cell">Float</th><th scope="col" className="numeric-cell">Valeur estimée</th><th scope="col" className="numeric-cell">Profit potentiel</th><th scope="col" className="numeric-cell">ROI</th><th scope="col" className="numeric-cell">Score</th><th scope="col"><span className="sr-only">Détail</span></th></tr></thead><tbody>{rows.map((row) => <tr key={row.id}>
    <td><Link className="item-name-link" href={`/items/${encodeURIComponent(row.id)}`}><span className="item-token">{(row.weapon ?? "CS2").slice(0, 3)}</span><span><strong>{row.weapon && row.skin ? `${row.weapon} | ${row.skin}` : row.market_hash_name}</strong><small>{row.exterior ?? "Exterior inconnu"}{row.stickers.length > 0 ? <span className="sticker-count">{row.stickers.length} sticker{row.stickers.length > 1 ? "s" : ""}</span> : null}</small></span></Link></td>
    <td><MarketBadge platform={row.platform} /></td>
    <td className="numeric-cell muted">{money(row.price_original, row.currency_original)}</td>
    <td className="numeric-cell strong">{money(row.price_eur_reference)}</td>
    <td className="numeric-cell mono">{row.float_value ? Number(row.float_value).toFixed(5) : "—"}{row.float_score !== null ? <small className="float-note">Score float {Math.round(row.float_score)}</small> : null}</td>
    <td className="numeric-cell" title={row.estimated_value_eur === null ? "Historique fiable insuffisant pour estimer la valeur." : "Estimation non garantie."}>{money(row.estimated_value_eur)}{row.confidence !== null ? <small className="cell-note">Confiance {Math.round(row.confidence)} %</small> : null}</td>
    <td className={`numeric-cell ${(numeric(row.potential_profit_eur) ?? 0) > 0 ? "positive" : ""}`} title={row.potential_profit_eur === null ? "Prix de revente ou frais effectifs manquants." : "Estimation selon les frais et hypothèses disponibles."}>{numeric(row.potential_profit_eur) !== null && Number(row.potential_profit_eur) > 0 ? "+" : ""}{money(row.potential_profit_eur)}</td>
    <td className={`numeric-cell ${(numeric(row.roi) ?? 0) > 0 ? "positive" : "muted"}`}>{percent(row.roi)}</td><td className="numeric-cell"><Score value={row.opportunity_score} /></td><td><Link className="row-link" href={`/items/${encodeURIComponent(row.id)}`} aria-label={`Analyser ${row.market_hash_name}`}><Icon name="arrow" size={16} /></Link></td>
  </tr>)}</tbody></table></div>;
}
