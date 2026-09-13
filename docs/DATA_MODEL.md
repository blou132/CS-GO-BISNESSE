# Modèle de données

Les montants sont des décimaux, jamais des nombres binaires flottants dans le
moteur financier. Les propriétés indisponibles restent `null`. Les lignes
`demo` et `live` ont des clés d'unicité séparées afin qu'une fixture ne puisse
pas remplacer une observation réelle.

## Tables persistées

### `canonical_items` et `cs2_items`

`canonical_items` rapproche les sources au niveau du nom de marché, du paint
index et de la variante, avec une empreinte stable séparée par mode. `cs2_items`
représente ensuite l'exemplaire exact provenant d'une plateforme : asset/def
index, float, seed, phase, collection, références SCM, état de trade, inspect
link et attributs source sélectionnés. Le couple plateforme/identifiant externe
reste unique dans un mode de données.

Le modèle ne déduit pas une phase, un pattern ou un float absent. La séparation
weapon/skin/exterior issue du nom sert de commodité ; le nom de marché original
reste toujours conservé.

### `item_stickers`

Un sticker possède nom, slot, usure, prix/volume Steam non appliqués et valeur ajoutée
estimée. Ces deux derniers montants sont indépendants. L'adaptateur n'utilise
jamais automatiquement le prix du sticker non appliqué comme premium.

### `market_listings`

Une annonce conserve plateforme, identifiant externe, objet, prix/devise
originaux, montant EUR de référence facultatif, taux/source/date FX, URL,
dates de publication, première observation et dernière vue, statut et avertissements.
Les statuts sont `ACTIVE`, `INACTIVE`, `SOLD` et `UNKNOWN`. Le MVP ne déduit
pas `SOLD` lors d'une disparition : une annonce excédentaire ou ancienne peut
être marquée `INACTIVE`, mais l'objet et l'historique restent conservés.
`raw_payload` n'est pas stocké dans le MVP : cela réduit la rétention de champs
inutiles ou sensibles. Les fixtures HTTP restent dans les tests lorsqu'elles
sont utiles.

### `price_observations`

Une observation associe nom de marché, plateforme, prix/devise originaux,
conversion EUR facultative, nature et horodatage. Les types persistables sont
`LISTING`, `SALE`, `BUY_ORDER`, `TRADE_VALUE` et `AGGREGATE`. Un fingerprint
évite de réinsérer la même observation collectée. Un agrégat ne devient pas
une vente ni un listing individuel. Les observations `LISTING` de même prix,
plateforme et objet sont aussi dédupliquées sur une fenêtre configurable afin
d'éviter une croissance inutile pendant le monitoring continu.

Cette table générique reste lisible pour l'historique MVP. Les nouvelles
données fortes ne lui sont pas assimilées :

- `aggregate_market_stats` conserve séparément min/max/moyenne/médiane/volume
  pour 24 h, 7 j, 30 j et 90 j, avec conversion FX traçable ;
- `realized_sales` conserve uniquement une vente réelle issue d'un événement
  ou d'un endpoint de ventes. Une empreinte permet les sources sans ID de vente ;
- `buy_order_observations` conserve prix, quantité et filtres de la demande.

### `fx_rates` et `platform_fee_schedules`

`fx_rates` historise paire, taux, source, date et nature `REFERENCE` ou
`EFFECTIVE`. `platform_fee_schedules` conserve chaque type de frais, fraction,
montants fixe/minimum, plage d'application, source et période de validité.
Aucun barème n'est prérempli sans source officielle ou réponse API.

### `trade_quotes` et `watch_rules`

`trade_quotes` prépare la séparation entre crédits affichés par une plateforme
et valeur cash réaliste des objets donnés/reçus, avec frais, spread, expiration
et confiance. `watch_rules` stocke de manière persistante un nom, un mode et des
filtres validables ; aucune transaction automatique n'est associée à ces tables.

### `market_sync_states`

Dernier essai, dernier succès, dernier échec, durée, compteurs reçus/créés/mis
à jour, code/message d'erreur, nombre d'échecs consécutifs et prochaine
exécution par plateforme et mode. Une erreur met à jour l'essai et le message,
mais ne modifie pas la date du dernier succès ni les données déjà conservées.
`last_error` et `last_error_at` restent donc consultables après une reprise
réussie : l'état courant et l'historique du dernier incident sont exposés
séparément par l'endpoint système et le Market Monitor.

### `market_opportunities`

Instantané persistant des opportunités calculables : listing, plateforme,
nom de marché, statut actif/inactif, score, valeur estimée, profit potentiel,
ROI, raison, date de détection et dernière vue. Les opportunités sont
recalculées après une synchronisation réussie. En live, elles restent absentes
tant que les ventes/frais nécessaires au calcul ne sont pas disponibles.

### `listing_analysis_snapshots`

Snapshot technique d'une analyse par annonce et par mode. Il conserve les
valeurs calculées nécessaires au scanner : référence, profit, ROI, scores
d'opportunité/float/liquidité/confiance/risque, spread, méthode, sources et
facteurs explicatifs. Il est recalculé après une synchronisation réussie.

Cette table ne constitue pas une transaction ni une nouvelle source de prix.
Elle évite de recalculer et transférer toute la base lors de chaque tri du
scanner. Les lignes sans snapshot restent affichables avec des métriques
inconnues et un avertissement explicite.

### `pattern_rules`

Structure préparatoire : skin, seed, catégorie, tier, premium estimé,
confiance, source et date de vérification. La table est vide par défaut.
Aucune règle de rareté n'est fournie sans source.

## DTO des adaptateurs

`AdapterItem`, `AdapterListing`, `AdapterSticker`, `AdapterAggregateStat`,
`AdapterRealizedSale`, `AdapterBuyOrder` et `AdapterFeeSchedule`
isolent le reste du produit du JSON propre à chaque plateforme. Les champs
sont validés avant persistance : décimaux positifs, float entre 0 et 1,
devise ISO sur trois lettres et timestamps avec fuseau.

`AdapterResult` contient séparément annonces individuelles, observations MVP,
agrégats, ventes, ordres d'achat, frais et avertissements. `MarketAdapter` expose recherche,
lecture d'une annonce quand l'API le permet, statistiques et fermeture du
client réseau.

La comparaison calcule minimum, moyenne et médiane par plateforme et nature
d'observation. Lorsqu'au moins deux plateformes ont le même type de donnée,
elle expose aussi l'écart médian absolu et relatif face à la meilleure médiane.

## Valeur, float et opportunité

Le Price Engine V2 choisit la classe de preuve la plus forte disponible :
au moins trois ventes réalisées récentes, puis les médianes historiques
agrégées, les ordres d'achat actuels et enfin les asks actuels. Ces replis sont
explicitement nommés dans `reference_method`; un ask ne devient jamais une
vente. `ReferencePrice` expose montant EUR, confiance, méthode, sources,
taille d'échantillon et date de calcul.

La confiance (0-100) combine niveau de preuve, nombre de sources, profondeur,
volume, fraîcheur, accord entre marchés et spread. Les coefficients sont
centralisés dans `PriceEngineConfig`. Le spread utilise le plus bas ask et le
plus haut bid récents et conserve une valeur négative lorsqu'un bid dépasse
l'ask au lieu de masquer ce signal.

La liquidité utilise les volumes 24 h/7 j/30 j, le nombre de listings, la
quantité demandée, le spread et la fraîcheur. Elle expose score, catégorie
(`VERY_LOW` à `VERY_HIGH`) et complétude des preuves. Une donnée absente n'est
pas assimilée à zéro. Le risque (0-100, valeur élevée défavorable) tient compte
de la liquidité, de la fraîcheur, du spread, du nombre de sources, de
l'exposition FX, du trade lock, de la confiance et des caractéristiques peu
comparables.

Le score float est un percentile inversé parmi au moins cinq exemplaires du
même `market_hash_name`, avec mi-rang pour les ex aequo. Il ne crée aucune
prime universelle.

Le score d'opportunité reste calculé uniquement pour la démo, où les ventes
et 10 % de frais de vente sont explicitement synthétiques. Pondération
centralisée : écart 30 %, liquidité 20 %, historique 20 %, float 15 %,
confiance marché 10 %, sécurité inverse du risque 5 %. Les pondérations vivent dans un objet
immuable remplaçable et le calcul possède un test dédié. En live, profit, ROI
et score restent inconnus tant que les frais effectifs et la route de revente
ne le sont pas.

Le scanner interroge ces snapshots par pages de 10 à 100 lignes. Les index
portent sur les clés d'analyse, `mode/status/date/prix`, le float et le paint
seed. Le dashboard est plafonné aux 100 annonces récentes ; il ne renvoie pas
la table complète au navigateur.

## Concepts futurs non persistés

- `Purchase` conservera prix/devise originaux, prix EUR effectif, frais et note.
- `Sale` comptable se distinguera d'une `RealizedSale` observée sur un marché.
- `PortfolioSnapshot` conservera la valorisation datée des avoirs.

Ces concepts seront ajoutés lorsqu'ils auront un usage réel. Aucun graphe de
route ni modèle d'achat automatisé n'existe dans la base actuelle.
