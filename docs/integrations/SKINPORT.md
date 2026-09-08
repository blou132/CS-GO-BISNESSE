# Skinport

- Statut : `PARTIAL`
- Documentation officielle : <https://docs.skinport.com/items>
- Historique officiel étudié : <https://docs.skinport.com/sales/history>
- Vérification : 8 septembre 2026
- Base : `https://api.skinport.com/v1`

## API et authentification

Le MVP appelle `GET /items` sans authentification, avec `app_id=730`,
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
7, 30 et 90 jours). Elles doivent être persistées dans un modèle dédié plutôt
que transformées en ventes unitaires.

Le Sale Feed officiel utilise Socket.IO avec un parser MessagePack et publie
des événements `listed` et `sold`. `price_changed` et `canceled` ne sont pas
supportés. Son normaliseur peut alimenter le pipeline commun, mais le transport
doit être validé séparément avant activation 24/7.

Les contrats ont été validés sur fixtures HTTP et un appel live
de `GET /items` a réussi en HTTP 200 le 5 septembre 2026. L'observation ainsi
collectée reste un agrégat et n'est jamais présentée comme une vente unitaire.
