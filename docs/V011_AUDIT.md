# V0.11 : audit initial du 14 septembre 2026

Depart `d02e5ae`, branche `feat/mvp-foundations`, arbre propre, 24 commits
locaux non pousses. Rapport SOURCES_VALUATION du 14 septembre relu ainsi que
README, architecture, roadmap, monitoring, configurations et code existant.
Le fichier Compose de base s'appelle `docker-compose.yml`, pas `compose.yml`.

Sauvegarde complete verifiee par `git bundle verify` :
`/home/serve/backups/cs2-v011-20260914/before-d02e5ae.bundle`.
Repertoire prive 0700, historique Git uniquement ; aucun ajout d'env ou dump.
HEAD sauvegarde : `d02e5ae1e65bcd63e430a066f32aa02cfe9c3620`.

| Sujet | Etat initial | Suite utile |
| --- | --- | --- |
| CSFloat LIVE | BLOCKED_EXTERNAL | CSFLOAT_API_KEY absente, contrats et pagination testables |
| DMarket LIVE | BLOCKED_EXTERNAL | Les deux variables de cles sont absentes, signatures/erreurs testables |
| Skinport REST | DONE | Smoke reel precedent valide, conserver le pacing corrige |
| Skinport realtime | PARTIAL | Ancien normaliseur non conforme, aucun transport, queue ou receipt DB |
| Reference price | PARTIAL | Hierarchie/fraicheur presentes ; provenance par preuve a exposer |
| Liquidite | PARTIAL | Moteur teste, donnees live incompletes |
| Spread | PARTIAL | Protection bids conditionnels/perimes ; aucun spread executable garanti |
| Float comparables | PARTIAL | Groupe exact et dedup presentes ; seuil configurable manquant |
| Fees | DONE | Barremes sources/fraicheur/refus ambiguite ; validation DMarket live bloquee |
| FX | DONE | BCE reference/effectif separes ; smoke reel a refaire si utile |
| Opportunity traceability | PARTIAL | Sources globales, pas de detail exhaustif par preuve ; invalidation a renforcer |
| Scanner/watchlist/auth | DONE | Ne pas refaire, garder les tests de regression |

La presence des cles a ete verifiee avec un parseur dotenv sur un montage
read-only de la configuration prevue, sortie limitee aux noms et etats.
Le token GitHub poste dans le chat n'a pas ete utilise ni enregistre ; sa
revocation a ete demandee. Aucun credential en cache utilisable pour push.

Plan : contrat officiel + probe borne, normalisation prudente, ingestion
optionnelle bornee et idempotente, metriques REST/stream distinctes,
provenance/invalidation, validation complete sur pile temporaire. Aucun
deploiement en production ni modification des services tiers.
