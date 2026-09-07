# Roadmap

Les numéros décrivent les étapes du produit, pas une promesse de couverture
complète à la première livraison. Une intégration testée sur fixtures n'est
pas une intégration validée avec un compte réel. Voir `VALIDATION.md` pour
les preuves d'exécution de cette passe.

| Version | Périmètre | Condition de validation |
| --- | --- | --- |
| V0.1 | FastAPI, Next.js, PostgreSQL, Compose, configuration, healthchecks, migrations, tests et lint | Lancement local et contrôles reproductibles |
| V0.2 | Catalogue et modèle normalisé CS2 | Champs inconnus null, schémas, persistance et tests |
| V0.3 | CSFloat | API officielle, normalisation et erreurs ; validation réelle séparée |
| V0.4 | Skinport | Agrégats conservés comme agrégats, pas d'exemplaires inventés |
| V0.5 | DMarket | API officielle signée, tests puis validation avec clés |
| V0.6 | Comparaison multi-market | Même identité, devise comparable et nature du prix explicite |
| V0.7 | Historique et statistiques | Horodatage, volumes et source sans doublons de collecte |
| V0.8 | Float Analyzer | Comparables du même skin, percentile descriptif, aucune prime universelle |
| V0.9 | Opportunity Scanner | Score documenté, filtres, frais explicites, confiance et limites visibles |
| V0.9.1 | Continuous Market Monitoring | Scheduler optionnel, statuts détaillés, métriques et persistance non destructive |

La préparation d'exploitation 24/7 complète ce socle : surcharge Compose de
production, sauvegarde et restauration PostgreSQL, déploiement avec migration
unique, logs bornés, scheduler optionnel et états séparés de l'application,
de la base et des sources externes. Elle ne change pas le périmètre
lecture/analyse du MVP.

Le premier MVP vise la lecture et l'analyse. Les annonces, même nombreuses,
ne suffisent pas à établir une valeur de revente fiable. L'absence d'historique
de ventes ou de frais effectifs doit produire une valeur inconnue, pas un
profit artificiel. Les calculs démontrés avec des fixtures restent DEMO.

## Versions suivantes — non implémentées dans cette passe

| Version | Fonction |
| --- | --- |
| V0.10 | Portfolio |
| V0.11 | Pattern Analyzer avec règles sourcées |
| V0.12 | Sticker Analyzer, valeur appliquée séparée du prix non appliqué |
| V0.13 | Trade Engine |
| V0.14 | Première plateforme de trade autorisée |
| V0.15 | Autres plateformes de trade |
| V0.16 | Currency Engine, fournisseur FX et taux effectifs |
| V0.17 | Fee Engine avancé |
| V0.18 | Profit net réel avec tous les coûts de transaction |
| V0.19 | Watchlist et alertes |
| V0.20 | Opportunity Score avancé |
| V0.21 | Arbitrage Market → Market |
| V0.22 | Market → Trade |
| V0.23 | Trade → Market |
| V0.24 | Route Optimizer |
| V0.25 | Backtesting |
| V1.0 | Version stable |

L'authentification devient un préalable à tout accès distant. Les achats
et l'acceptation automatique de trades restent hors périmètre.
