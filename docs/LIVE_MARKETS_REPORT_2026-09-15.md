# V0.11 : validation live et ingestion realtime

Mission executee les 14 et 15 septembre 2026. Tests finaux le 15 septembre,
vers 16:03-16:07 UTC. **PRODUCTION UNCHANGED par cette mission.**

## Resultat et classification

Le maximum verifiable sans cles ni contournement est atteint pour cette
passe. L'infrastructure locale est validee ; les trois integrations ne sont
**pas** toutes declarees live. Il n'y a toujours aucun moteur de transactions.

| Sujet | Etat final | Preuve / limite |
| --- | --- | --- |
| CSFloat live | BLOCKED_EXTERNAL | Cle absente, contrats et erreurs testes |
| DMarket live | BLOCKED_EXTERNAL | Paire de cles absente, signature fixture et erreurs testees |
| Skinport REST | DONE pour le smoke cible | Lectures publiques reussies, uniquement agregats |
| Skinport realtime | PARTIAL / BLOCKED_EXTERNAL | Code, protocole local et DB testes ; handshake public 403 |
| Reference price | PARTIAL live | Calcul sur mediane reelle Skinport ; absence de comparaison multi-source authentifiee |
| Liquidite | PARTIAL live | Volumes historiques reels, pas de carnet executable complet |
| Spread | PARTIAL | Garde-fous testes, pas de spread executable live prouve |
| Comparables float | DONE pour la protection | Minimum configurable, echantillon exact et distinct, pas de premium invente |
| Fees | DONE pour le refus des inconnues | Barremes existants conserves ; validation DMarket live bloquee |
| FX | DONE pour reference | Cinq devises BCE reelles, pas de FX effectif invente |
| Tracabilite | DONE pour reference / PARTIAL pour arbitrage | Preuves retenues exposees ; profit et ROI LIVE restent null |

## Git et sauvegardes

- Depot : `/home/serve/CS-GO-BISNESSE` ; branche `feat/mvp-foundations`.
- Depart : `d02e5ae1e65bcd63e430a066f32aa02cfe9c3620`, arbre propre et
  24 commits locaux non pousses. L'audit est conserve dans `V011_AUDIT.md`.
- HEAD fonctionnel teste : `903ef9b`, suivi du commit documentaire de ce rapport.
- Commits : `e28dd8b` contrats/cursor CSFloat-DMarket ; `ed865a1` backend
  realtime/provenance ; `903ef9b` interface et validation isolee.
- La cloture documentaire porte l'ensemble a 28 commits devant la reference
  distante `2a636e7caeb5b46146e3927a2236b50108c1fbf8`, reconfirmee par
  `git ls-remote` le 15 septembre.
- Backup initial verifie :
  `/home/serve/backups/cs2-v011-20260914/before-d02e5ae.bundle`.
- Backup final :
  `/home/serve/backups/cs2-v011-20260914/after-20260915.bundle`.
  Historique Git complet, sans ajout de fichier secret ni dump DB.
- Aucun usage ni enregistrement du token poste dans le chat. Revocation
  demandee. Les tentatives de push du 14 et du 15 septembre, limitees au cache
  de credentials existant, echouent : `could not read Username`, prompts
  desactives. Aucun force-push ni modification d'auth serveur effectue.

L'arbre doit rester propre apres ce commit. Le SHA de cloture exact est celui
de `git log -1` ; `git bundle list-heads` permet de verifier sa presence dans
la sauvegarde finale sans rendre le rapport auto-referentiel.

## CSFloat et DMarket

Presence des trois variables verifiee les 14 puis 15 septembre par parseur
dotenv sur montage read-only de `/opt/cs2-arbitrage-hub/.env.production`.
Seuls les noms et booleens de configuration ont ete affiches :

| Variable | Etat |
| --- | --- |
| `CSFLOAT_API_KEY` | NOT_CONFIGURED |
| `DMARKET_PUBLIC_KEY` | NOT_CONFIGURED |
| `DMARKET_SECRET_KEY` | NOT_CONFIGURED |

CSFloat : aucune reponse de listing authentifiee ni verification live de
float/seed/stickers. Le curseur d'entree officiel est maintenant accepte et
borne ; aucun curseur de sortie n'est devine et aucune boucle de pages n'est
declenchee. Quota chiffre et headers reels restent non verifies.
Le [contrat CSFloat](https://docs.csfloat.com/) reste la reference documentaire.

DMarket : signature Ed25519 et canonicalisation couvertes par les tests
existants ; offres/targets/ventes/frais verifies sur fixtures uniquement.
Aucun resultat live signe n'est revendique. La
[specification officielle](https://docs.dmarket.com/v1/swagger.html) ne remplace
pas cette verification avec une paire de cles utilisable.

Pour les deux adaptateurs : matrice 401, 403, 429, 500, 502, 503, timeout et
JSON invalide testee. Le transport ne divulgue pas les corps ou credentials,
reste GET-only, borne ses tentatives et respecte `Retry-After`. Un echec des
enrichissements n'efface pas les offres primaires deja obtenues.

Smokes prets, depuis `apps/api` avec les variables deja fournies de facon sure :

```bash
python -m app.markets.smoke --platform csfloat --query 'AK-47 | Redline (Field-Tested)' --live
python -m app.markets.smoke --platform dmarket --query 'AK-47 | Redline (Field-Tested)' --live
```

Aucune lecture implicite de `.env`, aucune transaction, aucune ecriture DB.

## Skinport REST, valorisation et FX reels

Smoke public final du 14 septembre a 20:54:02-20:54:41 UTC :

- REST `online`, 2 observations d'offre agregee, 8 statistiques historiques,
  0 listing individuel, aucun echec partiel.
- La recherche peut renvoyer une variante StatTrak. La valorisation du smoke
  filtre le nom **exact** `AK-47 | Redline (Field-Tested)` avant le calcul.
- Mediane retenue : **25,66 EUR**, fenetre **7D**, volume **70**, methode
  `HISTORICAL_MEDIANS`, une preuve agregee retenue, confiance **66/100**.
- Liquidite descriptive : **42/100**, categorie `MEDIUM`, completude **55 %**.
- Profit **null**, frais **UNKNOWN**, opportunite executable **false**.

Ce chiffre de reference vient d'une statistique de la
[source historique Skinport](https://docs.skinport.com/sales/history), pas
d'une promesse de revente. Un volume de ventes agregees ne devient pas autant
de transactions unitairement identifiees. Aucun gain FX n'est cree.

Taux BCE dates du 14 septembre 2026, recuperes via le
[service de donnees officiel EXR](https://data-api.ecb.europa.eu/service/data/EXR/D.USD+GBP+JPY+CHF+CNY.EUR.SP00.A?lastNObservations=1&format=csvdata).
Conversion de 100 unites source, arrondie ici pour lecture :

| Source | EUR de reference | FX effectif |
| --- | ---: | --- |
| USD | 86,572591 | inconnu |
| GBP | 116,825159 | inconnu |
| JPY | 0,560161 | inconnu |
| CHF | 106,033294 | inconnu |
| CNY | 12,905057 | inconnu |

Le smoke conserve les Decimal et horodatages ; il n'a rien persiste en DB.
Ces observations datees ne sont pas presentees comme des cours actuels garantis.

## Skinport realtime

Probe reproductible du 14 septembre a **20:57:30 UTC** : `connected=false`,
`events=0`, `http_status=403`, `error_code=connection_failed`. Aucune relance
rapide, aucun anti-bot contourne, aucune API privee inspectee.

Le [contrat officiel](https://docs.skinport.com/websocket/sale-feed) utilise
Socket.IO MessagePack et `listed`/`sold`. Le normaliseur tient compte de
`saleId` nullable, `assetid` Steam distinct de `assetId`, devise par ligne,
slug d'URL et date de reception explicite. Sans unite de prix verifiee, il
refuse l'ingestion. Les montants malformes ou hors capacite SQL sont rejetes.

Implementation : queue 256 par defaut, batches de 20, backoff exponentiel,
jitter, fermeture de session, retry DB borne, receipts transactionnels,
compteurs de pertes/doublons, expiration conservatrice et calcul par nom
touche. Le moteur REST reste independant. Voir `REALTIME_INGESTION.md` pour
les limites de shutdown, retention et exploitation mono-processus.

`SKINPORT_REALTIME_ENABLED=false` demeure le defaut. Pas de validation 24/7
du flux, pas de preuve de recuperation de tous les evenements manques.

## Securite des calculs

- Hierarchie et garde-fous existants conserves : ventes, medianes, demande,
  annonces ; meme nom/exterior/variante, bids conditionnels refuses.
- `FLOAT_MIN_SAMPLES` vaut 5, configurable de 5 a 1000. En dessous :
  `INSUFFICIENT_DATA`. Le percentile est descriptif, sans prime financiere.
- Fiche objet : prix d'achat avec identifiant, prix original/devise, preuves
  de reference effectivement retenues, horodatages, FX source/date, volume,
  comparables et frais inconnus. Affichage borne a 50 preuves avec compte total.
- Le scanner et la watchlist excluent les annonces live perimees, meme avec
  collecteur arrete. Les compteurs actifs utilisent la meme protection.
- Prix modifie : snapshot recalcule ; vente confirmee : `SOLD` ; disparition
  ou expiration sans preuve : `INACTIVE`. Un replay ne rafraichit pas le prix.
- Aucun profit/ROI/opportunity score LIVE fabrique tant que frais effectifs,
  route de revente et revalidation executable ne sont pas etablis.
- SkinSniper reste une reference parmi 18 sources du registre, sans collecte
  automatique ni utilisation de son pourcentage d'ecart comme profit.

## Tests et base temporaire

| Controle | Resultat final |
| --- | --- |
| Backend pytest | **140 passed**, 2 avertissements de deprecation Starlette existants |
| Ruff check / format --check | PASS, 73 fichiers formates |
| Mypy | PASS, 48 fichiers source |
| Frontend npm test | **44 passed**, 15 fichiers |
| Lint / typecheck / build Next.js | PASS |
| npm audit --audit-level=high | 0 vulnerabilite rapportee |
| Compose development + modele production | PASS, pas de lancement du modele production |
| Build Docker API/web | PASS |
| Alembic PostgreSQL | upgrade head / check / downgrade nouvelle table / re-upgrade / check : PASS |
| Persistance PostgreSQL | receipts, changement de prix, vente, replay, stale scanner, provenance : PASS |
| Navigateur | 3 scripts PASS, desktop 1440 px, mobile 390 et 360 px |

Migration additive `f8a2b6c0d4e1`, parent `e6f7a8b9c0d1` : table
`realtime_receipts`, PK d'empreinte et index `received_at`. Pas de changement
des tables de prix pour porter la provenance, derivee des champs existants.
La base temporaire apres fixtures mesurait **9 344 691 octets**.

Les tests couvrent le vrai protocole MessagePack contre un serveur local,
heartbeat, erreurs, queue pleine, deduplication, rollback/retry, shutdown,
pruning et absence de faux statut online. Ils ne simulent pas une autorisation
du fournisseur. Le HTTP 403 du navigateur est une fixture explicite ; le
transport public reel a ete teste separement et a effectivement refuse.

Parcours conserves : dashboard, marches, integrations, scanner, fiche objet,
creation/modification/pause/suppression et rechargement watchlist, isolation
LIVE/DEMO. Zero erreur console/page relevee, zero debordement du document.
Les tables de preuves gardent un defilement horizontal interne sur mobile.

Derniere validation jetable : `python3 scripts/tests/validate-v011-stack.py --run`.
Preuves persistantes, hors Git :
`/home/serve/CS-GO-BISNESSE/artifacts/v011-20260915-160431/`.
Le premier test navigateur de provenance utilisait un selecteur texte trop
strict ; corrige, puis toute la suite a ete relancee avec succes.
Les conteneurs et le volume `cs2-v011-validation` ont ete supprimes apres test.

## Production et services existants

Verification read-only a la reprise du 15 septembre :

- SHA production : `378b6f0494a042d434e42acd8b2dc014413eecb6`, identique au depart.
- Migration production : `2f8c9d1a4b70`, non migree par cette mission.
- Taille DB observee : **9 590 451 octets**. Elle varie pendant la collecte
  existante ; aucune ecriture de test ni deploiement n'a cible cette base.
- Conteneurs CS2 web/API/DB healthy. L'uptime observe est passe de 6 jours le
  14 septembre a 5 heures le 15 septembre, hors des commandes de cette mission.
  Aucun redemarrage de ces conteneurs n'a ete effectue ici.
- Server Panel, Apache, Cockpit et Tailscale controles actifs les 14 et 15 septembre.
  Aucun fichier de ces services, AdGuard ou Minecraft n'a ete modifie.
- Aucun changement reseau, UFW, Livebox, SSH, ports publics ou authentification
  V0.10. La production garde ses modalites d'acces existantes.

## Suite recommandee

1. Revoquer le token GitHub expose et configurer une authentification Git
   sure directement sur le serveur, hors conversation, pour pousser les commits.
2. Fournir les trois variables marche dans l'emplacement securise prevu,
   jamais dans un message ni Git ; executer les smokes read-only bornes.
3. Faire confirmer par Skinport l'acces officiel depuis ce serveur, l'unite
   du prix et un identifiant stable utilisable, puis valider un petit flux.
4. Observer duree, pertes, retards DB et retention avant activation durable.
5. Ne proposer un deploiement qu'apres ces validations et une decision explicite.
   Ne pas commencer trade engine, rarete speculative ou optimisation de routes.
