# V0.12 : Live Credentials, Market Activation and Security Cleanup

Implementation et tests : 15-16 septembre 2026. Cloture et verification Git,
credentials de test et production : 20 septembre. **PRODUCTION UNCHANGED
par cette mission.** Aucun achat, vente, depot, retrait ou trade execute.

## Resultat et limites

| Sujet | Etat | Preuve / limite |
| --- | --- | --- |
| Saisie de credentials | VALIDATED | Helper isole ; tests permissions, atomicite, non-divulgation |
| CSFloat | NOT_CONFIGURED | Cle absente ; contrats et smokes locaux prets |
| DMarket | NOT_CONFIGURED | Paire absente ; signature testee, pas d'auth reelle |
| Skinport REST | ONLINE au smoke du 16 septembre | GET items/history 200, agregats reels |
| Skinport realtime | BLOCKED_BY_PROVIDER | HTTP 403 le 15 septembre ; cause NOT_DETERMINED |
| Token GitHub divulgue | HUMAN_ACTION_REQUIRED | Revocation non confirmee, aucune reutilisation |
| GitHub SSH | SSH_READY_WAITING_USER | Cle dediee creee, publickey refuse le 20 septembre |
| Pipeline LIVE authentifie | BLOCKED_EXTERNAL | Pas de donnees CSFloat/DMarket authentifiees |
| Pipeline local / provenance | VALIDATED sur fixtures | PostgreSQL et navigateur isoles |
| Production / V0.10 auth | NON DEPLOYE / NON ACTIVEE | Code et schema precedents conserves |

L'objectif ideal de toutes les sources authentifiees n'est pas atteint. L'absence
de cles n'est pas un echec du code. Aucune V0.13 commencee, aucune ponderation
financiere existante modifiee, aucun resultat LIVE invente.

## Git et sauvegardes

- Depot `/home/serve/CS-GO-BISNESSE`, branche `feat/mvp-foundations`.
- HEAD avant : `6eb59c0e86a8896489bd4abed6f44d38c03f4913`, arbre propre,
  28 commits locaux non pousses.
- Commits V0.12 : `60f12b9` stockage credentials ; `aaa7548` diagnostics,
  smokes bornes, garde-fous et statut provider ; `d383dce` preuves de validation.
- HEAD applicatif apres : `d383dce`, suivi du commit documentaire portant ce
  rapport. Le SHA de cloture exact se lit avec `git rev-parse HEAD` ou la ref
  HEAD du bundle ; il ne peut pas etre ecrit dans son propre commit.
- Remote conserve : `https://github.com/blou132/CS-GO-BISNESSE.git`, sans
  identifiant embarque. Reference publique reconfirmee le 20 septembre :
  `2a636e7caeb5b46146e3927a2236b50108c1fbf8`.
- Merge-base : cette meme reference ; 0 commit en retard, 32 en avance avec
  la cloture documentaire. Aucun force-push, amend ou historique reecrit.
- Bundle V0.11 reverifie le 20 septembre :
  `/home/serve/backups/cs2-v011-20260914/after-20260915.bundle`, historique complet.
- Bundle V0.12 de cloture :
  `/home/serve/backups/cs2-v012-20260920/before-push.bundle`, dossier `0700`,
  fichier `0600`, verification Git apres le commit documentaire.
- Arbre propre controle apres cloture. Pas de push : SSH reste refuse.

Cle dediee `~/.ssh/id_ed25519_github_cs2`, mode `0600`, sans passphrase pour
l'usage serveur : protection du compte et de Docker essentielle. Cle existante
non remplacee. Seul `Host github.com` ajoute dans `~/.ssh/config`, mode `0600`.
Aucun SSH global touche. Host keys existantes concordantes avec les empreintes
officielles GitHub.

Action humaine : ajouter `~/.ssh/id_ed25519_github_cs2.pub` dans GitHub Settings >
SSH and GPG keys. Puis verifier l'identite retournee par `ssh -T git@github.com`,
branche, divergence et bundle avant push normal. Le remote pourra alors devenir
`git@github.com:blou132/CS-GO-BISNESSE.git`. Ne jamais copier la cle privee.

## Token compromis

Type : GitHub fine-grained PAT divulgue dans la conversation. Aucune valeur,
prefixe personnel, suffixe ou hash du token reproduit dans le travail.

Audit initial par motifs : 482 objets Git accessibles via refs/reflogs,
224 fichiers de travail hors dependances/caches et cinq fichiers metadata/historique.
Aucun motif PAT/cle privee trouve dans ce perimetre. Fichiers suivis et historique
rescannes apres les commits applicatifs : 517 objets Git, aucun motif detecte.
Cette recherche ne prouve pas l'absence
universelle de tout secret, de copies externes ou de donnees encodees autrement.

| Emplacement | Resultat |
| --- | --- |
| Sources et documentation courantes | Aucun PAT trouve |
| Historique Git / reflogs examines | Aucun PAT trouve ; aucune purge engagee |
| `.git/config`, metadata, `.bash_history` examines | Aucun PAT trouve |
| Dernieres 500 lignes de logs CS2 API/web/DB | Aucun PAT trouve |
| Journal de conversation Codex | SECRET_FOUND, GITHUB_PAT |

Localisation, sans lecture exposee de son contenu :
`/home/serve/.codex/sessions/2026/09/08/rollout-2026-09-08T14-49-02-01a08110-93de-75c3-9bd0-53d7574299b3.jsonl`.
Permissions constatees `0664`, proprietaire serve. Original non supprime ni
recopie ; hors Git et bundle CS2. Copies distantes de conversation et autres
sauvegardes hors perimetre non auditees.

Revocation : **HUMAN_ACTION_REQUIRED**, aucune interface officielle deja
authentifiee utilisable pour la revocation. Aucune reutilisation du PAT pour se
connecter. Revoquer le token divulgue dans GitHub Settings > Developer settings >
Personal access tokens > Fine-grained tokens. Apres revocation, traiter les copies
de journaux selon une decision distincte, sans suppression automatique de preuves.
[Procedure et documentation officielle](SECURITY.md).

## Hygiene et stockage

Ignore files, env d'exemple, Dockerfiles, Compose et CI controles. `.gitignore`
et `.dockerignore` renforces pour credentials, secrets, extensions de cles et
backups. `git add -f` peut toujours contourner un ignore : revue humaine necessaire.

Audit layers le 16 : images API production/validation, 10 layers chacune ; web,
5 chacune. 39/202 fichiers applicatifs production et 61/330 validation examines,
hors dependances. Aucun dotenv/nom sensible de cle privee ni motif PAT/cle privee.
Pas de configuration reelle fournie aux builds. La derniere reconstruction API
ne change que le cleanup expurge du smoke, sans ajout de secret.

`docker inspect` traite sans afficher Config.Env : mot de passe DB et DATABASE_URL
restent accessibles aux utilisateurs controlant Docker. Ce modele de menace est
documente, pas remplace. Aucune valeur de secret affichee : OUI.

Helper : `./scripts/configure-market-credentials.py`, getpass dans l'image de test
Docker sans reseau, UID/GID utilisateur, root filesystem read-only, sans capabilities.
Fichier unique : `~/.config/cs2-arbitrage-hub/markets.env`, hors Git. Dossier `0700`
constate ; fichier `0600`/ownership verifies sur donnees synthetiques. Aucun fichier
de vraies cles cree : les trois variables restent NOT_CONFIGURED au controle du 20.

Format minimal, refus PAT GitHub, paire Ed25519 verifiee avec PyNaCl, dotenv sans
interpolation, autres variables preservees, doublons/liens/permissions excessives
refuses. Verrou, ecriture atomique/fsync, ancien fichier sauvegarde en `0600`,
retention de trois sauvegardes. Tests interruption/conservation/non-divulgation passes.
Pas d'arguments secrets, export shell ou copie dans `.env.production`.
[Commandes de saisie et de smoke](SECURITY.md).

Config production examinee en lecture seule le 15 septembre : trois cles absentes.
Elle n'a pas ete modifiee. Le stockage de test et la production ne sont pas confondus.

## CSFloat et DMarket

Contrats officiels relus le 15 : [CSFloat](https://docs.csfloat.com/),
[DMarket](https://docs.dmarket.com/v1/swagger.html),
[FAQ quotas](https://dmarket.com/faq#startUsingTradingAPI). Details dans les fiches.

| Controle | CSFloat | DMarket |
| --- | --- | --- |
| Credential test | NOT_CONFIGURED | NOT_CONFIGURED |
| Auth reelle | NOT_TESTED | NOT_TESTED |
| Endpoint prepare | GET /api/v1/listings | GET /marketplace-api/v2/offers |
| HTTP authentifie observe | Aucun, request NOT_SENT | Aucun, request NOT_SENT |
| Listings/offres LIVE | Non mesure | Non mesure |
| Parser LIVE | NOT_TESTED | NOT_TESTED |
| Pagination | UNKNOWN, une page | UNKNOWN, une page |
| Quota du compte observe | UNKNOWN | UNKNOWN |
| Signature | Non applicable | Tests locaux passes ; acceptation serveur non prouvee |
| Ventes / ordres / frais LIVE | Non verifies | Non verifies |

Smokes sans reseau executes : `not_configured`, code 2, requests vide. Avec une
cle : cinq annonces maximum, une tentative par endpoint, `--enrich` explicite
pour les lectures DMarket supplementaires. Compteurs, champs optionnels presents,
duree et metadata HTTP expurges. Aucune ecriture DB ni transaction.

Tests offline : 401/403/404/429/500/502/503, timeout, JSON invalide, schemas
malformes, redirections, cooldown, Retry-After, collecte partielle et fermeture.
Tests scheduler existants passes. DMarket : vecteur public RFC 8032, signature
invalide, alteration chemin/corps/timestamp, paire incoherente, cles absentes,
refus de signer POST ou GET avec corps. Le rejet d'un timestamp expire par le vrai
serveur reste non verifie ; le test local verifie la signature alteree.

Aucun schema authentifie invente, aucune fixture presentee comme capture LIVE.
Frais personnels, float/pattern/stickers et comparaison exhaustive fixture/schema
LIVE restent a verifier apres saisie humaine des cles.

## Skinport

REST : **16 septembre 15:17:36-15:18:14 UTC**, GET `/v1/items` et `/v1/sales/history`
HTTP 200, 2 observations, 8 statistiques, 0 listing individuel, aucune erreur
partielle. Pas d'ecriture DB ni transaction.

Realtime : probe unique **15 septembre 16:47:51 UTC**, HTTP 403, aucune connexion,
zero evenement. `skinport.com/socket.io/`, `text/html`, serveur Cloudflare,
pas de Retry-After ni marqueur `cf-mitigated: challenge`. Versions : python-socketio
5.16.4, python-engineio 4.14.0, aiohttp 3.14.3, msgpack 1.2.2. Aucun cookie,
corps de reponse, signature ou header d'auth conserve.

[Contrat officiel du feed](https://docs.skinport.com/websocket/sale-feed) concordant
avec MessagePack et le payload d'abonnement. Aucune exigence supplementaire
documentee ne justifie de modifier Origin, cookies ou identite client. La presence
de Cloudflare seule ne revele pas la regle ayant refuse l'acces. Conclusion :
**BLOCKED_BY_PROVIDER, cause NOT_DETERMINED** ; confirmation Skinport requise.
Pas de contournement, scraping, proxy, API privee ni nouvel essai le 20 septembre.
Le resultat est date, pas une mesure permanente.

Realtime desactive. Nouveau statut `blocked` et historique optionnel
`SKINPORT_REALTIME_BLOCKED_AT`, incompatible avec activation automatique. Aucun
blocage fabrique par defaut. REST ONLINE + flux BLOCKED affichent une source
degradee sans rendre API/DB unhealthy. Readiness inchangee. SkinSniper reste
REFERENCE_SOURCE uniquement, sans collecte.

## Pipeline et calculs

Pipeline authentifie complet : **BLOCKED_EXTERNAL**, non valide sur donnees
reelles. Pipeline local normalisation/persistance/analyse/API/frontend valide
avec fixtures explicites, pas une preuve d'acces fournisseur.
DEMO isolee ; fixtures PostgreSQL techniques marquees TEST dans identite/attributs
et environnement. Elles exercent les chemins `mode=live` dans une DB jetable,
jamais une DB de collecte reelle. Le schema conserve LIVE/DEMO : pas de nouveau
mode production ni migration V0.12.

Reference reelle mesuree pour AK-47 Redline Field-Tested : **25,69 EUR**, mediane
7 jours, volume agrege 69, confiance **65/100** ; une preuve agregee, pas 69 ventes
individuellement identifiees. Liquidite **44/100**, MEDIUM, completude **55 %**.
Valeur datee, non garantie de revente. Ponderations conservees.

Tests ajoutes : source unique/volume 1 ne produit pas une confiance elevee ;
annonce a 1 EUR et autre demande a 99 999 EUR ne creent pas d'opportunite executable.
Frais UNKNOWN, FX effectif UNKNOWN, profit/ROI LIVE non inventes ; zero opportunite
fiable est valide. Garde-fous V0.11 exact item/variante, comparables et fraicheur
conserves. Pas de primes pattern/float arbitraires ni spread SkinSniper pris pour profit.

Provenance exposee/testee : source/type, record/external ID si disponible,
observed_at, prix/devise, FX, preuves retenues, comparables, confiance et frais.
Receipts realtime avec received_at. Limite restante : received_at et normalized_at
distincts non materialises pour toutes les familles REST historiques. Pas de
dates absentes inventees ; contrat a completer avec la validation authentifiee.

FX BCE du 16 septembre pour 100 unites, arrondi pour lecture : USD 86,677646 EUR,
GBP 116,631677, JPY 0,559034, CHF 105,831305, CNY 12,923236. Source/date/montant
original conserves, FX effectif null. Calculs Decimal, frais inconnus jamais 0 %.

## DB et retention

Base jetable apres tests : **9 344 691 octets**. 18 listings (16 DEMO, 2 TEST),
138 observations, 5 receipts, 1 vente TEST, 16 snapshots et 16 opportunites DEMO.
Ces comptes ne sont pas des donnees LIVE. Tailles avec indexes : listings 163 840,
observations 147 456, snapshots 147 456, receipts 40 960 octets. Detail dans le log.

Dedupe/replay/vente/prix change/expiration passes. Pas de retention brute illimitee.
Retention existante receipts/observations 30 jours par defaut ; max_listings et
expiration conserves. Toutes les ventes/lignes historiques inactives ne sont pas
soumises a une purge globale. Surveiller observations, receipts, ventes et listings.
Croissance, events/sec, ecritures/sec, latence et memoire realtime LIVE non mesurables
sans acces au flux ; aucune extrapolation fiable depuis quelques fixtures.

## Tests et preuves

| Controle | Resultat du 16 septembre |
| --- | --- |
| Backend pytest | **163 passed**, 2 avertissements Starlette preexistants |
| Ruff / format / mypy | PASS, 78 fichiers formates, 50 modules types |
| Frontend tests | **45 passed**, 15 fichiers |
| Lint / typecheck / build | PASS |
| npm audit --audit-level=high | 0 vulnerabilite rapportee |
| Compose dev + modele prod | PASS, aucun lancement du modele prod |
| Images API/web | Builds PASS, API reconstruite apres cleanup du smoke |
| PostgreSQL Alembic | upgrade/check/downgrade/re-upgrade/check PASS |
| PostgreSQL ingestion | Dedupe, prix, vente, stale scanner, provenance PASS |
| Navigateur | Dashboard, markets, scanner, item, watchlist, integrations PASS |
| Desktop/mobile | 1440/390/360 px, zero erreur console/page ou debordement document |

Unit/integration marques separement. `pytest` normal ne contacte pas de fournisseur.
Futurs tests live ignores sans `RUN_LIVE_MARKET_TESTS=1`. Smokes externes actuels
separes, `--live` obligatoire. Aucun secret CI. Fixture navigateur 403 explicitement
simulee ; refus reel mesure separement. Aucun ecran DEMO revendique comme LIVE.

Preuves hors Git : `artifacts/v012-backend-20260916.log`,
`v012-frontend-20260916.log`, `v012-stack-20260916.log`,
`v012-public-live-20260916.log`, captures `artifacts/v012-20260916-151622/`.
Commande : `python3 scripts/tests/validate-v011-stack.py --version v012 --run`.
Stack et volume isoles supprimes apres tests, images outils conservees.
Preuves relues le 20 ; pas de nouveau smoke de marketplace pendant cette cloture.

## Production et actions humaines

Le 20 : code `378b6f0494a042d434e42acd8b2dc014413eecb6`, migration `2f8c9d1a4b70`,
DB **9 705 139 octets** au controle read-only. CS2 API/web/DB healthy, Crafty actif,
AdGuard arrete. Uptime different entre reprises, hors des commandes de cette mission.
Controles HTTP du 20 : panel 200 apres suivi des redirections, portfolio 200,
health CS2 200 ; server-panel/apache2/cockpit.socket/tailscaled actifs.
Arbre Git production propre. Le HTTP 200 du panel ne constitue pas un test
de session administrateur authentifiee.
Aucun fichier de ces services, Minecraft, Tailscale, AdGuard, reseau, firewall
ou Livebox modifie. V0.10 non activee en production. Aucun collecteur V0.12 dirige
vers la DB production. Aucun redemarrage de service existant par cette mission.

Restent : revoquer le PAT, enregistrer la cle SSH publique, saisir
`CSFLOAT_API_KEY`, `DMARKET_PUBLIC_KEY`, `DMARKET_SECRET_KEY` dans le terminal prive,
obtenir une clarification Skinport. Puis smokes authentifies minimaux et pipeline
isole avec schema/provenance reels, avant toute decision de deploiement.
V0.13 est une suite a cadrer apres ces preuves, pas une implementation commencee
ni une autorisation de deploiement implicite.
