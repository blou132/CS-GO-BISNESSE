# Currency, Fee and Profit Engine

La devise comptable est l'EUR. Chaque donnée de marché conserve néanmoins son
montant et sa devise d'origine, ainsi que le taux, la source et la date utilisés
pour la conversion de référence.

## Change

Le collecteur BCE couvre EUR, USD, GBP, JPY, CHF et CNY. La série officielle
exprime les unités de devise pour 1 EUR ; la conversion d'un prix vers EUR
emploie son inverse. Les taux sont persistés comme `REFERENCE` et ne sont jamais
présentés comme le taux réellement payé. Un taux `EFFECTIVE` devra provenir
d'une transaction ou d'un relevé réel et reste séparé.

## Frais

`FeeRule` et `PlatformFeeSchedule` acceptent les types `BUY`, `SELL`, `DEPOSIT`,
`WITHDRAW`, `TRADE`, `PAYMENT` et `FX`. Une règle peut contenir taux, montant
fixe, minimum, devise, tranche de prix, item ciblé et période de validité.

Le moteur sélectionne d'abord une règle spécifique à l'item, puis une règle
générale applicable. Il refuse les devises, tranches ou dates incompatibles et
retourne `null` lorsqu'aucun barème sourcé ne correspond. Il n'applique donc
aucun pourcentage universel à Skinport, CSFloat ou une autre plateforme.
DMarket peut alimenter ses frais de vente par l'endpoint officiel
`customized-fees` lorsque les clés sont configurées.

## Profit net

`PurchaseCostBreakdown` additionne :

- prix de l'item ;
- frais d'achat ;
- paiement ;
- change ;
- dépôt ;
- trade.

`SaleRevenueBreakdown` retranche du prix de vente réalisable estimé :

- frais de vente ;
- retrait ;
- change ;
- trade.

Le résultat fournit profit net et ROI sur le coût total. `ROI/day` n'est
calculé que si une durée de détention explicite est fournie. L'API de simulation
ne remplit aucun frais manquant et ne garantit pas le prix de vente.
