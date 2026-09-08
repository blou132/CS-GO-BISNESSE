# SkinBaron

- Statut : `REQUIRES_APPROVAL`
- Site officiel : <https://skinbaron.de/special/sbapi?language=en>
- Documentation officielle : <https://skinbaron.de/misc/apidoc/>
- Vérification : 8 septembre 2026

SkinBaron publie une API officielle couvrant notamment `Search`, `BestDeals`,
`NewestItems`, `GetNewestSales30Days`, `GetPriceList` et
`GetExtendedPriceList`. L'accès exige toutefois une approbation demandée au
support depuis un compte SkinBaron, et chaque fonctionnalité peut être activée
séparément.

Aucun appel n'est implémenté sans cette approbation. Un futur adaptateur sera
strictement read-only et n'activera jamais `BuyItems`, `ListItems`, modification
de prix ou retour d'objets.
