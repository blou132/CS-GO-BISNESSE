# CS2 Arbitrage Hub

Application web privée d'observation des marchés de skins Counter-Strike 2.
Cette première base normalise des listings, conserve leur provenance,
compare les observations disponibles et sépare explicitement prix affiché,
vente réalisée, estimation et profit. Elle n'effectue aucun achat ni trade.

## Démarrage avec Docker Compose

Prérequis : Git et Docker Desktop avec Compose.

```powershell
git clone https://github.com/blou132/CS-GO-BISNESSE.git
cd CS-GO-BISNESSE
Copy-Item .env.example .env
```

Remplacez `replace-with-local-password` dans `.env` par un mot de passe local
URL-safe. Générez ensuite le hash du mot de passe administrateur sans écrire
le mot de passe brut dans le fichier :

```powershell
python scripts/generate-admin-password-hash.py
```

Placez la sortie entre quotes simples dans `ADMIN_PASSWORD_HASH`, puis
renseignez un `SESSION_SECRET` aléatoire d'au moins 32 caractères. Lancez :

```powershell
docker compose up --build
```

Ouvrez <http://127.0.0.1:3000/login>. L'API est disponible sur
<http://127.0.0.1:8000/docs>. Les ports écoutent uniquement sur la boucle
locale et PostgreSQL n'est pas publié sur la machine hôte.

Au premier démarrage, le conteneur API applique la migration Alembic avant
de servir les requêtes. Vérifiez l'état avec :

```powershell
docker compose ps
Invoke-RestMethod http://127.0.0.1:8000/health/ready
```

Pour arrêter les processus en conservant la base :

```powershell
docker compose down
```

`docker compose down -v` supprime aussi les données PostgreSQL ; ne l'utilisez
que lorsque cette suppression est voulue.

## Modes de données

Le site s'ouvre en mode `LIVE`. Il ne bascule jamais silencieusement sur des
données fictives. Une synchronisation live demande un nom de skin et appelle
les API officielles configurées. Une plateforme indisponible ne bloque pas
les résultats déjà stockés des autres sources.

Le bouton **Charger la démo** initialise des fixtures synthétiques dans un mode
de stockage distinct. Chaque écran et chaque ligne portent la mention DEMO.
Les ventes, frais et scores de ce mode servent uniquement à vérifier le
parcours ; ils n'ont aucune valeur de marché.

## Configuration

Pour saisir les cles marketplace sans les publier ni modifier la production :
[workflow interactif V0.12](docs/SECURITY.md). Les validations authentifiees restent
distinctes des tests sur fixtures ; voir le
[rapport de cloture du 20 septembre](docs/LIVE_CREDENTIALS_REPORT_2026-09-20.md).

Toutes les variables sont décrites dans [.env.example](.env.example).

| Variable | Requise | Usage |
| --- | --- | --- |
| `POSTGRES_PASSWORD` | Docker | Mot de passe PostgreSQL local |
| `DATABASE_URL` | Hors Compose | Connexion SQLAlchemy PostgreSQL |
| `MARKET_SYNC_ENABLED` | Facultative | Active le monitoring périodique quand `true` |
| `MARKET_SYNC_QUERY` | Avec monitoring | Nom de skin collecté en continu |
| `CSFLOAT_SYNC_INTERVAL_SECONDS` | Facultative | Intervalle du scheduler CSFloat |
| `SKINPORT_SYNC_INTERVAL_SECONDS` | Facultative | Intervalle du scheduler Skinport |
| `SKINPORT_REALTIME_ENABLED` | Facultative | Flux optionnel, `false` par defaut ; validation live encore bloquee |
| `SKINPORT_REALTIME_PRICE_UNIT*` | Avec flux | Unite et source verifiees avant toute ingestion |
| `FLOAT_MIN_SAMPLES` | Facultative | Minimum de comparables pour le percentile, 5 par defaut |
| `DMARKET_SYNC_INTERVAL_SECONDS` | Facultative | Intervalle du scheduler DMarket |
| `CSFLOAT_API_KEY` | CSFloat live | Clé API transmise côté serveur |
| `DMARKET_PUBLIC_KEY` | DMarket | Clé publique Ed25519 |
| `DMARKET_SECRET_KEY` | DMarket | Clé privée Ed25519, serveur uniquement |
| `FX_USD_EUR_RATE` | Facultative | EUR pour 1 USD, taux de référence |
| `FX_RATE_SOURCE` | Avec taux FX | Source explicite du taux |
| `FX_RATE_TIMESTAMP` | Avec taux FX | Date ISO 8601 avec fuseau |
| `FX_REFERENCE_SYNC_ENABLED` | Facultative | Collecte read-only des taux BCE quotidiens |
| `FX_REFERENCE_SYNC_INTERVAL_SECONDS` | Facultative | Intervalle de vérification BCE, 6 heures par défaut |
| `API_BASE_URL` | Frontend | Adresse privée du backend |
| `ADMIN_USERNAME` | Frontend | Identifiant de l'administrateur unique |
| `ADMIN_PASSWORD_HASH` | Frontend | Hash Scrypt généré par le script du projet |
| `SESSION_SECRET` | Frontend | Signature HMAC des sessions, 32 caractères minimum |
| `SESSION_COOKIE_SECURE` | Frontend | Ajoute `Secure` au cookie lorsque l'accès utilise HTTPS |
| `SESSION_TTL_SECONDS` | Facultative | Durée de session, 8 heures par défaut |
| `LOGIN_RATE_LIMIT_*` | Facultative | Seuil et fenêtre de limitation des connexions |

Sans taux USD/EUR complet, les montants USD gardent leur prix et devise
originaux mais leur valeur EUR reste `null`. Un taux de référence ne devient
jamais un coût de change effectif.

## Développement sans Docker

Backend (Python 3.12+ et PostgreSQL requis) :

```powershell
py -3.13 -m pip install --user uv
cd apps/api
uv sync --extra dev
$env:DATABASE_URL = "postgresql+psycopg://cs2:mot-de-passe@127.0.0.1:5432/cs2"
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --host 127.0.0.1
```

Frontend (Node.js 20.9+ ; Node 24 LTS recommandé) :

```powershell
cd apps/web
npm ci
npm run dev
```

## Validation

```powershell
cd apps/api
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run mypy app
cd ..\web
npm test
npm run lint
npm run typecheck
npm run build
```

La configuration Compose peut être vérifiée sans lancer les images avec
`docker compose config`. L'état exact des contrôles exécutés lors de cette
livraison figure dans [docs/VALIDATION.md](docs/VALIDATION.md).

## Déploiement Linux 24/7

La surcharge `compose.production.yml` conserve la stack de développement et
ajoute l'exécution production, les réseaux isolés, le durcissement des
conteneurs, les logs bornés et un port frontend configurable. La configuration
se trouve dans `.env.production`, ignoré par Git.

Sur le serveur, l'administrateur met d'abord le dépôt à jour avec Git, puis le
script déploie exactement le commit présent localement. Il ne fait pas de
`git pull` automatique.

Après avoir copié et renseigné `.env.production` :

```bash
./scripts/deploy.sh
```

La procédure complète, les migrations uniques, les sauvegardes, la
restauration et le rollback sont décrits dans
[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

Le monitoring continu est désactivé par défaut. Pour l'activer, définir
`MARKET_SYNC_ENABLED=true` et `MARKET_SYNC_QUERY` côté serveur. L'écran
Marchés affiche ensuite l'état de chaque plateforme, la prochaine exécution,
les compteurs de synchro et les métriques persistées. Voir
[docs/MARKET_MONITORING.md](docs/MARKET_MONITORING.md).

L'accès applicatif passe par `/login`. Toutes les pages et API métier sont
protégées par une session signée, avec vérification supplémentaire dans les
handlers API privés. `/api/health` reste public pour Docker et les contrôles
d'exploitation. Le mot de passe brut n'est jamais stocké par l'application.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Déploiement Linux](docs/DEPLOYMENT.md)
- [Validation serveur](docs/SERVER_VALIDATION.md)
- [Monitoring marché 24/7](docs/MARKET_MONITORING.md)
- [Modèle de données](docs/DATA_MODEL.md)
- [Price Engine V2](docs/PRICE_ENGINE.md)
- [Scanner paginé](docs/SCANNER_API.md)
- [Watchlist persistante](docs/WATCHLIST.md)
- [Rapport data et validation du 13 septembre 2026](docs/DATA_MARKETS_REPORT_2026-09-13.md)
- [Rapport sources, SkinSniper et valorisation du 14 septembre 2026](docs/SOURCES_VALUATION_REPORT_2026-09-14.md)
- [Currency, Fee and Profit Engine](docs/FINANCE_ENGINE.md)
- [Roadmap](docs/ROADMAP.md)
- [Audit initial](docs/AUDIT.md)
- [Intégrations officielles](docs/integrations/)

L'authentification administrateur ne remplace pas TLS ni un contrôle d'accès
réseau. L'application reste destinée à une exposition privée uniquement.
