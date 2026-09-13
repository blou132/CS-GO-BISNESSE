# SkinSniper

- Role : `AGGREGATOR`, `REFERENCE_SOURCE`, `MARKET_DISCOVERY_SOURCE`.
- Site officiel : <https://skinsniper.com/>.
- Derniere verification : **2026-09-13**.
- API publique exploitable : **API_NOT_FOUND** dans les ressources examinees.
- Decision d'integration : **RESEARCH_REQUIRED**, reference humaine seulement.
- Etat applicatif : `not_integrated`, aucune collecte, aucune cle demandee.

## Recherche officielle

Requetes effectuees, restreintes a `skinsniper.com` :

```text
SkinSniper official API
SkinSniper developer API
SkinSniper public API
SkinSniper partner API
```

Les quatre recherches ciblees n'ont pas donne de contrat d'API. Une recherche
plus large API/developer/partner et la navigation officielle ont trouve
[l'extension](https://skinsniper.com/extension) : SkinSniper y indique que son
extension utilise son API et que le code de l'extension est ouvert. Cela prouve
un usage par leur propre client, PAS une API publique ou partenaire autorisee
pour ce projet. Aucune URL d'endpoint, schema, licence de reutilisation des
donnees, quota ou contrat tiers exploitable n'a ete trouve dans ces pages.

`API_NOT_FOUND` signifie donc "contrat officiel tiers non trouve", pas
"aucune API n'existe". `PARTNER_API` n'est pas confirme et `PRIVATE_API` n'est
pas classe comme un acces documente. Aucun code d'extension, trafic reseau,
endpoint prive, cookie Steam ou mecanisme anti-bot n'a ete analyse ou contourne.

## Marches couverts et decouverte

Le [comparateur de marches](https://skinsniper.com/tools/market-comparison)
affiche Steam, CSFloat, CS.MONEY, DMarket, HaloSkins, Skinflow, BUFF Market,
SkinsMonkey, Skinport, White Market et Waxpeer. Il affiche aussi des frais et
caracteristiques commerciales. Ce releve est une liste de candidats, pas une
validation de leurs donnees ou de leurs autorisations API.

Les acces propres a ces plateformes sont qualifies dans
[MARKET_DISCOVERY.md](MARKET_DISCOVERY.md). BUFF Market et BUFF 163 restent
deux sources distinctes. Tradeit.gg ne doit jamais etre confondu avec tradeit.app.

## Outils et donnees visibles

L'[accueil officiel](https://skinsniper.com/) reference des outils de comparaison,
mouvement de prix, alertes, valorisation d'inventaire et inspection/stickers.
Le [comparateur de prix](https://skinsniper.com/tools/price-comparison) presente
des prix par marche et leurs ecarts absolus/pourcentages, filtres par variante
et etat. Aucune ligne de prix n'est importee dans notre stockage.

Le [Fade Pattern Finder](https://skinsniper.com/tools/fades) associe modele,
seed et pourcentage affiche, avec inspection. Utilite retenue : verification
visuelle secondaire. Ni table de seeds ni regle de rarete ni prime ne sont
copiees sans provenance, date, methode verifiable et droit d'utilisation.

## Limites et validation d'arbitrage

Un `Difference %` n'est jamais un benefice net, meme si l'ecart est extreme.
Avant toute opportunite realisable, notre moteur devra verifier : annonce
encore active, identite exacte, float/pattern/stickers, demande et ventes
comparables, liquidite, fraicheur, frais d'achat/vente/depot/retrait/paiement,
FX effectif et trade lock. Un prix demande eleve n'est pas une offre d'achat.

SkinSniper n'est pas une source de verite unique et ne fournit actuellement
aucune preuve au Price Engine du projet. Une future comparaison de nos spreads
avec les siens restera secondaire et n'aura lieu qu'avec un acces autorise,
des dates/devise/objets comparables et aucune substitution au profit net.

## Integration decision

Pas de `SkinSniperAdapter`. Registre et lien de reference uniquement.
Pour reexaminer cette decision : obtenir une documentation officielle tiers
(publique ou partenaire), ses droits de reutilisation, l'authentification,
les quotas et les garanties de fraicheur. Aucune automatisation du site en attendant.
