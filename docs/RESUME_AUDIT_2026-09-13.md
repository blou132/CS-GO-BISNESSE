# Audit de reprise : sources et valorisation

Point de depart : `472750b`, branche `feat/mvp-foundations`, arbre propre,
19 commits devant `origin/feat/mvp-foundations`. Rapport precedent lu :
[DATA_MARKETS_REPORT_2026-09-13.md](DATA_MARKETS_REPORT_2026-09-13.md).

`DONE` signifie present et teste dans le depot, pas deploye. `PARTIAL`
signifie un socle existant a completer, `TODO` un travail absent,
`BLOCKED_EXTERNAL` un besoin d'acces ou de contrat externe. Cette matrice
decrit l'etat AVANT la nouvelle tranche ; le rapport de fin consigne les deltas.

| Section du nouveau brief | Etat initial | Preuve / manque |
| --- | --- | --- |
| 0. Reprise et etat actuel | DONE | README, rapport, roadmap, architecture, git et code inspectes |
| 1. Sources live | PARTIAL | Trois adaptateurs dans `app/markets`; tests HTTP, pas tous valides avec compte |
| 2. SkinSniper | TODO | Absent du registre et de `docs/integrations` |
| 3. Registre central | PARTIAL | `markets/registry.py`, API et page integrations existent ; nouveaux candidats absents |
| 4. Skinport | PARTIAL | REST/historique et normaliseur feed ; transport feed absent, pacing REST a corriger |
| 5. CSFloat | PARTIAL | Champs exacts presents ; validation de filtres et epreuves read-only a renforcer |
| 5. CSFloat live authentifie | BLOCKED_EXTERNAL | `CSFLOAT_API_KEY` |
| 6. DMarket | PARTIAL | Offers, targets, ventes, frais signes ; echec enrichissement annule les offres |
| 6. DMarket live authentifie | BLOCKED_EXTERNAL | `DMARKET_PUBLIC_KEY`, `DMARKET_SECRET_KEY` |
| 7. Nouvelles marketplaces | PARTIAL | SkinBaron/GamerPay audites ; BUFF, White, Waxpeer, HaloSkins, Skinflow a qualifier |
| 8. Data Model V2 | DONE | Modeles distincts dans `models/entities.py`, migration `9b7c6d5e4f30` |
| 9. Price Engine V2 | PARTIAL | `pricing/valuation.py` : reference hierarchisee, confiance ; fraicheur de preuves a renforcer |
| 10. Liquidite | PARTIAL | Score/categorie/completude presents ; assemblage accepte des volumes anciens |
| 11. Spread | PARTIAL | Ask/bid en Decimal ; anciens targets et restrictions item a exclure |
| 12. FX | DONE | BCE historisee, reference/effectif distincts, configuration corrigee ; aucune activation automatique |
| 13. Frais | PARTIAL | Calcul et stockage existants ; regles futures/anciennes et ambiguite a traiter |
| 14. Profit net | PARTIAL | Decompositions Decimal testees ; raccordement automatique aux routes live absent |
| 15. Opportunites | PARTIAL | Score/snapshots existants, aucun profit live invente ; categories/routes a completer |
| 16. Float | PARTIAL | Comparaison par nom exact, minimum 5 ; echantillons repetes/perimes a filtrer |
| 17. Patterns | PARTIAL | `PatternRule`, phase/seed/fade ; aucune prime sourcee integree |
| 18. Stickers | PARTIAL | Nom/slot/wear et valeurs separees ; premium applique inconnu |
| 19. Sources de trade | PARTIAL | Recherche du 8 septembre et refus d'endpoints prives ; actualisation necessaire |
| 20. TradeQuote | DONE | Modele, expiration, frais et valorisation cash testee ; aucun provider live revendique |
| 21. Cash / credits | DONE | `pricing/trades.py` refuse les sommes cash incompletes |
| 22. Scanner | DONE | `6274019`, pagination/tri/filtres SQL ; ne pas reecrire |
| 23. Watchlist | DONE | `b04b752`, CRUD/matches/protection/modes ; ne pas recreer |
| 24. Performance | PARTIAL | Index et upsert presents ; historique et futurs flux a borner |
| 25. Production | DONE | Conservation volontaire ; validation isolee uniquement pour cette tranche |
| 26. Server Panel | DONE | Integration existante ; aucun changement requis |
| 27. Services existants | DONE | Hors perimetre des modifications |
| 28. GitHub | BLOCKED_EXTERNAL | Pas d'authentification d'ecriture au dernier essai ; commits locaux conserves |
| 29. Validation | TODO | Relancer toutes les suites apres la nouvelle tranche |
| 30. Commits | TODO | Nouveaux commits atomiques sans reecriture d'historique |
| 31. Rapport final | TODO | Distinguer recherches, contrats testes, collecte live et production |

## Decisions de perimetre

- Ne pas recreer les modeles V2, le scanner, la watchlist, FX ou l'authentification.
- Aucun deploiement ; aucune migration en production ni modification d'un autre service.
- SkinSniper : recherche officielle seulement, jamais de scraping de prix ou
  d'analyse de ses endpoints internes. Un pourcentage d'ecart n'est pas un profit.
- Renforcer les contrats des sources et les garde-fous de valorisation avant
  d'ajouter une optimisation de routes ou une prime arbitraire.
