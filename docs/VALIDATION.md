# Validation — 6 septembre 2026

## Environnement de contrôle

- Windows, Python 3.13.7 et uv 0.12.10 ;
- Node.js 26.8.1 et npm 11.19.0 ;
- PostgreSQL 17.11 local temporaire, limité à `127.0.0.1:55432` ;
- Docker Compose 5.5.1 pour la validation statique des manifestes ;
- Chromium piloté par agent-browser 0.36.0 pour le contrôle visuel.

Les outils, données et captures temporaires sont dans `.tools/` ou
`artifacts/`, ignorés par Git. Aucun secret réel n'a été utilisé.

## Backend

| Contrôle | Résultat |
| --- | --- |
| `ruff check apps/api` | Succès |
| `ruff format --check apps/api` | 38 fichiers conformes |
| `mypy apps/api/app` | Succès, 30 fichiers |
| `pytest apps/api/tests -q` | 18 tests réussis |
| Alembic `upgrade`, `downgrade` puis `upgrade head` | Succès sur PostgreSQL 17.11 |
| Alembic `current` | `7d9e1c84b2f0 (head)` |
| Alembic `check` | Aucune opération manquante |
| Conservation pendant la migration | 16 objets, 16 annonces, 138 observations et 6 états conservés |
| `/health/live` | Processus API en HTTP 200 |
| `/health/ready` | PostgreSQL joignable en HTTP 200 ; test dédié en HTTP 503 lors d'une panne simulée |
| `/health/status` | API, base et trois marketplaces séparées, sans clé ou secret |

Pytest signale deux avertissements de dépréciation provenant de FastAPI/
Starlette et de leurs dépendances de test. Ils ne concernent pas le code du
projet et aucun test n'est ignoré.

## Frontend

| Contrôle | Résultat |
| --- | --- |
| `npm test` | 2 tests réussis |
| `npm run lint` | Succès |
| `npm run typecheck` | Succès, routes Next.js générées |
| `npm run build` | Succès, 9 routes produites dont `/api/health` |
| Serveur standalone de production | HTML, CSS et JavaScript en HTTP 200 |
| `npm audit --audit-level=high` | 0 vulnérabilité connue |

La vérification navigateur a couvert la page Marchés en desktop et à 390 px.
Elle confirme l'affichage réel de l'API, de PostgreSQL, des états externes, du
dernier essai, du dernier succès et de la dernière erreur. Le passage explicite
en mode DEMO conserve son avertissement et ses données isolées. Aucune erreur
navigateur n'a été relevée.

## Infrastructure et scripts

| Contrôle | Résultat |
| --- | --- |
| Compose développement `config --quiet` | Succès |
| Compose développement + production `config --quiet` | Succès |
| Modèle Compose production JSON | Réseaux, ports, volume, dépendances, commandes et durcissement conformes |
| `bash -n` sur les scripts | Succès |
| `scripts/tests/backup-common-test.sh` | Succès |
| `git diff --check` | Succès |

Le test du modèle fusionné confirme notamment que PostgreSQL et FastAPI ne
publient aucun port, que le frontend écoute sur `127.0.0.1:3000`, que le réseau
PostgreSQL est interne, que le volume nommé est conservé et que la commande API
production ne lance ni Alembic ni reload.

Le moteur Docker n'est pas installé sur cette machine. Les images n'ont donc
pas été construites ni démarrées dans des conteneurs ici. `pg_dump`,
`pg_restore`, les healthchecks Docker, le système de fichiers en lecture seule,
la rotation `json-file` et le script de déploiement complet restent à valider
sur la machine Linux disposant de Docker Engine.

## Intégrations live

Les appels live du 5 septembre n'ont pas été rejoués pendant cette passe :

- Skinport avait répondu en HTTP 200 via son endpoint officiel et son agrégat
  avait été stocké comme `AGGREGATE` ;
- CSFloat exige une clé absente de l'environnement de contrôle ;
- DMarket reste validé par fixtures signées, sans appel personnel faute de
  clés.

L'endpoint système a exposé ces limites comme `unavailable` ou `stale`, sans
les convertir en état ONLINE et sans rendre l'application unhealthy.
