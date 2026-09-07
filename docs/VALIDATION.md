# Validation — 6 septembre 2026

## Environnement de contrôle

- Linux, Python 3.12.3 ;
- environnement Python temporaire : `/tmp/cs2-arbitrage-api-venv` ;
- Docker 29.8.0 et Docker Compose 5.5.1 ;
- image Node `node:24-alpine` utilisée en conteneur jetable pour le frontend ;
- aucune clé CSFloat ou DMarket réelle ;
- aucun démarrage applicatif persistant et aucun déploiement serveur.

Aucun secret réel n'a été utilisé. Les conteneurs existants du serveur n'ont
pas été modifiés ou arrêtés.

## Backend

| Contrôle | Résultat |
| --- | --- |
| `python3 -m compileall apps/api/app apps/api/tests` | Succès |
| `ruff format --check .` depuis `apps/api` | 43 fichiers conformes |
| `ruff check .` depuis `apps/api` | Succès |
| `mypy app` depuis `apps/api` | Succès, 32 fichiers |
| `pytest` depuis `apps/api` | 25 tests réussis |
| Alembic `upgrade head` | Succès sur SQLite temporaire |
| Alembic `downgrade -1` puis `upgrade head` | Succès |
| Alembic `check` | Aucune opération manquante |

Pytest signale deux avertissements de dépréciation issus de FastAPI/Starlette
dans l'environnement de test. Aucun test n'est ignoré.

Les tests couvrent notamment :

- séparation DEMO/LIVE ;
- `/health/live`, `/health/ready`, `/health/status` ;
- adaptateurs CSFloat, Skinport et DMarket sur fixtures ;
- absence de requête sans clé CSFloat ;
- signature DMarket sans fuite de secret ;
- agrégats Skinport conservés comme `AGGREGATE` ;
- absence de retry agressif après HTTP 429 ;
- configuration du scheduler ;
- verrou par marketplace ;
- statuts `not_configured`, `stale` et `very_stale` ;
- upsert de listings et déduplication d'observations identiques ;
- persistance non destructive des listings ;
- opportunités persistées après recalcul ;
- validation des réglages `MARKET_SYNC_*`.

## Frontend

La machine n'avait ni `node` ni `npm` installés localement. Les validations ont
donc été exécutées dans un conteneur jetable `node:24-alpine`, avec le dossier
`apps/web` monté en lecture seule puis copié dans `/tmp/work` du conteneur.

| Contrôle | Résultat |
| --- | --- |
| `npm ci` | Succès, 0 vulnérabilité pendant l'installation |
| `npm test` | 5 tests réussis |
| `npm run lint` | Succès |
| `npm run typecheck` | Succès, routes Next générées |
| `npm audit --audit-level=high` | 0 vulnérabilité connue |

Le `docker compose build` a également exécuté `npm run build` dans le Dockerfile
frontend. Next.js a compilé avec succès et a produit les routes :

- `/` ;
- `/scanner` ;
- `/markets` ;
- `/items/[id]` ;
- `/api/dashboard` ;
- `/api/health` ;
- `/api/market-monitor` ;
- `/api/sync` ;
- `/api/items/[id]`.

## Docker et Compose

| Contrôle | Résultat |
| --- | --- |
| `docker compose -f docker-compose.yml -f compose.production.yml config --quiet` avec mot de passe factice | Succès |
| `docker compose ... build` avec `IMAGE_TAG=validation` | Succès |

Le build a validé les deux images projet :

- `cs2-arbitrage-hub-api:validation` ;
- `cs2-arbitrage-hub-web:validation`.

Il n'y a pas eu de `docker compose up`, pas de migration sur une base réelle,
pas d'arrêt de service existant et pas de modification réseau hôte.

## Scripts

Le script `scripts/deploy.sh` ne lance plus `git pull --ff-only`. Le workflow
attendu est désormais :

1. l'administrateur choisit le commit avec Git ;
2. le dépôt doit être propre ;
3. `./scripts/deploy.sh` construit et déploie exactement ce commit local.

La validation complète de `backup-db.sh`, `restore-db.sh`, du redémarrage après
reboot et de la restauration contrôlée doit être faite sur le serveur de
production avec la base réelle, selon `SERVER_VALIDATION.md`.

## Intégrations live

Les appels live aux marketplaces n'ont pas été rejoués pendant cette passe.

- CSFloat : clé absente, état attendu `not_configured`.
- DMarket : clés absentes, état attendu `not_configured`.
- Skinport : endpoint public disponible dans le code, données conservées comme
  agrégats uniquement.

Une marketplace non configurée, en erreur ou limitée par quota ne rend pas
`/health/ready` unhealthy.
