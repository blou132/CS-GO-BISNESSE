# Banque centrale européenne

- Statut : `PUBLIC_API`
- Portail : <https://data.ecb.europa.eu/>
- Documentation SDMX : <https://data.ecb.europa.eu/help/api/overview>
- Jeu de données : `EXR`
- Vérification : 8 septembre 2026

La BCE publie chaque jour ouvré des taux de référence de l'euro et expose les
séries via son service SDMX. Les premières devises ciblées sont EUR, USD, GBP,
JPY, CHF et CNY.

Le client utilise la requête quotidienne bornée
`EXR/D.USD+GBP+JPY+CHF+CNY.EUR.SP00.A` avec `lastNObservations=1`,
`detail=dataonly` et le format CSV officiel. La série exprime des unités de
devise pour 1 EUR. La base conserve cette orientation exacte ; le service de
conversion l'inverse seulement au moment de convertir un prix vers EUR.

La synchronisation est indépendante des marketplaces, déduplique chaque
devise/date et conserve donc l'historique quotidien. Elle reste désactivée par
défaut et s'active avec `FX_REFERENCE_SYNC_ENABLED=true`; son intervalle ne peut
pas être inférieur à une heure. Le dernier taux disponible est accepté pendant
120 heures afin de couvrir week-ends et jours fériés sans fabriquer de cours.

Ces taux sont informatifs. Ils représentent une référence et non le taux
réellement subi lors d'un paiement, dépôt ou retrait. Le modèle conserve donc
séparément `REFERENCE` et `EFFECTIVE`.
