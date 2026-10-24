Couche Alpaca

Responsabilités :

- `errors.py`       : codes d'erreur ASCOM Alpaca et exception `AlpacaError`
- `protocol.py`     : lecture des paramètres, enveloppe de réponse, transactions
- `management.py`   : `/management/v1/*` (versions, description, devices)
- `dome.py`         : device Dome n° 0 (InterfaceVersion 3)
- `safetymonitor.py`: device SafetyMonitor n° 0 (InterfaceVersion 1)
- `discovery.py`    : répondeur UDP 32227 (`alpacadiscovery1`)
- `server.py`       : routeur agrégé, inclus une seule fois par `app.py`

Règles :

- Toute commande du Dome passe par `DomeService` : l'interlock monture
  s'applique donc à l'identique depuis NINA et depuis l'API REST.
- Un refus métier devient une erreur Alpaca (`1035` InvalidOperation), jamais
  un succès silencieux.
- Le SafetyMonitor est fail-safe : une erreur de lecture renvoie `IsSafe =
  false`, jamais une erreur ni un faux « safe ».
- Aucun accès matériel à l'import : les services sont lus via le conteneur au
  moment de la requête.
