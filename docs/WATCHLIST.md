# Watchlist persistante

La page `/watchlist` permet de créer, modifier, mettre en pause et supprimer
des règles stockées dans PostgreSQL (`watch_rules`). Le mode fait partie de
chaque lecture et écriture : une règle DEMO reste invisible et inaccessible
en LIVE, y compris si son identifiant est connu.

## Filtres

Chaque règle cible un `market_hash_name` exact, avec exterior si celui-ci fait
partie du nom. Les conditions optionnelles se combinent par ET : marché,
prix maximal en EUR, float maximal, phase Doppler et liste de paint seeds.
Les plafonds sont inclusifs. La liste de seeds utilise une correspondance OU
entre ses valeurs, accepte 0 à 1000 et au plus 100 entrées.

Un prix EUR ou un float inconnu est exclu lorsqu'un plafond correspondant est
actif. Aucun premium de phase, de pattern ou de sticker n'est inventé.
Les montants restent des `Decimal` dans le backend et des chaînes exactes dans
le JSON des règles. Les requêtes utilisent les filtres paramétrés du scanner,
ses snapshots d'analyse et sa pagination SQL (100 annonces maximum par page).

## API

Toutes les routes acceptent `mode=live|demo` (LIVE par défaut).

| Méthode | Chemin | Fonction |
| --- | --- | --- |
| GET | `/api/watchlist` | Liste paginée, `page`, `page_size` de 1 à 100 |
| POST | `/api/watchlist` | Création d'une règle |
| PUT | `/api/watchlist/{id}` | Remplacement des propriétés d'une règle |
| DELETE | `/api/watchlist/{id}` | Suppression explicite, réponse 204 |
| GET | `/api/watchlist/{id}/matches` | Annonces correspondantes, `page`, `page_size`, `sort` |

Le proxy Next.js exige une session administrateur pour toutes ces routes,
contrôle l'origine des mutations et accepte uniquement un corps JSON pour
POST/PUT. Les erreurs internes de l'API ne sont jamais transmises au navigateur.
FastAPI reste dans le réseau privé du projet selon la configuration existante.

Une règle en pause reste consultable/modifiable mais ne produit pas de
correspondances (HTTP 409). La suppression demande confirmation dans l'interface.

## Périmètre actuel

Les correspondances portent sur les annonces déjà collectées. Enregistrer une
règle ne lance ni une requête marketplace, ni une transaction, ni une alerte
externe. Le scheduler existant garde sa configuration. La rotation de collecte
sur les règles actives et les notifications restent à raccorder explicitement.

## Vérification

`tests/test_watchlist.py` couvre la persistance, les plafonds, la précision,
les seeds, la pagination, le mode, les pauses et les entrées invalides.
Les tests frontend couvrent la session, l'origine, les paramètres, les erreurs
internes et la saisie des seeds.

`scripts/tests/watchlist-browser.mjs` est un scénario Playwright réservé à
une pile temporaire localhost. Il reçoit `CS2_TEST_PASSWORD` dans son
environnement, crée uniquement une règle DEMO et supprime sa propre règle en
fin de test. Il vérifie le rechargement, les modes, les correspondances, la
pause, la suppression et les viewports 1440, 390 et 360 px.
