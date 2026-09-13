# Decouverte de marketplaces : 13 septembre 2026

Recherche limitee aux sites et documentations des plateformes. Les noms venant
de [SkinSniper](skinsniper.md) ne conferent aucune autorisation API. "Inconnu"
signifie non verifie, jamais gratuit, illimite ou egal a zero.

| Source | API / authentification | Donnees de lecture documentees | Frais, devise, quotas, conditions | Decision |
| --- | --- | --- | --- | --- |
| CSFloat | [API officielle](https://docs.csfloat.com/), cle Authorization | Annonces fixes actives, float/index/seed/stickers/inspect/date ; ventes non documentees | Prix cents USD ; quotas chiffres generaux non trouves dans cette reference ; frais effectifs non collectes | Adaptateur existant, test avec cle requis |
| Skinport | [REST public](https://docs.skinport.com/sales/history), [feed officiel](https://docs.skinport.com/websocket/sale-feed) | Historique agrege 24 h/7/30/90 j ; feed listed/sold | EUR demande ; REST 8/5 min, cache 5 min, Brotli ; pas de frais cash-out universels supposes | Completer REST ; ne pas declarer feed LIVE |
| DMarket | [Swagger officiel](https://docs.dmarket.com/v1/swagger.html), Ed25519 | Offers, targets, last-sales, customized-fees, attributs CS2 | USD, frais retournes par compte/item ; quotas via FAQ ; operations transactionnelles hors perimetre | Adaptateur read-only existant, cles requises |
| SkinBaron | [Approbation officielle](https://skinbaron.de/special/sbapi?language=en), [Swagger](https://skinbaron.de/misc/apidoc/) | Capacites individuelles soumises a autorisation ; recherche/ventes selon fiche existante | Frais/devises/quota de chaque methode a confirmer avec l'acces | `REQUIRES_APPROVAL` |
| GamerPay | [Annonce officielle de fermeture](https://gamerpay.gg/shutting-down) | Fin des nouveaux trades/listings annoncee au 8 mai, fermeture au 29 mai 2026 | Pas de nouvel adaptateur | `UNAVAILABLE` |
| White.Market | [Docs partenaire](https://api.white.market/docs_partner/index.html), [token puis JWT 24 h](https://api.white.market/docs_partner/3-authorization.html) | GraphQL search/details, float/pattern/phase/stickers ; SSE/WebSocket ; historique du compte distinct de ventes globales | [Exports](https://api.white.market/docs_partner/5-skins-buy/products.html) publics avec `data_as_of` ; USD dans schema ; frais cash-out/quota global inconnus ; [conditions API](https://white.market/pl/terms-of-use) a respecter | `REQUIRES_APPROVAL`, aucun appel partenaire ni export massif |
| Waxpeer | [OpenAPI officiel](https://api.waxpeer.com/docs), cle serveur | Prices/count, annonces par nom, disponibilite, buy orders, phases ; historique a qualifier quant au perimetre compte/global | Unite monetaire, frais, attributs exacts et quota a confirmer avant normalisation ; **des GET achetent et suppriment** | `OFFICIAL_API`, non integre ; liste blanche de routes obligatoire |
| HaloSkins | [Open Platform](https://www.haloskins.com/html/openDoc/catalogue.html), app-key approuvee | Annonces paginees, statut, prix USD, float/index/seed/stickers/phase ; suivi WebSocket ; historique des commandes du compte | Les lectures peuvent utiliser POST ; pas de ventes globales supposees ; `gradient` non traduit en prime/Fade sans contrat ; quota/frais cash-out non verifies | `REQUIRES_APPROVAL` |
| BUFF Market | [Site officiel](https://buff.market/) et recherche `site:buff.market API developer` | Aucun contrat tiers trouve dans les pages examinees | Auth, listings, ventes, float, frais, devise API, quota et reutilisation inconnus | `RESEARCH_REQUIRED` |
| BUFF 163 | [Site officiel](https://buff.163.com/) non exploitable dans l'outil ; recherche officielle sans contrat exploitable | Aucun endpoint prive explore | Ne pas transposer le contrat ou la devise de BUFF Market | `RESEARCH_REQUIRED` |
| Skinflow | [Site officiel](https://skinflow.gg/trade) et recherche `site:skinflow.gg API documentation` | Parcours commerciaux de trade, aucune documentation API tiers trouvee | Auth/quotas/frais d'API inconnus ; la page distingue solde du site et retrait cash | `RESEARCH_REQUIRED` |
| Steam | [Web API officielle](https://steamcommunity.com/dev) | Aucune API publique de prix Market validee pour ce projet | Steam Wallet non assimile a du cash retirable ; pas d'endpoint interne de prix | `RESEARCH_REQUIRED` |

## Priorite d'integration suivante

1. Valider CSFloat et DMarket avec les cles personnelles, sans achat ni vente.
2. Valider le contrat Skinport live avant d'ajouter un transport durable.
3. Etudier une collecte bornee Waxpeer ou White.Market, avec autorisation et
   unite monetaire explicites ; un export de plusieurs millions de lignes
   ne doit pas etre charge aveuglement en memoire.
4. HaloSkins/SkinBaron : approbation externe puis contrat read-only teste.

La recherche des plateformes de trade est dans [TRADE_SOURCES_RESEARCH.md](../TRADE_SOURCES_RESEARCH.md).
