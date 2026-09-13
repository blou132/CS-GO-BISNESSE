# Recherche des sources de trade

Vérification : 13 septembre 2026. Seules les surfaces officielles ont servi à
prendre une décision d'intégration.

| Source | API officielle trouvée ? | Documentation | Auth / restrictions | Quote read-only | Décision |
| --- | --- | --- | --- | --- | --- |
| Tradeit.gg | non publiée | centre d'aide uniquement | partenariat à confirmer | non documentée | `RESEARCH_REQUIRED` |
| CS.MONEY | non publiée | conditions d'utilisation | consentement écrit exigé pour une application tierce | non documentée | `RESEARCH_REQUIRED` |
| Swap.gg | non publiée | centre d'aide uniquement | partenariat à confirmer | non documentée | `RESEARCH_REQUIRED` |
| SkinsMonkey | non publiée | centre d'aide uniquement | partenariat à confirmer | non documentée | `RESEARCH_REQUIRED` |
| DMarket Trade | oui | Swagger officiel | clés Ed25519 | données de marché, targets, ventes et frais en lecture | utiliser uniquement les GET analytiques |

« Non publiée » signifie qu'aucun contrat développeur public n'a été trouvé;
cela ne constitue pas une preuve d'inexistence d'une API privée ou partenaire.
Le projet n'utilise aucun scraping, cookie Steam, endpoint privé ou transaction.

Nouvelle verification : [Tradeit](https://support.tradeit.gg/en/),
[Swap.gg](https://help.swap.gg/en/), [SkinsMonkey](https://skinsmonkey.com/help)
et leurs recherches officielles n'ont pas fourni de contrat developpeur tiers.
Les [conditions CS.MONEY](https://cs.money/tos/) continuent a exiger un accord
ecrit pour une application tierce ; son solde Trade n'est pas retirable.
Le [Swagger DMarket](https://docs.dmarket.com/v1/swagger.html) reste la source
des lectures analytiques signees, pas d'une quote d'echange cash executable.
Pour les quatre premieres plateformes, auth partenaire, devises de quote,
frais effectifs et limites API restent inconnus. Les tarifs d'une page
commerciale ou d'un comparateur ne deviennent pas des frais transactionnels.

## Fondation TradeQuote

Le moteur `pricing/trades.py` accepte des quotes déjà obtenues par une source
autorisée. Il sépare pour chaque côté les crédits affichés par la plateforme et
la valeur cash EUR issue du Price Engine. Il calcule uniquement lorsque toutes
les valorisations nécessaires sont connues :

- valeur cash donnée et reçue ;
- frais explicites ;
- différence cash nette ;
- ratio cash reçu/donné ;
- spread effectif ;
- confiance bornée par la qualité de la source et des valorisations.

Une valorisation partielle n'est jamais additionnée comme si elle était
complète. Aucun provider live ni endpoint d'exécution n'est déclaré tant qu'un
contrat officiel read-only n'est pas disponible.
