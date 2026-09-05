# Modèle de données

Les montants sont des décimaux, jamais des nombres binaires flottants dans le
moteur financier. Les propriétés indisponibles restent `null`. Les lignes
`demo` et `live` ont des clés d'unicité séparées afin qu'une fixture ne puisse
pas remplacer une observation réelle.

## Tables persistées

### `cs2_items`

Identité normalisée d'un exemplaire provenant d'une plateforme :
`market_hash_name`, arme, skin, exterior, StatTrak, Souvenir, float, paint
index, paint seed, phase Doppler, pourcentage Fade et inspect link. Le couple
plateforme/identifiant externe est unique dans un mode de données.

Le modèle ne déduit pas une phase, un pattern ou un float absent. La séparation
weapon/skin/exterior issue du nom sert de commodité ; le nom de marché original
reste toujours conservé.

### `item_stickers`

Un sticker possède nom, slot, usure, prix Steam non appliqué et valeur ajoutée
estimée. Ces deux derniers montants sont indépendants. L'adaptateur n'utilise
jamais automatiquement le prix du sticker non appliqué comme premium.

### `market_listings`

Une annonce conserve plateforme, identifiant externe, objet, prix/devise
originaux, montant EUR de référence facultatif, taux/source/date FX, URL,
dates de publication et d'observation, et avertissements. `raw_payload` n'est
pas stocké dans le MVP : cela réduit la rétention de champs inutiles ou
sensibles. Les fixtures HTTP restent dans les tests lorsqu'elles sont utiles.

### `price_observations`

Une observation associe nom de marché, plateforme, prix/devise originaux,
conversion EUR facultative, nature et horodatage. Les types persistables sont
`LISTING`, `SALE`, `BUY_ORDER`, `TRADE_VALUE` et `AGGREGATE`. Un fingerprint
évite de réinsérer la même observation collectée. Un agrégat ne devient pas
une vente ni un listing individuel.

### `market_sync_states`

Dernier essai et dernier succès par plateforme et mode. Une erreur met à jour
l'essai et le message, mais ne modifie pas la date du dernier succès ni les
données déjà conservées.

### `pattern_rules`

Structure préparatoire : skin, seed, catégorie, tier, premium estimé,
confiance, source et date de vérification. La table est vide par défaut.
Aucune règle de rareté n'est fournie sans source.

## DTO des adaptateurs

`AdapterItem`, `AdapterListing`, `AdapterSticker` et `AdapterObservation`
isolent le reste du produit du JSON propre à chaque plateforme. Les champs
sont validés avant persistance : décimaux positifs, float entre 0 et 1,
devise ISO sur trois lettres et timestamps avec fuseau.

`AdapterResult` contient séparément annonces individuelles, observations
agrégées/historiques et avertissements. `MarketAdapter` expose recherche,
lecture d'une annonce quand l'API le permet, statistiques et fermeture du
client réseau.

La comparaison calcule minimum, moyenne et médiane par plateforme et nature
d'observation. Lorsqu'au moins deux plateformes ont le même type de donnée,
elle expose aussi l'écart médian absolu et relatif face à la meilleure médiane.

## Valeur, float et opportunité

Une estimation de valeur requiert au moins trois observations `SALE`
convertibles en EUR. Elle utilise leur médiane et fournit une confiance
descriptive. Les listings et agrégats ne satisfont pas cette condition.

Le score float est un percentile inversé parmi au moins cinq exemplaires du
même `market_hash_name`, avec mi-rang pour les ex aequo. Il ne crée aucune
prime universelle.

Le score d'opportunité initial n'est calculé que pour la démo, où les ventes
et 10 % de frais de vente sont explicitement synthétiques. Pondération
centralisée : écart 30 %, liquidité 20 %, historique 20 %, float 15 %,
confiance marché 10 %, risque 5 %. Les pondérations vivent dans un objet
immuable remplaçable et le calcul possède un test dédié. En live, profit, ROI et score restent
inconnus tant que les frais effectifs et la route de revente ne le sont pas.

## Concepts futurs non persistés

- `FxQuote` conservera devise/montant originaux, devise de référence, taux,
  source, date et nature `reference` ou `effective`.
- `TradeQuote` séparera valeurs affichées par la plateforme et valeurs cash
  estimées des objets donnés/reçus, avec frais et expiration.
- `Purchase` conservera prix/devise originaux, prix EUR effectif, frais et note.
- `WatchRule` exprimera critères d'identité, float, phase, seeds et prix.

Ces concepts seront ajoutés par migrations lorsque leurs usages seront
implémentés. Aucun graphe de route ni modèle d'achat automatisé n'existe dans
la base actuelle.
