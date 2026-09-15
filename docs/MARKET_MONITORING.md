# Monitoring marché 24/7

Depuis la consolidation V0.11, un [collecteur realtime optionnel](REALTIME_INGESTION.md)
peut completer REST. Il est desactive par defaut et non valide en live.
`/api/market-monitor` separe `platforms` (REST) de `realtime.skinport` (flux).
Les erreurs et compteurs du flux ne remplacent pas l'etat REST.

Le Continuous Market Monitoring est un scheduler intégré à l'API FastAPI.
Il reste simple : pas de Redis, pas de Celery, pas de service système hôte.
Il tourne seulement quand l'API tourne et quand `MARKET_SYNC_ENABLED=true`.

## Configuration

Variables serveur :

```dotenv
MARKET_SYNC_ENABLED=false
MARKET_SYNC_QUERY=
CSFLOAT_SYNC_INTERVAL_SECONDS=900
SKINPORT_SYNC_INTERVAL_SECONDS=900
DMARKET_SYNC_INTERVAL_SECONDS=900
STALE_AFTER_SECONDS=3600
VERY_STALE_AFTER_SECONDS=86400
PRICE_OBSERVATION_MIN_INTERVAL_SECONDS=3600
```

Le défaut est volontairement inactif. Pour le premier déploiement réel, laisser
`MARKET_SYNC_ENABLED=false` tant que le port, la base, les sauvegardes et les
healthchecks n'ont pas été validés.

Quand le scheduler est activé, `MARKET_SYNC_QUERY` doit contenir au moins trois
caractères. Une seule requête de marché est suivie pour le moment, par exemple
`MARKET_SYNC_QUERY="AK-47 | Redline (Field-Tested)"`. Les plateformes
optionnelles non configurées restent `not_configured` et ne bloquent ni le
démarrage ni `/health/ready`.

## Exécution

Au démarrage de l'API :

1. les adaptateurs CSFloat, Skinport et DMarket sont construits côté serveur ;
2. un `SyncCoordinator` maintient un verrou local par plateforme ;
3. le scheduler calcule une prochaine exécution par plateforme ;
4. chaque collecte appelle le même chemin de persistance que la synchro
   manuelle ;
5. après un succès, les opportunités calculables sont recalculées.

Le conteneur API de production reste à un seul worker Uvicorn. Avec plusieurs
workers, les verrous et quotas locaux ne suffiraient plus : il faudrait une
coordination externe.

## Rate limits et erreurs

Le transport HTTP reste lecture seule. Il met les réponses en cache, espace les
requêtes et borne les retries. Un HTTP `429` arrête immédiatement la tentative
courante, respecte `Retry-After` et n'effectue pas de boucle agressive.

Les erreurs sont persistées dans `market_sync_states` :

- `not_configured` : clé ou paire de clés absente ;
- `error` : réponse invalide, timeout terminal ou erreur applicative sûre ;
- `unavailable` : limite active ou indisponibilité temporaire ;
- `stale` / `very_stale` : dernier succès trop ancien.

Les logs utilisent le message `market_sync` avec `event=sync_started`,
`sync_completed`, `sync_failed` ou `sync_skipped_locked`. Les secrets,
en-têtes, requêtes complètes et corps de réponse ne sont pas journalisés.

## Persistance

Les listings sont upsertés par `mode + platform + external_id`. Un listing
observé est `ACTIVE`; les anciennes lignes ne sont pas supprimées pour inventer
une vente. Les observations de prix conservent plateforme, objet, prix,
devise, référence EUR facultative, type et timestamp. Une fenêtre de
déduplication évite de stocker des observations `LISTING` identiques trop
rapprochées.

Skinport reste `PARTIAL` : l'endpoint utilisé expose des agrégats par nom de
marché. Ces données sont persistées comme `AGGREGATE`, jamais comme listing
individuel ni vente réalisée.

## Healthchecks

- `/health/live` : processus API vivant.
- `/health/ready` : PostgreSQL utilisable uniquement.
- `/health/status` : API, base et états CSFloat/Skinport/DMarket.
- `/api/market-monitor` : état complet du scheduler et métriques persistées.

Une marketplace en panne ou non configurée ne rend pas `/health/ready`
unhealthy. Cette séparation évite de redémarrer l'API à cause d'une API externe.

## Interface

La page `/markets` est le Market Monitor en lecture seule. Elle affiche :

- API et base ;
- scheduler actif/inactif ;
- requête configurée ou non ;
- listings actifs et totaux ;
- observations de prix ;
- opportunités actives ;
- erreurs de synchro sur 24 h ;
- dernière tentative, dernier succès, prochaine exécution et compteurs par
  plateforme.

Aucun bouton dangereux de type “run sync global” n'est ajouté à cette page.
L'authentification administrateur protège l'accès, mais ne transforme pas une
collecte large ou agressive en opération sûre.

## Limites connues

- une seule requête de monitoring est suivie ;
- pas de coordination multi-worker ;
- pas de notifications externes Discord/email ;
- les opportunités live restent inconnues sans ventes et frais effectifs ;
- CSFloat et DMarket nécessitent des clés personnelles pour collecter en live ;
- le déploiement ne configure pas DNS, reverse proxy, Tailscale, UFW ou ports
  publics.
