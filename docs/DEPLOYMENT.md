# Déploiement sur un serveur Linux

Cette procédure prépare une instance privée, permanente et mono-hôte de CS2
Arbitrage Hub avec Docker Engine et Docker Compose. Elle ne modifie ni le
pare-feu, ni le DNS, ni les routes, ni les services système du serveur.

## Prérequis

- une machine Linux avec Git, `curl`, `flock`, `realpath`, Docker Engine et le
  plugin Docker Compose ;
- un utilisateur autorisé à exécuter `docker compose` ;
- une version récente de Compose prenant en charge les tags de fusion
  `!reset` et `!override` ;
- de l'espace persistant pour le volume PostgreSQL, les images et les dumps ;
- un accès privé au port choisi. Le port `3000` écoute par défaut uniquement
  sur `127.0.0.1`.

Vérifier l'installation sans modifier l'hôte :

```bash
git --version
docker version
docker compose version
curl --version
```

Les commandes ci-dessous supposent que le dépôt se trouve dans
`/opt/cs2-arbitrage-hub`. Adaptez seulement ce chemin à votre installation.

## Configuration de production

Cloner le dépôt, sélectionner la branche et créer le fichier externe de
configuration :

```bash
git clone https://github.com/blou132/CS-GO-BISNESSE.git /opt/cs2-arbitrage-hub
cd /opt/cs2-arbitrage-hub
git switch feat/mvp-foundations
cp .env.example .env.production
chmod 600 .env.production
```

Dans `.env.production`, définir au minimum :

```dotenv
ENVIRONMENT=production
POSTGRES_PASSWORD=un-secret-long-et-unique
ADMIN_USERNAME=admin
ADMIN_PASSWORD_HASH='scrypt$...'
SESSION_SECRET=un-secret-aleatoire-distinct-de-32-caracteres-minimum
SESSION_COOKIE_SECURE=false
APP_BIND_ADDRESS=127.0.0.1
APP_PORT=3000
CORS_ORIGINS=http://127.0.0.1:3000
BACKUP_DIR=./backups/postgres
BACKUP_RETENTION_DAYS=14
```

Ajouter les clés CSFloat et DMarket seulement si elles sont disponibles.
Elles restent vides sinon ; l'interface indiquera `not_configured` sans
déclarer l'application unhealthy. Ne jamais placer `.env.production` ou les
dumps dans Git.
Le mot de passe PostgreSQL entre dans une URL de connexion : utilisez seulement
les lettres, chiffres et caractères `.` `_` `~` `-`, comme le vérifie le script.

Générer le hash administrateur dans un terminal interactif :

```bash
./scripts/generate-admin-password-hash.py
```

Le script demande deux fois le mot de passe sans l'afficher et écrit uniquement
le hash Scrypt. Copier cette sortie entre quotes simples dans
`ADMIN_PASSWORD_HASH`. Ne placez jamais le mot de passe brut dans un fichier,
une commande Docker, Git ou les logs. Générer séparément le secret de session,
par exemple avec `openssl rand -hex 32`.

Conserver `SESSION_COOKIE_SECURE=false` pour un accès HTTP direct sur la boucle
locale ou le LAN. Le passer à `true` seulement lorsque le navigateur rejoint
réellement l'application en HTTPS ; un cookie `Secure` n'est pas envoyé en HTTP.

`APP_BIND_ADDRESS=127.0.0.1` est le réglage initial recommandé. Le choix d'une
autre adresse et la protection du trafic doivent être décidés avec la
configuration réseau réelle du serveur.

La commande Compose de production utilisée dans toute cette page est :

```bash
docker compose --env-file .env.production \
  -f docker-compose.yml -f compose.production.yml
```

Le monitoring 24/7 est volontairement inactif par défaut. Pour collecter un
skin en continu, renseigner explicitement :

```dotenv
MARKET_SYNC_ENABLED=true
MARKET_SYNC_QUERY="AK-47 | Redline (Field-Tested)"
CSFLOAT_SYNC_INTERVAL_SECONDS=900
SKINPORT_SYNC_INTERVAL_SECONDS=900
DMARKET_SYNC_INTERVAL_SECONDS=900
```

Sans clés personnelles, CSFloat et DMarket restent `not_configured`. Skinport
reste un agrégat et n'est jamais présenté comme annonce individuelle.

## Premier déploiement

Le script vérifie Git, les paramètres d'authentification et Compose, construit
des images étiquetées avec le commit, démarre PostgreSQL, crée un dump, exécute
une seule migration Alembic, démarre l'API et le frontend, puis contrôle
l'endpoint système :

```bash
cd /opt/cs2-arbitrage-hub
chmod +x scripts/*.sh scripts/tests/*.sh
./scripts/deploy.sh
```

Le dump initial peut contenir une base vide ; il confirme que la chaîne de
sauvegarde fonctionne avant la première migration. Contrôler ensuite :

```bash
docker compose --env-file .env.production \
  -f docker-compose.yml -f compose.production.yml ps
curl --fail http://127.0.0.1:3000/api/health
```

La réponse distingue le processus API, PostgreSQL, l'authentification et l'état
observé des trois sources externes. Une configuration d'authentification
invalide rend le frontend unhealthy et bloque le déploiement. Une marketplace
en erreur ne rend pas l'API ou PostgreSQL unhealthy.

Ouvrir ensuite `http://127.0.0.1:3000/login`. Les pages, les API métier et les
actions sont protégées ; seul `/login`, `/api/login` et `/api/health` restent
publics. La session signée expire après `SESSION_TTL_SECONDS`, huit heures par
défaut. Cinq échecs de connexion sur quinze minutes déclenchent par défaut une
réponse HTTP 429. Ce compteur en mémoire convient à l'instance unique et repart
à zéro au redémarrage du frontend.

## Mise à jour

Depuis une copie propre de la branche, récupérer d'abord le code voulu :

```bash
cd /opt/cs2-arbitrage-hub
git fetch origin
git switch feat/mvp-foundations
git pull --ff-only
git status --short
./scripts/deploy.sh
```

Le script suit cet ordre :

1. refus d'un dépôt modifié ou non propre ;
2. validation de la configuration Compose ;
3. construction des images du commit local courant ;
4. attente de PostgreSQL et sauvegarde ;
5. migration Alembic dans un conteneur ponctuel unique ;
6. recréation des services persistants et attente de leurs healthchecks ;
7. requête HTTP sur `HEALTHCHECK_URL`.

Il s'arrête au premier échec. Il n'effectue ni reset Git, ni push, ni
pull Git, ni suppression de volume, ni modification du réseau de l'hôte. En
cas d'échec après une migration, examiner l'état avant toute restauration.
Un verrou `flock` empêche deux déploiements ou restaurations lancés depuis la
même copie du dépôt de s'exécuter en parallèle.

## Migrations Alembic

La commande permanente de l'API ne lance aucune migration. Cela évite que
plusieurs réplicas tentent de modifier le schéma en parallèle. Pour une mise à
jour manuelle, démarrer d'abord uniquement PostgreSQL, puis lancer exactement
un conteneur de migration :

```bash
export IMAGE_TAG="$(git rev-parse --short=12 HEAD)"
docker compose --env-file .env.production \
  -f docker-compose.yml -f compose.production.yml build
docker compose --env-file .env.production \
  -f docker-compose.yml -f compose.production.yml up -d --wait db
./scripts/backup-db.sh
docker compose --env-file .env.production \
  -f docker-compose.yml -f compose.production.yml \
  run --rm --no-deps api alembic upgrade head
docker compose --env-file .env.production \
  -f docker-compose.yml -f compose.production.yml \
  up -d --remove-orphans --wait
```

Ne lancez pas cette séquence depuis deux terminaux en même temps.

## Sauvegardes

PostgreSQL utilise le volume nommé `postgres_data`. Il survit à
`docker compose down`, mais le volume ne remplace pas une sauvegarde externe.

Créer un dump PostgreSQL au format custom :

```bash
cd /opt/cs2-arbitrage-hub
./scripts/backup-db.sh
```

Le fichier est d'abord écrit avec le suffixe `.partial`, validé par
`pg_restore --list`, puis renommé en
`cs2-AAAAMMJJTHHMMSSZ-identifiant.dump`. Le répertoire est défini par
`BACKUP_DIR`. Un chemin relatif est résolu depuis la racine du projet. Le
script refuse `/` et la racine du projet, refuse d'adopter un répertoire non
vide sans marqueur dédié et ne supprime que les fichiers `cs2-*.dump`
directement présents dans ce répertoire. `BACKUP_RETENTION_DAYS` vaut 14 par
défaut.

Copier régulièrement ces dumps vers un autre support protégé. La rotation
locale ne protège ni contre une panne de disque ni contre la perte du serveur.

## Restauration

La restauration remplace la base complète. Choisir explicitement un dump et
lancer la commande dans un terminal interactif :

```bash
cd /opt/cs2-arbitrage-hub
./scripts/restore-db.sh /chemin/absolu/cs2-20260906T120000Z.dump
```

Le script valide l'archive, affiche l'avertissement, puis exige la saisie
exacte de `RESTORE`. Il arrête l'API et le frontend, restaure PostgreSQL,
applique les migrations jusqu'à `head`, puis redémarre les services. Si
`pg_restore` échoue, l'API et le frontend restent arrêtés pour éviter de servir
une base partiellement restaurée.

Après restauration :

```bash
docker compose --env-file .env.production \
  -f docker-compose.yml -f compose.production.yml ps
curl --fail http://127.0.0.1:3000/api/health
```

## Logs

Afficher les derniers événements, puis suivre les nouveaux :

```bash
docker compose --env-file .env.production \
  -f docker-compose.yml -f compose.production.yml logs --tail=200
docker compose --env-file .env.production \
  -f docker-compose.yml -f compose.production.yml logs -f api web db
```

Le backend écrit des événements JSON avec timestamp, niveau, composant,
message et, lorsque pertinent, marketplace, route, événement
`sync_started`/`sync_completed`/`sync_failed`, statut, durée, compteurs et
code d'erreur. Il n'enregistre pas les clés API, mots de passe ou en-têtes
d'autorisation. Docker utilise le pilote `json-file`, limité par défaut à cinq
fichiers de 10 Mio par conteneur. Modifier `DOCKER_LOG_MAX_SIZE` et
`DOCKER_LOG_MAX_FILES` dans `.env.production` si nécessaire.
Le frontend journalise uniquement les événements d'authentification
(`login_success`, `login_failed`, `login_rate_limited`, `logout`) sans mot de
passe, hash ni jeton de session.

## Arrêt et redémarrage

Arrêter les conteneurs en conservant la base :

```bash
docker compose --env-file .env.production \
  -f docker-compose.yml -f compose.production.yml down
```

Redémarrer la version déjà construite :

```bash
export IMAGE_TAG="$(cat .deployment/current-image-tag)"
docker compose --env-file .env.production \
  -f docker-compose.yml -f compose.production.yml up -d --wait
```

Les trois services utilisent `restart: unless-stopped`. Ne lancez jamais
`docker compose down -v` sauf si la suppression définitive des données est
voulue et sauvegardée.

## Rollback manuel

Avant une mise à jour, noter le commit courant et conserver le dump créé par
le script. Les images sont étiquetées avec les douze premiers caractères du
commit et restent utilisables tant qu'elles n'ont pas été supprimées du cache
Docker.

1. Revenir au code précédent sans réécrire l'historique :

   ```bash
   git log --oneline -5
   git switch --detach <commit-precedent>
   export IMAGE_TAG="$(git rev-parse --short=12 HEAD)"
   ```

2. Si les deux images de ce tag existent encore, les relancer sans build :

   ```bash
   docker image inspect "cs2-arbitrage-hub-api:$IMAGE_TAG" \
     "cs2-arbitrage-hub-web:$IMAGE_TAG"
   docker compose --env-file .env.production \
     -f docker-compose.yml -f compose.production.yml up -d --wait
   ```

3. Si elles n'existent plus, reconstruire depuis ce commit avec
   `docker compose ... build`, puis relancer.

4. Si la version précédente ne sait pas lire le schéma migré, restaurer le
   dump créé avant la migration avec `IMAGE_TAG` réglé sur le commit précédent :

   ```bash
   IMAGE_TAG="$IMAGE_TAG" ./scripts/restore-db.sh /chemin/du/dump.dump
   ```

5. Vérifier `ps`, `/api/health` et les logs. Revenir ensuite sur la branche avec
   `git switch feat/mvp-foundations` avant une future mise à jour.

Une restauration perd les écritures effectuées après le dump. Elle ne doit
donc être utilisée que lorsque le rollback du schéma l'exige.

## Dépannage

- **Compose refuse `!reset` ou `!override`** : mettre à jour le plugin Docker
  Compose, puis relancer `docker compose version` et la validation `config`.
- **PostgreSQL reste unhealthy** : consulter `docker compose ... logs db`,
  vérifier l'espace disque et les variables `POSTGRES_DB`, `POSTGRES_USER` et
  `POSTGRES_PASSWORD`. Ne changez pas les identifiants d'un volume déjà créé
  sans plan de migration.
- **L'API reste unhealthy** : consulter les logs API et appeler
  `/health/live`, puis `/health/ready` depuis le réseau concerné. Le premier
  confirme le processus ; le second vérifie PostgreSQL.
- **Une marketplace est indisponible** : consulter `/api/health` et la page
  Marchés. L'heure du dernier essai, le dernier succès et la dernière erreur
  viennent de la base. Vérifier ensuite la clé concernée et l'accès sortant.
- **Le monitoring 24/7 ne collecte rien** : vérifier `MARKET_SYNC_ENABLED`,
  `MARKET_SYNC_QUERY`, la page Marchés, puis les logs `market_sync`. Une
  plateforme non configurée reste informative ; une erreur réseau est visible
  dans `last_error_code`.
- **Le frontend ne répond pas** : vérifier `APP_BIND_ADDRESS`, `APP_PORT`,
  `docker compose ... ps web` et les logs. Aucun reverse proxy n'est installé
  par ce projet.
- **La page de connexion répond 503** : vérifier la présence de
  `ADMIN_USERNAME`, d'un hash produit par le script et d'un `SESSION_SECRET`
  d'au moins 32 caractères. Ne jamais afficher leur valeur dans un ticket ou
  un log.
- **Le déploiement échoue après migration** : garder les conteneurs et le dump,
  lire les logs, puis choisir entre corriger la nouvelle version ou appliquer
  le rollback documenté. Ne supprimez pas le volume.

Les scénarios de validation serveur, y compris persistance, sauvegarde,
restauration contrôlée et redémarrage, sont détaillés dans
[SERVER_VALIDATION.md](SERVER_VALIDATION.md).

## Intégration future au Server Panel

Une intégration ultérieure pourra afficher l'état de CS2 Arbitrage Hub et
proposer start, stop, restart, logs et health via les scripts officiels. Elle
devra rester séparée de l'authentification applicative et ne sera ajoutée
qu'après stabilisation. Le présent déploiement ne modifie pas Server Panel.
