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

## Spread

Le spread compare le plus bas ask récent au plus haut bid récent :

```text
spread absolu = ask - bid
spread % = (ask - bid) / ask * 100
```

Un spread négatif est conservé : il peut signaler une incohérence temporelle
ou une possibilité à analyser, mais ne déclenche aucune transaction.

## Liquidité et risque

Le score de liquidité combine volumes 24 h/7 j/30 j, listings, quantité des
ordres d'achat, spread et fraîcheur. Les facteurs disponibles sont normalisés,
puis le résultat est réduit selon la complétude des preuves. Le moteur renvoie
également `VERY_LOW`, `LOW`, `MEDIUM`, `HIGH` ou `VERY_HIGH`.

Le risque est un score séparé où 100 signifie défavorable. Ses facteurs sont
la faible liquidité, les données anciennes, le spread, la dépendance à une
source, l'exposition FX, le trade lock, la faible confiance et les attributs
atypiques. Dans l'ancien score d'opportunité DEMO, seule la sécurité
`100 - RiskScore` contribue positivement.

## Limites

- Les ventes historiques Skinport agrégées restent des agrégats.
- Un listing ou un bid de repli n'est pas un prix réalisable garanti.
- Aucun premium monétaire de float, pattern ou sticker n'est appliqué sans
  comparables et source.
- Les profits LIVE restent inconnus tant que frais, change effectif et route de
  revente ne sont pas établis.
