# Validation — 7 septembre 2026

Rapport plus récent : [passe data, scanner et watchlist du 13 septembre](DATA_MARKETS_REPORT_2026-09-13.md).
Le présent document conserve les preuves historiques de la première mise en service.

## Environnement de contrôle

- hôte Linux `serve-projet` ;
- Docker Engine 29.8.0 et Docker Compose 5.5.1 ;
- Python 3.13 dans un conteneur jetable construit depuis `uv.lock` ;
- Node 24 et Playwright 1.58.2 dans des conteneurs jetables ;
- production permanente dans `/opt/cs2-arbitrage-hub` ;
- aucune clé CSFloat ou DMarket ;
- aucun changement UFW, Tailscale, DNS, DHCP, route, IP ou service tiers.

Au relevé final, la partition racine utilisait 60 Gio sur 937 Gio et 12 Gio
de mémoire étaient disponibles sur 15 Gio. Le seul port hôte publié par le
projet était `127.0.0.1:3000`.

## Backend

| Contrôle | Résultat |
| --- | --- |
| `pytest` | 25 tests réussis, 2 avertissements de dépendances |
| `ruff check .` | Succès |
| `ruff format --check .` | 43 fichiers conformes |
| `mypy app` | Succès, 32 fichiers |
| Alembic `upgrade head` | Succès sur SQLite temporaire |
| Alembic `check` | Aucune opération manquante |

La correction de monitoring vérifie désormais que les métriques live ne
comptent aucune ligne DEMO. Les tests couvrent aussi les healthchecks, les
adaptateurs, les erreurs de configuration, le scheduler, les verrous par
marketplace, la persistance et la déduplication des observations.

## Frontend et authentification

| Contrôle | Résultat |
| --- | --- |
| `npm ci` | Succès |
| `npm test` | 30 tests réussis |
| `npm run lint` | Succès |
| `npm run typecheck` | Succès |
| `npm run build` | Succès, proxy Next.js 16 inclus |
| `npm audit --audit-level=high` | 0 vulnérabilité connue |

Les tests V0.10 couvrent login valide/invalide, configuration invalide,
rotation d'identifiants contre le rate limit, session signée, expiration,
cookie `HttpOnly`/`SameSite`/`Secure`, routes page et API protégées, contrôle
serveur des API, origine des POST et logout.

Une image `cs2-arbitrage-hub-web:auth-validation` a été lancée temporairement
sur `127.0.0.1:3300`, reliée uniquement au réseau applicatif du projet. Le test
Playwright a confirmé :

- redirection anonyme de `/markets` vers `/login?next=/markets` ;
- connexion administrateur et chargement de la page Marchés réelle ;
- cookie `HttpOnly`, `SameSite=Lax`, expiration présente et `Secure=false`
  dans ce scénario HTTP ;
- déconnexion, suppression effective de la session et retour à `/login` ;
- absence de débordement horizontal à 390 × 844 ;
- absence d'erreur console ou erreur de page.

Le conteneur de validation a ensuite été supprimé. Le test a permis de corriger
deux problèmes avant livraison : une redirection logout construite depuis
`0.0.0.0:3000` et le cas Chromium `Origin: null`/`Sec-Fetch-Site: same-origin`
provoqué par la politique `no-referrer`.

## Docker et Compose

| Contrôle | Résultat |
| --- | --- |
| `docker compose ... config --quiet` avec secrets factices | Succès |
| build API `auth-validation` | Succès |
| build frontend `auth-validation` | Succès |
| frontend de validation en lecture seule | Succès |
| healthcheck de validation avec auth | API, base et auth healthy |

La configuration de production ne publie ni PostgreSQL ni FastAPI. Les trois
services ont `restart: unless-stopped`. Le healthcheck frontend appelle
désormais `/api/health` et échoue si les paramètres d'authentification sont
absents ou mal formés.

## Production réelle

Le premier déploiement permanent, la migration PostgreSQL, la persistance
après `docker compose down` sans `-v`, le redémarrage API/frontend, la
sauvegarde et une restauration contrôlée avec donnée témoin ont été exécutés
avec succès. Quatre dumps validés étaient présents, avec permissions 600 ; le
dernier était `cs2-20260907T114423Z-272992.dump` (37 330 octets).

L'état permanent conservé pendant la préparation V0.10 est le commit
`378b6f0494a042d434e42acd8b2dc014413eecb6`, avec API, frontend et PostgreSQL
healthy. La V0.10 n'a pas remplacé ce frontend : aucun mot de passe
administrateur de production n'a été fourni et le projet interdit de stocker
un mot de passe brut ou de fabriquer un identifiant inutilisable.
Le nouveau préflight a été exécuté contre cette configuration : il s'est arrêté
sur `ADMIN_USERNAME est absent ou vide` avant Compose, backup, build ou restart,
comme attendu.

## Monitoring live

Le scheduler 24/7 est actif avec un intervalle de 900 secondes. Au relevé du
7 septembre 2026 à 16:40 UTC :

- Skinport : `online`, 2 agrégats reçus, durée 1 036 ms ;
- CSFloat : `not_configured`, clé absente ;
- DMarket : `not_configured`, clés absentes ;
- métriques live : 0 listing, 42 observations de prix, 0 opportunité ;
- prochaine exécution annoncée : 16:55 UTC.

Skinport reste explicitement traité comme agrégat de prix et non comme annonce
individuelle. Les absences de clés restent informatives et ne rendent pas
PostgreSQL ou l'API unhealthy.

## Git et limite restante

Le dépôt de travail est sur `feat/mvp-foundations`. Le remote GitHub reste en
HTTPS ; `gh` n'est pas installé et la clé SSH présente n'est pas autorisée par
GitHub. Aucun credential n'a été fabriqué et aucun force-push n'a été tenté.

Pour activer la V0.10 en production, l'administrateur doit choisir son mot de
passe directement dans un terminal avec :

```bash
./scripts/generate-admin-password-hash.py \
  --env-file /opt/cs2-arbitrage-hub/.env.production \
  --username admin
```

Le script écrit
uniquement le hash, génère le secret de session et n'affiche aucune de ces
valeurs. Une fois ce choix humain effectué, `./scripts/deploy.sh` réalisera la
sauvegarde, le build, la migration, les healthchecks et le remplacement
contrôlé du frontend.
