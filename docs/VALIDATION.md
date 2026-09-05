# Validation — 5 septembre 2026

## Environnement de contrôle

- Windows, Python 3.13.7 et uv 0.12.10
- Node.js 26.8.1 et npm 11.19.0
- PostgreSQL 17.11 local temporaire, limité à `127.0.0.1:55432`
- Docker Compose 5.5.1 pour la validation du manifeste

Les outils et données temporaires sont rangés dans `.tools/`, ignoré par Git.
Aucun secret réel n'a été utilisé.

## Backend

| Contrôle | Résultat |
| --- | --- |
| `ruff check apps/api` | Succès |
| `ruff format --check apps/api` | 35 fichiers conformes |
| `mypy apps/api/app` | Succès, 29 fichiers |
| `pytest apps/api/tests -q` | 14 tests réussis |
| Alembic `downgrade base` puis `upgrade head` | Succès sur PostgreSQL 17.11 |
| Alembic `current` | `310b4bb61557 (head)` |
| Alembic `check` | Aucune opération manquante |
| Healthcheck `/health/ready` | `200`, `status: ok` |
| Calcul de profit API | 102 EUR de coût, 14 EUR net, ROI 13,72549 % pour le cas contrôlé |

Pytest signale deux avertissements de dépréciation provenant de FastAPI/
Starlette et de leurs dépendances de test. Ils ne concernent pas le code du
projet et aucun test n'est ignoré.

## Frontend

| Contrôle | Résultat |
| --- | --- |
| `npm test -- --run` | 2 tests réussis |
| `npm run lint` | Succès |
| `npm run typecheck` | Succès, routes Next.js générées |
| `npm run build` | Succès, 8 routes produites |
| Serveur standalone de production | Page et feuille CSS en HTTP 200 |
| `npm audit --audit-level=high` | 0 vulnérabilité connue |

Le serveur standalone renvoie aussi les en-têtes `nosniff`, `DENY` et
`no-referrer` configurés. La vérification navigateur a couvert le dashboard, le scanner, le filtre de
profit, le détail d'un objet, la page Marchés et une fenêtre mobile de 390 px.
La démo contient 16 listings synthétiques CSFloat/DMarket et huit agrégats
Skinport synthétiques. L'étiquette DEMO, la nature des observations et les
limites de calcul restent visibles. Aucune erreur console n'a été relevée.

## Intégrations live

- Skinport : appel officiel `GET /v1/items` réussi en HTTP 200. L'agrégat est
  stocké comme `AGGREGATE`, sans inventer de listing individuel.
- CSFloat : l'appel sans clé a renvoyé HTTP 403 lors de la recherche initiale.
  L'adaptateur exige maintenant `CSFLOAT_API_KEY` avant tout appel ; aucune
  annonce réelle n'est revendiquée.
- DMarket : signature Ed25519 et réponse V2 validées par fixtures HTTP. Aucun
  appel réel n'a été fait faute de clés personnelles.

## Infrastructure

`docker compose --env-file .env config --quiet` valide les services `db`,
`api` et `web`, y compris la substitution des variables. Le moteur Docker
n'est pas installé sur la machine de contrôle : la construction et le
démarrage effectifs des images n'ont donc pas pu être exécutés ici.
