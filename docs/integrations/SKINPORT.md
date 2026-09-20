# Skinport

## V0.12 : acces refuse, cause non determinee

Relecture du [feed officiel](https://docs.skinport.com/websocket/sale-feed),
15 septembre : Socket.IO MessagePack, websocket, `saleFeedJoin` EUR/en/730.
Aucune exigence de cle, Origin, user-agent specifique ou restriction geographique
n'est indiquee sur cette page. L'auth Basic des API de compte ne prouve pas une
exigence d'auth du flux ; aucune cle Skinport n'est ajoutee.

Probe unique du 15 septembre 16:47:51 UTC : HTTP **403**, `text/html`, serveur
Cloudflare, pas de `cf-mitigated: challenge`, pas de Retry-After, zero evenement.
**BLOCKED_BY_PROVIDER / cause NOT_DETERMINED**. Cela ne permet de conclure ni
a une restriction geo, ni a un manque de cle, ni a un fingerprint impose.
Skinport doit confirmer l'autorisation et la cause. Aucun contournement ni
nouvel essai avec headers/cookies falsifies. Flux toujours desactive.

REST revu le 16 septembre : HTTP 200 items et history. Source globalement
DEGRADED quand le blocage du flux est connu, REST independamment ONLINE,
application non unhealthy. Le statut historique optionnel est decrit dans
[SECURITY.md](../SECURITY.md). Les metriques de debit realtime LIVE ne sont
pas mesurees faute de connexion autorisee.

- Statut : `PARTIAL`
- Documentation officielle : <https://docs.skinport.com/items>
- Historique officiel étudié : <https://docs.skinport.com/sales/history>
- Vérification : 13 septembre 2026
- Base : `https://api.skinport.com/v1`

## API et authentification

L'adaptateur appelle `GET /items` sans authentification, avec `app_id=730`,
`currency=EUR`, `tradable=true` et l'en-tête Brotli obligatoire
`Accept-Encoding: br`. L'endpoint fournit des prix et quantités agrégés par
`market_hash_name`, pas les exemplaires individuels avec leur float ou seed.

La réponse est enregistrée comme `AGGREGATE`. `quantity` désigne l'offre
présente et n'est donc pas transformé en volume de ventes. Aucun identifiant
d'annonce n'est inventé.

## Quotas et limites

La documentation officielle annonce 8 requêtes par 5 minutes et un cache de
5 minutes. L'adaptateur utilise un TTL de 5 minutes et un intervalle minimal
de 38 secondes entre appels de ce fournisseur. Brotli est pris en charge par
la dépendance HTTP du backend.

`GET /sales/history` fournit des statistiques agrégées par fenêtres (24 h,
7, 30 et 90 jours). L'adaptateur normalise min/max/moyenne/médiane/volume dans
`AggregateMarketStat`; aucune transaction unitaire n'est créée depuis cet
endpoint. Une synchronisation ciblée demande uniquement l'historique des noms
exacts retenus par la recherche, par groupes bornés à 20.

Le Sale Feed officiel utilise Socket.IO avec un parser MessagePack et publie
des événements `listed` et `sold`. `price_changed` et `canceled` ne sont pas
supportés. Son normaliseur typé alimente le contrat commun en listings exacts
ou ventes réalisées à partir du `saleId`. Le transport Socket.IO/MessagePack,
la reconnexion et la file bornée sont implementes et testes localement en
V0.11, mais restent desactives. Voir [l'exploitation du flux](../REALTIME_INGESTION.md).

La relecture du 13 septembre montre un ecart entre l'ancien normaliseur et
l'[exemple officiel](https://docs.skinport.com/websocket/sale-feed) : `currency`
est par vente, `saleId` peut etre nul et `url` peut etre un slug. Les unites
exactes de `salePrice` doivent etre confirmees avant raccordement. Les fixtures
precedentes ne prouvent pas la compatibilite du feed actuel. Le registre exclut
donc `WEBSOCKET` et `REALIZED_SALES` des capacites collectees Skinport.

## Validation REST du 13 septembre

Le pacing normal de 38 secondes ne declenche plus un faux `rate_limited`
local. Les HTTP 429 et les delais `Retry-After` restent respectes. Un echec
d'historique conserve les observations de prix et marque la collecte
`degraded`. Les noms/devise de l'historique sont controles, les lots limites a 20.

Le smoke test read-only du code de travail a reussi : 2 observations d'offre,
8 statistiques historiques (quatre fenetres pour chaque nom retenu), aucun
listing individuel ni vente unitaire, aucune ecriture en base. La recherche
REST reste une recherche par sous-chaine et peut inclure une variante StatTrak.

Commande de verification explicite, depuis `apps/api` avec les dependances :

```bash
python -m app.markets.smoke --platform skinport --query 'AK-47 | Redline (Field-Tested)' --live
```

Les contrats REST et le normaliseur du feed ont été validés sur fixtures. Un appel live
de `GET /items` a réussi en HTTP 200 le 5 septembre 2026. L'observation ainsi
collectée reste un agrégat et n'est jamais présentée comme une vente unitaire.

## V0.11 : flux non valide en live

Le probe officiel du 14 septembre 2026 a 20:57 UTC renvoie HTTP 403,
aucun evenement recu. Aucun contournement tente. Les contrats d'unite et
d'identifiant nullable restent a confirmer avec Skinport avant activation.
Le normaliseur refuse les prix non verifies, conserve `assetid` Steam, et
n'invente ni URL d'annonce depuis un slug ni date de vente fournisseur.
Les tests locaux couvrent le protocole reel contre un serveur de test,
la reconnexion, les doublons, l'expiration et la persistance PostgreSQL.
