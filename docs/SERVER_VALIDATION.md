# Validation serveur

Ce guide décrit les contrôles à exécuter sur le serveur Linux cible sans
modifier le réseau hôte. Il complète `DEPLOYMENT.md` pour le premier
déploiement réel dans `/opt/cs2-arbitrage-hub`.

## Préflight lecture seule

Depuis le serveur :

```bash
cd /opt/cs2-arbitrage-hub
git status --short --branch
docker version
docker compose version
docker compose --env-file .env.production \
  -f docker-compose.yml -f compose.production.yml config --quiet
```

Vérifier que `.env.production` existe, est privé et ne contient pas le mot de
passe d'exemple. Ne pas afficher les valeurs d'authentification :

```bash
ls -l .env.production
grep -n 'replace-with-local-password' .env.production && exit 1 || true
```

Ces commandes ne touchent ni UFW, ni Tailscale, ni DNS, ni routes, ni reverse
proxy existant.

## Premier déploiement

Le script ne fait pas de `git pull`. L'administrateur choisit donc le commit
avant de lancer :

```bash
cd /opt/cs2-arbitrage-hub
git fetch origin
git switch feat/mvp-foundations
git pull --ff-only
git status --short
./scripts/deploy.sh
```

Résultat attendu :

- images construites avec le hash du commit ;
- PostgreSQL démarré sur réseau Compose interne ;
- dump créé avant migration ;
- migration Alembic exécutée une seule fois ;
- API et frontend démarrés ;
- `/api/health` confirme API, PostgreSQL et authentification.

## Tests d'acceptation

```bash
docker compose --env-file .env.production \
  -f docker-compose.yml -f compose.production.yml ps
curl --fail http://127.0.0.1:3000/api/health
curl --silent --output /dev/null --write-out '%{http_code}\n' \
  http://127.0.0.1:3000/api/market-monitor
curl --silent --output /dev/null --write-out '%{http_code} %{redirect_url}\n' \
  http://127.0.0.1:3000/markets
docker compose --env-file .env.production \
  -f docker-compose.yml -f compose.production.yml logs --tail=100 api web db
```

Vérifier les ports publiés :

```bash
docker compose --env-file .env.production \
  -f docker-compose.yml -f compose.production.yml config | grep -A6 'ports:'
```

Production attendue :

- seul `web` publie un port hôte ;
- `APP_BIND_ADDRESS` vaut `127.0.0.1` sauf décision réseau séparée ;
- `db` ne publie aucun port hôte ;
- `api` ne publie aucun port hôte.

Sans session, `/api/market-monitor` doit répondre `401` et `/markets` doit
rediriger vers `/login`. Se connecter ensuite dans un navigateur et vérifier
Dashboard, Scanner, Marchés, un détail d'objet, puis le bouton de déconnexion.
Le cookie doit être `HttpOnly`, `SameSite=Lax`, posséder une expiration et ne
porter `Secure` que si `SESSION_COOKIE_SECURE=true`.

## Persistance

Créer une donnée de démonstration, redémarrer les conteneurs, puis vérifier
qu'elle existe toujours :

```bash
docker compose --env-file .env.production \
  -f docker-compose.yml -f compose.production.yml exec -T api \
  python -c "import urllib.request; urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:8000/api/sync?mode=demo', method='POST'), timeout=90).read()"
docker compose --env-file .env.production \
  -f docker-compose.yml -f compose.production.yml restart api web
docker compose --env-file .env.production \
  -f docker-compose.yml -f compose.production.yml exec -T api \
  python -c "import urllib.request; assert b'\"mode\":\"demo\"' in urllib.request.urlopen('http://127.0.0.1:8000/api/dashboard?mode=demo', timeout=10).read()"
```

Ce test ne valide pas le marché live ; il confirme le volume PostgreSQL.

## Sauvegarde

```bash
./scripts/backup-db.sh
ls -lh backups/postgres
```

Le dernier fichier doit être un `cs2-*.dump` sans suffixe `.partial`.

## Restauration contrôlée

À tester seulement sur une fenêtre de maintenance, car la restauration arrête
API et frontend pendant l'opération :

```bash
./scripts/restore-db.sh /chemin/absolu/du/dump.dump
```

Le script exige un terminal interactif et la saisie exacte de `RESTORE`.
Après restauration :

```bash
docker compose --env-file .env.production \
  -f docker-compose.yml -f compose.production.yml ps
curl --fail http://127.0.0.1:3000/api/health
```

## Test de redémarrage serveur

Ne redémarrer le serveur que pendant une fenêtre validée. Après reboot :

```bash
cd /opt/cs2-arbitrage-hub
export IMAGE_TAG="$(cat .deployment/current-image-tag)"
docker compose --env-file .env.production \
  -f docker-compose.yml -f compose.production.yml ps
curl --fail http://127.0.0.1:3000/api/health
```

Les services utilisent `restart: unless-stopped`. Si l'application a été
arrêtée volontairement avec `docker compose down`, elle ne repartira pas seule
au reboot sans nouvelle commande `up`.

## Contrôles à ne pas automatiser

Ce projet ne modifie pas :

- UFW ou nftables ;
- Tailscale ;
- SSH ;
- DNS, DHCP ou AdGuard ;
- netplan, NetworkManager ou systemd-networkd ;
- routes ou IPs ;
- reverse proxy existant ;
- port forwarding de box ou NAT.

Toute exposition autre que `127.0.0.1` doit être décidée et validée hors de ce
script.
