# Sources, SkinSniper et valorisation : rapport de tranche

Verification finale : 14 septembre 2026, 15:39 UTC. Recherche documentaire et
smoke Skinport : 13 septembre. Ce rapport distingue le code teste, les appels
live et la production. Il ne declare pas le cahier des charges global termine.

## Etat Git

- Depot : `/home/serve/CS-GO-BISNESSE`, branche `feat/mvp-foundations`.
- Depart : `472750b`, 19 commits locaux preexistants, arbre propre.
- SHA applicatif valide : `63733a07b08a536a320721a2e32a5a4f5cf71ad6`.
- Remote apres `git fetch origin` reussi le 14 septembre :
  `2a636e7caeb5b46146e3927a2236b50108c1fbf8`.
- `LOCAL COMMITS NOT PUSHED` : 23 avant ce rapport, 24 avec son commit de
  documentation. Le SHA de ce dernier est donne par `git rev-parse HEAD`.
- Push non interactif refuse : authentification HTTPS GitHub indisponible.
  Aucun changement d'identifiants, force-push, reset ou amend.

Commits applicatifs de cette tranche :

| SHA | Changement |
| --- | --- |
| `67c292d` | SkinSniper, decouverte officielle, registre, distinction collecte/contrat |
| `437221b` | Resilience des sources, statut partiel, smoke read-only, test navigateur |
| `da5ca83` | Preuves fraiches, snapshots d'ordres, comparables float dedupliques |
| `63733a0` | Frais perimes, futurs et ambigus refuses |

Les 19 commits precedents sont conserves. Liste exhaustive reproductible :
`git log --oneline origin/feat/mvp-foundations..HEAD`.

## Audit et acquis conserves

La [matrice de reprise](RESUME_AUDIT_2026-09-13.md) qualifie les 31 sections
avant modification en `DONE`, `PARTIAL`, `TODO`, `BLOCKED_EXTERNAL`.
Le [rapport precedent](DATA_MARKETS_REPORT_2026-09-13.md) a ete lu avant le travail.

Scanner pagine, filtres/tri SQL, watchlist persistante avec CRUD, pause/reprise,
correspondances et isolation LIVE/DEMO, configuration FX/CI, modeles V2 et
authentification privee etaient deja presents. Aucun de ces modules n'a ete
recree. Les changements partages d'analyse enrichissent leurs resultats sans
reecrire leurs parcours. L'authentification V0.10 reste non activee en production.

## Sources live

| Source | Code raccorde | Preuve de cette tranche | Etat restant |
| --- | --- | --- | --- |
| CSFloat | Listings, prix cents USD, float, paint seed/index, stickers, inspect, etat/date | Fixtures, bornes prix/float, categorie officielle, absence de cle, redirections | `BLOCKED_EXTERNAL` pour validation authentifiee |
| Skinport REST | Items agreges EUR, historique min/max/moyenne/mediane/volume 24 h, 7/30/90 j | Appel live reussi : 2 observations, 8 agregats | REST valide ; aucune annonce individuelle revendiquee |
| Skinport feed | Ancien normaliseur seulement | Contrat officiel relu, divergences identifiees | `PARTIAL` : transport et normaliseur actuel non valides, non actives |
| DMarket | Offres, targets/buy orders, dernieres ventes, frais, attributs exacts | Signature et schemas testes sur fixtures, echecs d'enrichissement isoles | `BLOCKED_EXTERNAL` pour validation authentifiee |

Le bug de pacing Skinport etait local : l'intervalle normal de 38 secondes
etait confondu avec un cooldown d'erreur borne a 5 secondes. Il est desormais
attendu normalement. Un vrai HTTP 429 ou `Retry-After` n'est pas raccourci.
L'historique est borne a 20 noms distincts et controle nom/devise. Une recherche
par sous-chaine peut inclure une variante StatTrak : les noms exacts restent
distincts, sans fusion de leurs prix.

Pour Skinport et DMarket, un enrichissement indisponible conserve les donnees
primaires deja recues et produit `degraded` / collecte partielle. Les erreurs
par capacite restent visibles dans API/monitoring. Une collecte complete
suivante retablit `online`. Le float DMarket egal a zero n'est plus perdu.

La commande `python -m app.markets.smoke --platform ... --query ... --live`
est explicite, bornee a 120 secondes, sans lecture automatique de `.env`,
ecriture en base ni transaction. Sortie limitee aux compteurs et codes d'erreur.
Sans cles, CSFloat et DMarket renvoient `not_configured`, code de sortie 2.

Les [notes CSFloat](integrations/CSFLOAT.md), [Skinport](integrations/SKINPORT.md)
et [DMarket](integrations/DMARKET.md) donnent commandes, contrats et limites.
Les statistiques historiques Skinport ne deviennent jamais des ventes realisees
individuelles. L'[exemple officiel du feed](https://docs.skinport.com/websocket/sale-feed)
place notamment la devise par vente et accepte un `saleId` nul ; l'ancien
normaliseur et les unites de prix doivent etre revalides avant tout raccordement.

## SkinSniper

`DONE` pour l'etude et l'inscription comme reference, pas comme collecteur.

- Roles : `AGGREGATOR`, `REFERENCE_SOURCE`, `MARKET_DISCOVERY_SOURCE`.
- Recherche officielle explicite : official API, developer API, public API,
  partner API, puis verification des pages officielles.
- `API_NOT_FOUND` signifie contrat public tiers exploitable non identifie,
  pas preuve qu'aucune API interne ou partenaire n'existe.
- L'[extension officielle](https://skinsniper.com/extension) mentionne une API
  utilisee par le produit. Cela ne documente pas un droit d'acces tiers.
- Decision : `RESEARCH_REQUIRED`, reference uniquement ; aucun adaptateur,
  scraping, endpoint interne, contournement anti-bot ou import de prix.
- Comparaisons de marches/prix, mouvements, frais, alertes, inventaire,
  Fade/pattern/inspect restent des outils de reference, sans regle de rarete copiee.

Un `Difference %` affiche ne produit aucune opportunite. Avant une future
opportunite executable, il faut revalider annonce active, exemplaire exact,
float/pattern/stickers, fraicheur, ventes realisees, liquidite, frais de chaque
etape, depot/retrait, FX effectif et trade lock. Un rapprochement de spread
avec SkinSniper n'est pas implemente ; il resterait un controle secondaire.

Document demande : [integrations/skinsniper.md](integrations/skinsniper.md).

## Registre et autres marketplaces

18 sources sont exposees par le registre et la page Integrations. L'API
distingue capacites documentees, capacites raccordees, acces, configuration,
roles, date de verification et etat operationnel. Une authentification
inconnue est `null`, jamais assimilee a un acces public confirme.

| Plateforme | Decision apres etude officielle | Integration automatique |
| --- | --- | --- |
| SkinBaron | API officielle, approbation requise par capacite | Aucune |
| GamerPay | Fermeture annoncee le 29 mai 2026 | Indisponible |
| BUFF Market / BUFF 163 | Contrat developpeur officiel non identifie ; sites distincts | Aucune |
| White.Market | Documentation partenaire GraphQL/JWT et exports publics ; autorisation a confirmer | Aucune |
| Waxpeer | Documentation API officielle ; certains GET ont des effets transactionnels | Aucune, future liste de routes read-only obligatoire |
| HaloSkins | API documentee, cle apres approbation | Aucune |
| Skinflow | Pas de contrat tiers officiel identifie | Aucune |
| Steam | Reference, pas nouvelle collecte de marche autorisee | Aucune |

La [matrice officielle de decouverte](integrations/MARKET_DISCOVERY.md) detaille
pour chaque source listings, ventes, float, trade, frais, devises, quotas et
authentification, avec ses liens officiels. Les inconnues restent explicites.
Aucune nouvelle cle ou compte n'a ete demande au travers du chat.

## Trade sites

Etude officielle actualisee, pas de quote live ni transaction :

- Tradeit.gg : `RESEARCH_REQUIRED`, pas de contrat tiers identifie. `tradeit.app`
  n'est pas utilise pour le projet.
- CS.MONEY : `RESEARCH_REQUIRED`, consentement/API a clarifier ; ses conditions
  distinguent solde Trade et cash recuperable.
- Swap.gg et SkinsMonkey : `RESEARCH_REQUIRED`, aucun contrat exploitable
  confirme depuis leurs ressources officielles.
- DMarket Trade : lectures marketplace connues, mais aucun provider de
  TradeQuote executable raccorde ni endpoint transactionnel appele.

Details sources : [Tradeit.gg](integrations/TRADEIT_GG.md),
[CS.MONEY](integrations/CS_MONEY.md), [Swap.gg](integrations/SWAP_GG.md),
[SkinsMonkey](integrations/SKINSMONKEY.md), [DMarket](integrations/DMARKET.md).
`TradeQuote` et la separation cash/credits etaient deja codes et testes.
Le moteur ne suppose jamais que 100 credits valent 100 EUR.

## Moteurs de valorisation

| Domaine | Delta termine | Limite restante |
| --- | --- | --- |
| ReferencePrice / confiance | Horodatage median de l'echantillon ; filtrage des valeurs futures/perimees ; dernier agregat par fenetre | Prix de reference analytique, pas garantie de revente |
| Liquidite | Preuves de plus de 24 h exclues ; une annonce recente ne rajeunit pas un ancien volume | Couverture partielle, score borne et completude affichable |
| Spread | Dernier snapshot par marche, puis meilleur bid ; quantite zero et restrictions d'item exclues | Une reponse entierement vide ne persiste pas encore de marqueur de snapshot |
| Float | Nom exact + exterior, actifs recents, assets dedupliques, minimum de comparables conserve | Sans asset commun, doublons inter-marches non prouvables |
| Frais | Verification future ou trop ancienne refusee, devise monetaire obligatoire, conflits de priorite refuses | Toutes les etapes de depot/retrait/paiement ne sont pas encore alimentees |
| Profit net | Moteur Decimal et decompositions existants conserves | Profit LIVE nullable sans route complete, frais et FX effectif |
| Opportunites | References/liquidite/spreads/comparables plus conservateurs dans les analyses | Classification complete et optimiseur de routes encore `PARTIAL` |

Le seuil de verification des frais de sept jours est une politique interne
parametrable lors de l'appel, pas une duree annoncee par les marketplaces.
Une absence de frais sourcables reste inconnue, pas zero. Aucune taxe, prime,
marge ou valeur de revente arbitraire n'a ete ajoutee.

Patterns et stickers : modeles et metadonnees existants conserves ; aucune
prime rarete/Fade/sticker appliquee sans source verifiable et comparables.
La valeur d'un sticker libre n'est pas la prime d'un sticker applique.

FX : EUR/USD/GBP/JPY/CHF/CNY, source/date et reference/effectif etaient deja
presentes. La collecte BCE reste optionnelle, sans activation en production.
La configuration fusionnee Compose passe avec valeurs par defaut et override FX.

Voir [PRICE_ENGINE.md](PRICE_ENGINE.md) et [FINANCE_ENGINE.md](FINANCE_ENGINE.md).

## Base et performance

Aucune nouvelle migration ni modification d'index dans cette tranche. Les
modeles V2 sont reutilises ; pas de nouvelle infrastructure. Sur PostgreSQL
jetable, les migrations existantes montent jusqu'a `e6f7a8b9c0d1` et
`alembic check` ne trouve aucune operation manquante.

Les requetes historiques globales de recalcul restent a borner pour de gros
volumes ; la pagination scanner existante est conservee. Les bornes de collecte,
le cache HTTP et la deduplication ne constituent pas un benchmark de charge.

Le volume de test `cs2-source-validation_postgres_data` a ete supprime a la fin.
La base de production conserve la revision `2f8c9d1a4b70` ; taille mesuree en
lecture seule : 9 451 187 octets a 15:39 UTC. Aucun backup, restore ou migration
de production n'a ete declenche dans cette tranche.

## Validation executee

| Controle | Resultat |
| --- | --- |
| `pytest -q` | 94 tests reussis, 2 avertissements de deprecation de dependances |
| `ruff check .` | Succes |
| `ruff format --check .` | 67 fichiers conformes |
| `mypy app` | 44 fichiers, aucune erreur |
| `npm test` | 42 tests reussis |
| `npm run lint` | Succes |
| `npm run typecheck` | Succes |
| `npm run build` | Succes |
| `npm audit --audit-level=high` | 0 vulnerabilite signalee |
| Docker build API + web | Succes, images de validation separees |
| `alembic upgrade head` / `alembic check` | Succes sur PostgreSQL 17.11 isole |
| Configuration Compose fusionnee | Conformite privee/hardening/FX, valeurs par defaut et override |
| Smoke Skinport reel | `online`, 2 observations, 8 agregats, 0 vente unitaire, 0 ecriture DB |
| Smoke CSFloat / DMarket sans cles | `not_configured`, aucune annonce reelle revendiquee |
| Playwright registre | API reelle locale, 18 sources, SkinSniper reference sans collecte |
| Playwright parcours existants | Dashboard, marches, integrations, scanner, detail, watchlist |
| Playwright desktop/mobile | 1440, 390 et 360 px, aucune erreur console/page, aucun overflow horizontal |

Les parcours watchlist ont verifie creation, correspondance prix/float,
persistance apres rechargement, isolation LIVE/DEMO, modification, pause et
suppression. Les donnees DEMO sont synthetiques et restent separees du live.

Scripts reproductibles : `scripts/tests/source-registry-browser.mjs` et
`scripts/tests/watchlist-browser.mjs`. Ils exigent une pile localhost isolee et
un compte temporaire fourni par variables d'environnement. Captures inspectees
dans `/tmp/cs2-source-evidence-20260914/`, dont `sources-1440.png` et
`sources-360.png`. Les tests ont utilise Playwright 1.55 avec son image compatible.
Deux echecs initiaux du harnais (montage read-only puis versions navigateur
incompatibles) ont ete corriges avant la passe complete reussie.

## Production et services preserves

Production **non modifiee**, SHA toujours
`378b6f0494a042d434e42acd8b2dc014413eecb6`. Ses trois conteneurs sont healthy,
avec uptime de six jours ; seul le web publie `100.73.99.88:3000`. Le healthcheck
HTTP confirme API et base healthy, Skinport online, CSFloat/DMarket not_configured.
Ce Skinport de production est l'ancien code, pas une preuve de deploiement des
nouveaux changements.

Server Panel, Apache, Cockpit socket et Tailscale sont actifs ; Crafty conserve
son uptime et ses publications. L'integration Server Panel existante n'a pas
ete refaite. Ses commandes start/stop/restart n'ont pas ete exercees puisque
aucun deploiement n'etait autorise. AdGuard, Minecraft, SSH et reseau n'ont pas
ete modifies ou redemarres.

La pile temporaire utilisait uniquement `127.0.0.1:3000` et `127.0.0.1:8000`,
une base distincte et des secrets ephemeres non affiches. Ses conteneurs,
reseau et volume ont ete supprimes ; aucun service de developpement permanent
n'a ete laisse en fonctionnement.

## Acces manquants et prochaine tranche

Variables manquantes pour preuves authentifiees : `CSFLOAT_API_KEY`,
`DMARKET_PUBLIC_KEY`, `DMARKET_SECRET_KEY`. Aucun secret n'est inclus au rapport.
Les autorisations partenaires White.Market, HaloSkins et SkinBaron restent a
obtenir/confirmer ; GitHub ne dispose pas d'une authentification d'ecriture.

Suite recommandee, sans prerequis de deploiement V0.10 :

1. Marqueurs de snapshots complets/vides et revalidation de bids applicables a
   l'item exact, puis raccordement des routes aux frais et FX effectifs.
2. Smoke CSFloat/DMarket avec cles autorisees fournies dans l'environnement,
   sans transaction ni exposition de leurs valeurs.
3. Revalidation du schema/unites/identifiants Skinport feed avant tout transport
   Socket.IO, reconnexion ou collecte continue.
4. Nouveau collecteur autorise apres verification des droits, unites et quotas,
   avec allowlist read-only des routes, notamment pour Waxpeer.
5. Bornage SQL de l'historique et tests de volume avant extension de la collecte.

SkinSniper reste une reference secondaire : aucun besoin d'API privee,
de scraping ou d'hypothese de profit pour poursuivre ce travail.
