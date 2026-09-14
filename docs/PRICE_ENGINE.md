# Price Engine V2

Le moteur ne mélange pas toutes les observations dans une moyenne. Il produit
une `ReferencePrice` à partir du premier niveau de preuve exploitable :

1. médiane d'au moins trois ventes réalisées des 30 derniers jours ;
2. médiane des statistiques historiques récentes, avec une observation retenue
   par plateforme et préférence pour 7 j, 30 j, 24 h puis 90 j ;
3. médiane des meilleurs ordres d'achat récents par plateforme ;
4. médiane des plus bas listings récents par plateforme.

Les données doivent être en EUR, positives, horodatées et non futures. Une
preuve trop ancienne est exclue du niveau concerné. Les seuils vivent dans
`PriceEngineConfig` et peuvent évoluer sans disperser de constantes dans le
code.

## Confiance

`PriceConfidence` est borné entre 0 et 100. Il part d'une base dépendant du
niveau de preuve, puis prend en compte :

- le nombre de plateformes distinctes ;
- la profondeur de l'échantillon ;
- le volume documenté ;
- la fraîcheur ;
- le désaccord relatif entre les prix ;
- le spread bid/ask actuel.

La confiance ne transforme pas une estimation en garantie. L'API renvoie la
méthode, les sources et la taille d'échantillon avec la valeur.
La fraicheur de l'echantillon utilise son horodatage median : une seule vente
recente ne rajeunit pas un ensemble ancien.

## Spread

Le spread compare le plus bas ask récent au plus haut bid récent :

```text
spread absolu = ask - bid
spread % = (ask - bid) / ask * 100
```

Un spread négatif est conservé : il peut signaler une incohérence temporelle
ou une possibilité à analyser, mais ne déclenche aucune transaction.
Seul le dernier snapshot d'ordres de chaque plateforme est retenu, avant
selection du meilleur bid. Les quantites nulles et les bids conditionnels
(float, pattern, sticker, etc.) sont exclus de l'assemblage tant qu'aucun
matcher ne prouve leur applicabilite a l'exemplaire analyse.

## Liquidité et risque

Le score de liquidité combine volumes 24 h/7 j/30 j, listings, quantité des
ordres d'achat, spread et fraîcheur. Les facteurs disponibles sont normalisés,
puis le résultat est réduit selon la complétude des preuves. Le moteur renvoie
également `VERY_LOW`, `LOW`, `MEDIUM`, `HIGH` ou `VERY_HIGH`.
L'assemblage exclut les preuves observees depuis plus de 24 h. Une annonce
fraiche ne peut donc pas reutiliser un ancien volume de ventes comme actuel.
Le dernier agregat plateforme/nom/fenetre remplace le precedent, y compris
lorsque son volume est zero ou que sa mediane est absente.

Le risque est un score séparé où 100 signifie défavorable. Ses facteurs sont
la faible liquidité, les données anciennes, le spread, la dépendance à une
source, l'exposition FX, le trade lock, la faible confiance et les attributs
atypiques. Dans l'ancien score d'opportunité DEMO, seule la sécurité
`100 - RiskScore` contribue positivement.

## Comparables float

Le groupe est le couple `market_hash_name` exact et `exterior`. Seules les
annonces actives, observees depuis moins de 24 h et avec float valide entrent
dans l'echantillon. Un asset repete n'est compte qu'une fois, a sa derniere
observation ; sans asset connu, la cle de repli est plateforme/ID externe.
Le seuil existant de cinq comparables reste requis, sans prime monetaire.

## Limites

- Les ventes historiques Skinport agrégées restent des agrégats.
- Un listing ou un bid de repli n'est pas un prix réalisable garanti.
- Aucun premium monétaire de float, pattern ou sticker n'est appliqué sans
  comparables et source.
- Les profits LIVE restent inconnus tant que frais, change effectif et route de
  revente ne sont pas établis.
- Une reponse d'ordres completement vide ne possede pas encore de marqueur de
  snapshot en base : les anciennes observations peuvent subsister jusqu'au
  seuil de fraicheur. Un bid observe n'est donc jamais une offre executable
  garantie ; la revalidation reste obligatoire avant une future opportunite.
- Sans asset ID commun, les doublons inter-plateformes ne sont pas prouvables.
