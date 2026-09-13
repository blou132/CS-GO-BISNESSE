# Scanner paginé

`GET /api/scanner` est l'endpoint de lecture destiné aux grands volumes. Le
dashboard reste une synthèse courte et le scanner ne filtre plus la collection
complète dans le navigateur.

## Contrat

Paramètres de pagination :

- `mode=live|demo` ;
- `page` commence à 1 ;
- `page_size` accepte 10 à 100, avec 50 par défaut ;
- `sort` accepte `opportunity`, `profit`, `roi`, `risk`, `liquidity`,
  `confidence`, `price`, `float`, `spread`, `discount` ou `recent`.

Filtres exacts : `market`, `weapon`, `exterior`, `currency`, `paint_seed` et
`pattern_type`. `skin` est une recherche partielle insensible à la casse. Les
bornes numériques disponibles sont `min_price`, `max_price`, `min_profit`,
`min_roi`, `max_float`, `min_score`, `min_liquidity`, `min_confidence`,
`max_risk` et `max_spread`.

La réponse contient `items`, `total`, `page`, `page_size`, `pages`, les
`facets` globales du mode et les avertissements. Une métrique inconnue est
`null`. Un filtre analytique exclut donc naturellement une annonce dont le
snapshot n'est pas encore calculé.

## Scalabilité

Les tris analytiques lisent `listing_analysis_snapshots`, recalculé après les
synchronisations réussies. La requête reste paramétrée par SQLAlchemy et
applique `LIMIT/OFFSET` dans PostgreSQL. Les index couvrent les principaux
chemins de tri et de filtre.

Validation synthétique du 12 septembre 2026 sur PostgreSQL 17 : 100 000
annonces et 100 000 snapshots, 50 premières lignes en 0,68 s, puis 100 lignes
à la page 250 d'un ensemble filtré de 25 080 lignes en 0,58 s. Ces mesures
locales vérifient le comportement, pas un SLA de production.
