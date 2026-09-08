# Banque centrale européenne

- Statut : `PUBLIC_API`
- Portail : <https://data.ecb.europa.eu/>
- Documentation SDMX : <https://data.ecb.europa.eu/help/api/overview>
- Jeu de données : `EXR`
- Vérification : 8 septembre 2026

La BCE publie chaque jour ouvré des taux de référence de l'euro et expose les
séries via son service SDMX. Les premières devises ciblées sont EUR, USD, GBP,
JPY, CHF et CNY.

Ces taux sont informatifs. Ils représentent une référence et non le taux
réellement subi lors d'un paiement, dépôt ou retrait. Le modèle conserve donc
séparément `REFERENCE` et `EFFECTIVE`.
