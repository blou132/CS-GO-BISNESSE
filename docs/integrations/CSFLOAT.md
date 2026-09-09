# CSFloat

- Statut : `OFFICIAL_API`
- Documentation officielle : <https://docs.csfloat.com/>
- Vérification : 8 septembre 2026
- Base : `https://csfloat.com/api/v1`

## API et authentification

L'adaptateur utilise `GET /listings` et `GET /listings/{id}`. La documentation
décrit l'en-tête `Authorization: <API-KEY>`. Bien que la page de la liste ne
marque pas explicitement ce GET comme authentifié, un appel de validation sans
clé a renvoyé HTTP 403 le 5 septembre 2026. L'adaptateur exige donc
`CSFLOAT_API_KEY` avant tout appel. Aucun endpoint d'écriture n'est appelé.

`GET /listings` expose notamment identifiant, état, type, prix en cents USD,
nom de marché, asset/def index, float, paint index/seed, StatTrak, Souvenir,
rareté, qualité, collection, références SCM, stickers et inspect link.
L'adaptateur accepte uniquement les annonces `buy_now` à l'état `listed`.
Les filtres officiels incluent notamment prix, float, paint seed/index,
collection, catégorie, stickers et nom de marché. Les tris documentés incluent
prix, date, float, `best_deal` et `float_rank`. `CSFloatSearch` regroupe ces
options dans trois stratégies bornées : `WATCHLIST`, `OPPORTUNITY_SCAN` et
`DISCOVERY` (20 résultats au maximum pour cette dernière).

## Limites

La première page est limitée à 50 annonces et la recherche emploie le
`market_hash_name` exact. La documentation consultée ne publie pas de quota
chiffré général ; le client espace ses requêtes, met les réponses en cache,
respecte `Retry-After` et borne les retries. Les prix sont des listings USD,
pas des ventes réalisées. Le contrat de normalisation, les filtres et les
erreurs ont été validés avec des fixtures HTTP. L'appel live sans clé a confirmé le refus
d'accès, mais aucune collecte d'annonce réelle n'est revendiquée faute de clé
personnelle.
