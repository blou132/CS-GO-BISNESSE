# DMarket

- Statut : `OFFICIAL_API`
- Documentation officielle : <https://docs.dmarket.com/v1/swagger.html>
- Vérification documentaire : 13 septembre 2026
- Base : `https://api.dmarket.com`

## API et authentification

L'adaptateur appelle `GET /marketplace-api/v2/offers` pour le jeu CS2
(`gameId=a8db`), les targets agrégées par titre, `trade-aggregator/v1/last-sales`
et `exchange/v1/customized-fees`. Chaque requête est signée Ed25519 à partir de
`DMARKET_PUBLIC_KEY` et `DMARKET_SECRET_KEY`, puis transmet `X-Api-Key`,
`X-Sign-Date` et `X-Request-Sign`. Les paramètres de chemin sont signés décodés
et la query string exactement encodée comme transmise. Les clés sont validées
comme paire avant l'appel et ne sont jamais journalisées.

L'endpoint fournit offres en cents USD, identifiant, état de verrouillage,
nom, float, paint index/seed, phase, Fade, stickers, inspect link et durée de
trade lock. Les offres verrouillées sont ignorées ; un trade lock indiqué est
conservé comme avertissement. Aucun endpoint d'inventaire, dépôt, achat, vente
ou trade n'est utilisé. Les targets deviennent des `BuyOrderObservation`. Les
dernières ventes conservent prix USD, date, type et attributs ; comme l'API ne
fournit pas d'ID de vente, la déduplication utilise une empreinte des champs
documentés et ne fabrique pas d'identifiant externe. Les frais par défaut et
réduits conservent fraction, minimum, plage de prix et expiration. Aucun
endpoint POST transactionnel n'est autorisé.

## Quotas et limites

La première page contient au plus 50 offres, 20 ventes et 100 règles de frais.
La spécification consultée ne
donne pas de quota global chiffré pour cet endpoint ; le transport espace les
appels, respecte `Retry-After`, borne les retries et met en cache. L'API ne
documente pas de lecture d'une offre publique isolée en v2 : `get_listing`
signale donc explicitement une capacité indisponible.

L'algorithme de signature est vérifié cryptographiquement dans les tests, y
compris pour un titre encodé dans le chemin. Offres, targets, ventes et frais
sont testés sur réponses synthétiques. Aucune vraie paire de clés DMarket n'était disponible,
donc aucune validation live authentifiée n'est revendiquée.

## Collecte partielle et validation

Un echec sur targets, ventes ou frais ne jette plus les offres deja obtenues.
Chaque enrichissement conserve son code d'erreur ; l'etat persiste devient
`degraded`, visible dans le monitoring, puis revient `online` apres une
collecte complete. Un float egal a zero reste zero et non une donnee absente.

La verification explicite se lance depuis `apps/api`, dependances installees,
avec les deux variables de cle deja presentes dans l'environnement :

```bash
python -m app.markets.smoke --platform dmarket --query 'AK-47 | Redline (Field-Tested)' --live
```

Pas de lecture de `.env`, d'ecriture en base, de sortie de secrets ni de
transaction. Code 0 pour `online`, 2 sinon. Sans paire de cles,
`not_configured` est confirme ; l'appel authentifie reste `BLOCKED_EXTERNAL`.

## V0.11 : validation du 14-15 septembre 2026

Les deux variables restent absentes dans la configuration prevue. La matrice
401/403/429/500/502/503/timeout/JSON invalide est testee au niveau adaptateur,
en plus des tests de signature et de collecte partielle existants. Aucune
signature authentifiee reelle ni lecture live des offres, targets, ventes ou
frais n'est revendiquee. Ne pas qualifier les fees de valides en compte reel
sur la seule base des fixtures.
