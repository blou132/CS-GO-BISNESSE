# Skinport

- Statut : `PARTIAL`
- Documentation officielle : <https://docs.skinport.com/items>
- Historique officiel étudié : <https://docs.skinport.com/sales/history>
- Vérification : 8 septembre 2026
- Base : `https://api.skinport.com/v1`

## API et authentification

L'adaptateur appelle `GET /items` sans authentification, avec `app_id=730`,
`currency=EUR`, `tradable=true` et l'en-tête Brotli obligatoire
`Accept-Encoding: br`. L'endpoint fournit des prix et quantités agrégés par
`market_hash_name`, pas les exemplaires individuels avec leur float ou seed.

La réponse est enregistrée comme `AGGREGATE`. `quantity` désigne l'offre
présente et n'est donc pas transformé en volume de ventes. Aucun identifiant
d'annonce n'est inventé.

## Quotas et limites

La documentation officielle annonce 8 requêtes par 5 minutes et un cache de
5 minutes. L'adaptateur utilise un TTL de 5 minutes et un intervalle minimal
de 38 secondes entre appels de ce fournisseur. Brotli est pris en charge par
la dépendance HTTP du backend.

`GET /sales/history` fournit des statistiques agrégées par fenêtres (24 h,
7, 30 et 90 jours). L'adaptateur normalise min/max/moyenne/médiane/volume dans
`AggregateMarketStat`; aucune transaction unitaire n'est créée depuis cet
endpoint. Une synchronisation ciblée demande uniquement l'historique des noms
exacts retenus par la recherche, par groupes bornés à 20.

Le Sale Feed officiel utilise Socket.IO avec un parser MessagePack et publie
des événements `listed` et `sold`. `price_changed` et `canceled` ne sont pas
supportés. Son normaliseur typé alimente le contrat commun en listings exacts
ou ventes réalisées à partir du `saleId`. Le transport Socket.IO/MessagePack,
la reconnexion et la file bornée ne sont pas activés : ils doivent être validés
séparément avant toute exécution 24/7.

Les contrats REST et le normaliseur du feed ont été validés sur fixtures. Un appel live
de `GET /items` a réussi en HTTP 200 le 5 septembre 2026. L'observation ainsi
collectée reste un agrégat et n'est jamais présentée comme une vente unitaire.
