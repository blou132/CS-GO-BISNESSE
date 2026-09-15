import { dateTime, money, observationLabel } from "@/lib/format";
import type { EvidenceSource, ValuationProvenance } from "@/lib/realtime-types";

function SourceRow({ entry, role }: { entry: EvidenceSource; role: string }) {
  return <tr>
    <td>{role}<small>{entry.platform} · {observationLabel(entry.kind)} {entry.window ?? ""}</small></td>
    <td>{entry.external_id ?? entry.record_id ?? "Inconnu"}</td>
    <td>{entry.currency ? money(entry.price_original, entry.currency) : "Inconnu"}<small>{money(entry.value_eur)} référence</small></td>
    <td>{dateTime(entry.observed_at)}<small>{entry.timestamp_basis === "feed_observed_at" ? "Réception du flux" : "Horodatage source / observation"}</small></td>
    <td>{entry.fx_source ?? "Inconnue"}<small>{dateTime(entry.fx_timestamp)}</small></td>
    <td>{entry.volume ?? "Inconnu"}</td>
  </tr>;
}

export function Provenance({ value }: { value: ValuationProvenance }) {
  return <section className="evidence-section" aria-label="Provenance de la valorisation">
    <div className="panel-heading"><h2>Provenance de la valorisation</h2><strong>{value.eligibility === "DEMO" ? "Simulation DEMO" : "Référence seule, gain non validé"}</strong></div>
    <dl className="stream-metrics">
      <div><dt>Échantillon de référence</dt><dd>{value.reference_sample_size}</dd></div>
      <div><dt>Comparables float</dt><dd>{value.comparable_count} / minimum {value.float_min_samples}</dd></div>
      <div><dt>Percentile float</dt><dd>{value.float_status === "AVAILABLE" ? "Disponible" : "Données insuffisantes"}</dd></div>
      <div><dt>Frais effectifs</dt><dd>{value.fee_status === "DEMO_SYNTHETIC" ? "Synthétiques, 10 % en DEMO" : "Inconnus"}</dd></div>
      <div><dt>FX effectif</dt><dd>Inconnu</dd></div>
    </dl>
    <div className="table-scroll" tabIndex={0} role="region" aria-label="Sources du prix, tableau défilant"><table className="evidence-table"><thead><tr><th scope="col">Rôle / source</th><th scope="col">Identifiant</th><th scope="col">Prix</th><th scope="col">Fraîcheur</th><th scope="col">FX de référence</th><th scope="col">Volume</th></tr></thead><tbody>
      <SourceRow entry={value.buy} role="Achat affiché" />
      {value.reference.map((entry, index) => <SourceRow key={`${entry.record_id}-${index}`} entry={entry} role="Référence retenue" />)}
    </tbody></table></div>
    {value.reference_sample_size > value.reference.length ? <p className="panel-heading-note">{value.reference.length} sources affichées sur {value.reference_sample_size} observations retenues.</p> : null}
  </section>;
}
