# Skinport realtime : V0.11

## Decision

Implemente et teste localement, mais **pas valide sur le flux public**.
Le 14 septembre 2026, le handshake officiel depuis ce serveur renvoie HTTP 403.
Aucun proxy, cookie de navigateur, endpoint prive ou contournement n'a ete utilise.
Le registre conserve Skinport `PARTIAL` et ne revendique pas de collecte live
WebSocket effective. La production n'a pas ete modifiee.

Le [contrat officiel Skinport](https://docs.skinport.com/websocket/sale-feed)
documente Socket.IO/MessagePack, `saleFeedJoin` et les seuls evenements `listed`
et `sold`. `updated`, `price_changed` et `canceled` ne sont pas supportes.
L'exemple a une devise par ligne, un `saleId` nullable et un `url` slug.
L'unite de `salePrice` n'y est pas explicitement definie. Elle reste donc
`unverified`, meme si une lecture en centimes semble plausible.

## Configuration desactivee par defaut

| Variable | Defaut | Usage |
| --- | --- | --- |
| `SKINPORT_REALTIME_ENABLED` | `false` | Activation explicite du collecteur |
| `MARKET_SYNC_QUERY` | vide | Sous-chaine cible, minimum 3 caracteres pour activer |
| `SKINPORT_REALTIME_QUEUE_SIZE` | `256` | Limite entre 1 et 5000 evenements |
| `SKINPORT_REALTIME_PRICE_UNIT` | `unverified` | `minor` ou `major` uniquement apres verification |
| `SKINPORT_REALTIME_PRICE_UNIT_SOURCE` | vide | Source HTTPS de la verification manuelle |
| `SKINPORT_REALTIME_STALE_SECONDS` | `300` | Age maximal d'une annonce du flux |
| `FLOAT_MIN_SAMPLES` | `5` | Minimum configurable, jamais inferieur a 5 |

Ne pas activer maintenant. Une URL de source renseignee n'est pas une preuve
automatique : l'administrateur doit d'abord confirmer le contrat avec Skinport.
L'abonnement officiel porte sur CS2/EUR/en ; le filtre de nom est applique
localement, pas presente comme une fonctionnalite de filtrage du fournisseur.
Chaque nom exact conserve ses propres comparaisons, notamment StatTrak/Souvenir.

## Transport et ingestion

- `python-socketio` assure Socket.IO, MessagePack et ping/pong Engine.IO.
- Une session HTTP possedee est fermee, y compris apres un handshake refuse.
- Un seul consommateur asynchrone traite au plus 20 lignes par transaction,
  dans un thread avec sa propre session SQLAlchemy.
- File bornee, frame WebSocket limitee a 1 Mio, au plus 100 lignes normalisees
  par message. Les debordements sont comptes, pas stockes ailleurs.
- Reconnexion 5, 10, 20 secondes... plafond 300 secondes, jitter jusqu'a 20 %.
  Un refus 401/403/429 impose au moins 300 secondes. `Retry-After` est respecte.
- Arret : annulation du recepteur, fermeture du transport, vidage de la file,
  attente de l'ecriture en cours avant fermeture de la DB. Sur PostgreSQL,
  chaque statement est borne a 5 s et chaque attente de verrou a 3 s.
  Une transaction lente peut prolonger le vidage ; ce n'est pas une garantie
  de duree totale d'arret. Une erreur DB est retentee une fois puis comptee.
- Le scheduler REST reste independant. Un refus du flux ne marque pas un
  succes REST comme echec. Les metriques du flux sont en memoire par processus.

Cette version est prevue pour le processus API unique du Compose existant.
Elle n'est pas une architecture multi-workers de collecte : ne pas augmenter
les replicas/workers avec ce flag active sans coordination inter-processus.
La deduplication DB ne remplace pas cette coordination.

## Integrite des donnees

`realtime_receipts` stocke une empreinte mode/source/type/saleId/prix/devise,
pas le payload brut. Receipt, listing/vente, observation et recalcul sont
commis ensemble. Une relance apres rollback reste idempotente.

- `saleId` absent : evenement ignore, aucun faux ID derive de `productId`.
- `assetid` Steam et `assetId` interne ne sont pas confondus.
- `listed` alimente l'annonce et une observation ; `sold` alimente une vente
  identifiee et marque l'annonce existante `SOLD`.
- Un replay identique ne rafraichit pas l'annonce. Un prix different est
  reevalue. Une annonce deja vendue ne peut pas etre ressuscitee.
- Sans evenement de retrait officiel, une annonce expire en `INACTIVE`,
  jamais en `SOLD`. Scanner et watchlist excluent aussi les annonces live
  trop anciennes par SQL, meme si le collecteur a ete arrete.
- Les snapshots d'une vente/expiration sont invalides. Le recalcul apres
  batch porte seulement sur les noms touches.
- `sold_at` utilise la reception du feed faute de date transactionnelle
  documentee, avec `timestamp_basis=feed_observed_at` dans la provenance.
  Cela ne prouve pas la date economique exacte d'une vente rejouee.

Limites : pas de sequence officielle ni de replay durable confirme, donc pas
de reconstruction fiable des evenements manques. Une repetition du meme prix
pour un meme identifiant est ignoree, meme si elle etait un nouvel evenement.
Un `listed` n'est pas une revalidation instantanee avant achat. Les donnees
restent des references, jamais une instruction automatique d'achat.

Receipts et PriceObservation ont une retention de `HISTORY_RETENTION_DAYS`
(30 jours par defaut), nettoyee pendant l'ingestion. `MAX_LISTINGS=500`
limite les annonces actives. Les annonces inactives et ventes normalisees
restent conservees suivant le modele existant : surveiller la taille DB avant
un flux durable, aucun effacement destructif de cet historique n'est ajoute.

## Valorisation et interface

La hierarchie de preuves reste ventes identifiees recentes, puis medianes,
puis demande courante, puis annonces. Les lectures historiques sont bornees
par les fenetres du moteur : 30 jours pour les ventes, 72 h pour les agregats,
24 h pour la demande. Les anciennes offres et les bids conditionnels restent
ecartes. Le percentile float ne constitue pas un premium financier.

La fiche objet expose les preuves **effectivement retenues** (50 maximum
affichees et nombre total), IDs internes/externes, prix/devises originaux,
horodatages, FX source/date, volumes et nombre de comparables. Les frais
effectifs inconnus restent `UNKNOWN`, le FX de reference n'est pas du FX
effectif et aucun profit/ROI LIVE n'est fabrique. Les metriques REST/flux du
Market Monitor sont rafraichies toutes les 5 secondes sans recharger la page.

## Validation reproductible

Avec les dependances backend et `PYTHONPATH=apps/api`, depuis la racine :

```bash
python scripts/tests/skinport-realtime-smoke.py --live --seconds 30
python scripts/tests/public-live-smoke.py --live --query 'AK-47 | Redline (Field-Tested)'
```

Les scripts ne chargent pas de fichier de secrets et n'ecrivent pas en DB.
Le premier ouvre une seule connexion officielle, sans reconnexion, et ne
sort que des compteurs/statuts. Le second fait des lectures Skinport REST/BCE.
Un succes de ce dernier ne valide ni le flux ni une opportunite executable.

Tests locaux : `tests/test_realtime.py`, `scripts/tests/realtime-browser.mjs`
et `scripts/tests/realtime-postgres-check.py`. Le test PostgreSQL exige le
marqueur `CS2_ISOLATED_VALIDATION=cs2-v011-validation`, exclusivement sur la
base jetable. Les scenarios navigateur simules portent explicitement la
mention fixture ; aucune fixture n'est injectee dans la production.

La validation complete se relance avec
`python3 scripts/tests/validate-v011-stack.py --run`. Elle refuse de remplacer
une stack temporaire existante, utilise les ports localhost 3000/8000 libres,
genere ses propres identifiants, verifie aussi le modele Compose production
sans le demarrer, puis detruit seulement `cs2-v011-validation`. Les captures
sont conservees sous `artifacts/v011-<date-UTC>/` hors Git. Prerequis navigateur :
image Playwright 1.55.0 et volume de dependances `cs2-playwright-tools` 1.55.0.
