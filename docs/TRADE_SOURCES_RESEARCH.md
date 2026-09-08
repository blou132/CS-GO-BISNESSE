# Recherche des sources de trade

Vérification : 8 septembre 2026. Seules les surfaces officielles ont servi à
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
