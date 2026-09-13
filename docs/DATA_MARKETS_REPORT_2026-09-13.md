# CS2 Arbitrage Hub : état de la passe data au 13 septembre 2026

Relevé de production : 11:43 UTC. Ce rapport distingue le code vérifié dans
la pile temporaire et la V0.9 conservée en production. Il ne déclare pas la
grande mission entièrement terminée : les limites restantes sont listées en fin.

## État Git

- Dépôt : `/home/serve/CS-GO-BISNESSE`.
- Branche : `feat/mvp-foundations`.
- SHA du code vérifié : `8e7a9d33a4dffa48e4696d0aa1b37b032c579dc9`.
- Remote après `git fetch origin` : `2a636e7caeb5b46146e3927a2236b50108c1fbf8`.
- 18 commits locaux en avance au relevé, avant le commit de ce rapport.
- Synchronisation : **LOCAL COMMITS NOT PUSHED**.

Le fetch public réussit mais ne prouve pas une authentification en écriture.
Le push HTTPS échoue avec `could not read Username`. Un essai SSH en mode
non interactif échoue avec `Permission denied (publickey)`. Aucun identifiant,
token ou changement de configuration Git n'a été ajouté pour contourner cela.

## Production

| Élément | État vérifié |
| --- | --- |
| Checkout `/opt/cs2-arbitrage-hub` | `378b6f0` |
| Frontend | `http://100.73.99.88:3000`, conteneur healthy |
| API | healthy, privée Docker |
| PostgreSQL | healthy, privé Docker |
| Alembic déployé | `2f8c9d1a4b70` |
| Scheduler marché | actif, intervalles observés de 900 secondes |
| Skinport | online, dernière réussite `2026-09-13T11:37:37.158887Z` |
| CSFloat / DMarket | not_configured |
| Listings live | 0 |
| Observations de prix live | 1154 |
| Opportunités live | 0 |

Aucun nouveau déploiement ni migration de production n'a eu lieu. V0.10 est
conservée dans le code sans activation automatique. La configuration de
l'authentification administrateur et l'accord d'activation restent des étapes
distinctes du développement demandé.

## Sources

Les recherches officielles des plateformes ont été documentées le 8 septembre
dans [le registre](integrations/README.md). Elles n'ont pas été refaites lors
de la finalisation scanner/watchlist du 13 septembre.

| Source | Code et recherche | Validation live / accès manquant |
| --- | --- | --- |
| CSFloat | API officielle, annonces exactes, attributs, filtres et stratégies bornées ; tests de normalisation | Clé `CSFLOAT_API_KEY` absente ; aucun smoke test avec compte |
| Skinport REST | Agrégats d'offre et historique 24 h / 7 / 30 / 90 j séparés | Ancien collecteur `/items` online en production ; enrichissement non déployé |
| Skinport Sale Feed | Normaliseur `listed` / `sold` testé ; aucune vente unitaire inventée depuis les agrégats | Transport Socket.IO/MessagePack, reconnexion et file bornée encore non raccordés |
| DMarket | Signature Ed25519, offres, targets/buy orders, ventes et frais read-only testés | `DMARKET_PUBLIC_KEY` et `DMARKET_SECRET_KEY` absentes |
| SkinBaron | API officielle documentée ; registre `REQUIRES_APPROVAL` | Autorisation requise, pas d'adaptateur live |
| GamerPay | Recherche historique consignée comme `UNAVAILABLE` | Aucun adaptateur |
| Tradeit.gg | Aucune API développeur publique exploitable trouvée dans l'audit ; `RESEARCH_REQUIRED` | Accord/contrat requis ; aucune confusion avec Tradeit.app |
| CS.MONEY | Recherche et restrictions documentées ; `RESEARCH_REQUIRED` | Pas d'API partenaire autorisée |
| Swap.gg | `RESEARCH_REQUIRED` | Pas de contrat API officiel exploitable validé |
| SkinsMonkey | `RESEARCH_REQUIRED` | Pas de contrat API officiel exploitable validé |
| DMarket Trade | Réutilisation des données de marché en lecture pour l'analyse | Pas d'exécution de trade |
| BCE | Collecteur SDMX de référence et historique testés | Désactivé par défaut, non activé sur le serveur de production |

La [recherche trade](TRADE_SOURCES_RESEARCH.md) référence les fiches officielles.
La présence d'un parser testé ne signifie pas qu'un flux fonctionne en LIVE.

## Modèles et moteurs

- Modèles distincts : `MarketListing`, `RealizedSale`, `AggregateMarketStat`,
  `BuyOrderObservation`, `TradeQuote`, `FXRate`, `PlatformFeeSchedule`.
- Identité canonique séparée des instances exactes ; les annonces ne sont pas
  fusionnées entre plateformes.
- `ReferencePrice` : méthode, sources, date et confiance ; ventes réalisées,
  médianes historiques, demandes et annonces restent distinguées.
- Liquidité, spread, confiance et risque : calculs testés, données absentes
  représentées par `null`.
- Float : comparaison du même skin, score seulement si l'échantillon suffit ;
  pas de prime monétaire universelle. Les modèles pattern/stickers existent,
  mais les règles avancées vérifiées et leurs primes restent à compléter.
- FX : EUR, USD, GBP, JPY, CHF, CNY ; montants originaux conservés ; taux BCE
  `REFERENCE` historisés séparément des futurs taux `EFFECTIVE`.
- Frais : BUY, SELL, DEPOSIT, WITHDRAW, TRADE, PAYMENT, FX ; source, date,
  devise, tranche et éventuelle spécificité item. Pas de commission inventée.
- Profit net : coûts d'achat et revenus de vente détaillés, ROI, durée de
  détention explicitement fournie pour ROI/jour. Le calculateur fonctionne ;
  la sélection automatique de routes live complètes reste à raccorder.
- TradeQuote : séparation crédits affichés / valeur cash, frais explicites,
  spread et confiance ; aucune quote partielle additionnée comme complète.
- Opportunités live : toujours aucune dans la production actuelle. Les exemples
  avec profits positifs du navigateur utilisent exclusivement des fixtures DEMO.

## Scanner et watchlist livrés dans le code

`6274019` ajoute les snapshots d'analyse et `/api/scanner` : filtres, tri et
pagination SQL. Le dashboard est limité à 100 annonces ; le détail charge le
skin visé. La navigation mobile est nommée et le texte accessible caché ne
provoque plus de débordement horizontal.

`b04b752` ajoute `/watchlist` et son API : création, édition, pause, suppression
confirmée et correspondances paginées. Filtres : nom exact, marché, prix maximal
EUR, float maximal, phase et seeds. Les bornes sont inclusives, les valeurs
inconnues exclues des filtres correspondants, et LIVE/DEMO restent isolés.

Les écritures sont protégées par session administrateur et contrôle d'origine
dans Next.js. Les montants conservent leur précision. Les règles utilisent la
table `watch_rules` existante, sans nouvelle migration. Elles filtrent les
annonces collectées ; elles ne déclenchent actuellement aucune collecte ni
notification automatique. Voir [WATCHLIST.md](WATCHLIST.md).

`8e7a9d3` transmet les paramètres BCE dans Compose, aligne la fraîcheur par défaut
sur 120 heures et corrige les valeurs factices du contrôle CI de configuration.
La CI inclut aussi `npm audit`. Le collecteur reste désactivé par défaut.

## Validation

| Contrôle | Résultat |
| --- | --- |
| Backend `pytest` | 67 tests réussis, 2 avertissements de dépendances |
| Ruff / format | Succès, 63 fichiers conformes |
| Mypy | Succès, 43 fichiers source |
| Frontend `npm test` | 41 tests réussis |
| ESLint / typecheck / build | Succès |
| `npm audit --audit-level=high` | 0 vulnérabilité signalée |
| Build Docker API + frontend | Succès dans le projet temporaire |
| Alembic sur PostgreSQL temporaire | Migration jusqu'à `e6f7a8b9c0d1` et `check` sans opération manquante |
| Cycle migration scanner du 12 septembre | Upgrade, check, downgrade vers `c4e8a10d7b21`, nouvel upgrade et check réussis |
| Compose production fusionné | Conformité des réseaux/ports/permissions, paramètres FX par défaut et surchargés |
| Scripts de backup | Syntaxe et tests des helpers réussis |
| Playwright | Dashboard, markets, scanner, item, integrations, watchlist |
| Watchlist navigateur | Création, correspondance prix/float, rechargement, mode, édition, pause, suppression |
| Mobile | 390/390 et 360/360 px, aucun débordement du document, aucune erreur console |

La mesure synthétique scanner du 12 septembre utilisait 100 000 annonces et
100 000 snapshots : 50 premières lignes en 0,68 s ; 100 lignes à la page 250
d'un ensemble filtré de 25 080 en 0,58 s. Il s'agit d'un test local, pas d'un
SLA ni du volume live. Voir [SCANNER_API.md](SCANNER_API.md).

Les captures du parcours watchlist sont dans `/tmp/cs2-watchlist-check` sur
le serveur. Le script reproductible est `scripts/tests/watchlist-browser.mjs`.
La pile `cs2-pagination-visual` utilisait seulement localhost, des identifiants
de test et un volume PostgreSQL séparé ; ses conteneurs et son volume de
fixtures ont été supprimés à l'issue des vérifications.

## Server Panel et services existants

- `server-panel`, `apache2`, `cockpit.socket`, `tailscaled` : actifs au relevé.
- Crafty : conteneur toujours démarré depuis 5 jours.
- Panel `/dashboard` : réponse 302 vers l'authentification.
- Carte CS2 et actions start/stop/restart/logs : intégration conservée ; pas de
  nouveau test authentifié ni d'action destructive sur la production.
- Aucun changement Apache/portfolio, AdGuard, Minecraft, Cockpit, Tailscale,
  UFW, SSH, route, IP, DNS, DHCP ou configuration réseau.

## Commits principaux de la passe

| SHA | Objet |
| --- | --- |
| `d1e223b` | Registre des sources |
| `70e3722` | Modèles normalisés V2 |
| `d5b9183` | Ingestion marché enrichie |
| `5ff2eaa` | Référence, liquidité et spread |
| `2bde4f6` | Change multi-devises |
| `1d3b2e3` | Frais sourcés et profit net |
| `b900e40` | Fondation TradeQuote |
| `e4e9bd7` | UI des données et intégrations |
| `6274019` | Scanner paginé |
| `b04b752` | Watchlist persistante |
| `8e7a9d3` | Configuration FX et CI |

## Prérequis externes et suite

- Rétablir l'authentification GitHub depuis un terminal local, puis pousser
  `feat/mvp-foundations`. Ne fournir aucun token dans le chat.
- Ajouter les clés personnelles uniquement dans
  `/opt/cs2-arbitrage-hub/.env.production` (permissions 600), sans Git ni navigateur.
  Les clés actuellement manquantes sont celles de CSFloat et DMarket.
- Conserver V0.10 sans activation tant que l'administrateur n'a pas choisi son
  mot de passe dans le terminal et demandé sa mise en production.
- Compléter la rotation de collecte watchlist, le transport du feed Skinport,
  les smoke tests avec clés, le circuit breaker du scheduler et les catégories
  d'opportunités. L'audit BUFF/YouPin et autres candidats reste également à faire.
- Version suivante du moteur : V0.15, analyse float/pattern/stickers sourcée,
  puis raccordement des frais et des demandes aux routes de revente calculables.

Le déploiement futur devra réutiliser le backup pré-migration et le workflow
existants, puis valider les services et l'intégration Panel. Les tests isolés
présentés ici ne sont pas une preuve de déploiement de V0.11+ en production.
