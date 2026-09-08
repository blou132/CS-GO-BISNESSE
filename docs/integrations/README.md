# Registre des sources

Vérification : 8 septembre 2026. Les capacités ci-dessous proviennent des
documentations ou pages officielles liées dans chaque fiche. L'absence de
documentation publique ne prouve pas qu'aucune API partenaire n'existe : elle
interdit seulement de déclarer une intégration `LIVE` sans accord supplémentaire.

| Plateforme | API | Auth | Listings | Sales | Float | Trade | Fees | Statut |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CSFloat | officielle | clé | oui | non documenté | oui | non | non documenté | `OFFICIAL_API` |
| Skinport | publique + compte | REST public / Basic compte | agrégats + flux | agrégats + flux | flux | non | transactions compte | `PUBLIC_API` |
| DMarket | officielle | Ed25519 | oui | oui | oui | lecture seulement | oui | `OFFICIAL_API` |
| SkinBaron | officielle | clé approuvée | oui | oui | oui | hors périmètre | à vérifier | `REQUIRES_APPROVAL` |
| GamerPay | fermée | — | non | non | non | non | non | `UNAVAILABLE` |
| Steam Market | non documentée | — | non intégré | non intégré | non | non | non | `RESEARCH_REQUIRED` |
| Tradeit.gg | non trouvée | — | non intégré | non intégré | non | recherche | non | `RESEARCH_REQUIRED` |
| CS.MONEY | non trouvée | accord requis | non intégré | non intégré | non | recherche | non | `RESEARCH_REQUIRED` |
| Swap.gg | non trouvée | — | non intégré | non intégré | non | recherche | non | `RESEARCH_REQUIRED` |
| SkinsMonkey | non trouvée | — | non intégré | non intégré | non | recherche | non | `RESEARCH_REQUIRED` |
| BCE | SDMX publique | aucune | — | — | — | — | — | `PUBLIC_API` |

Le registre exécutable se trouve dans `apps/api/app/markets/registry.py`. Il
reste statique et versionné : les capacités légales et techniques ne sont pas
des données utilisateur et ne nécessitent pas une table modifiable en production.
