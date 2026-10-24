# ObservatoryServer

Serveur de pilotage d'un observatoire à toit roulant, exposé à terme en
**ASCOM Alpaca** pour être commandé par **N.I.N.A.**

## Matériel

| Élément | Détail |
|---|---|
| Toit roulant | Moteur 12 V réducté (40 tr/min), driver **BTS7960**, Arduino |
| Fins de course | Contacts **NF** câblés vers GND (`INPUT_PULLUP` ⇒ HIGH = butée) |
| Monture | ASCOM / **EQMOD**, pilotée par NINA |
| Client | NINA 3.3.x — device *Dome* + device *SafetyMonitor* |
| Météo | Open-Meteo (prévision horaire), **pas de station physique** |

## État d'avancement

- **Phase 1 — terminée** : le serveur démarre et se pilote **sans matériel**
  (mode simulation), configuration validée, interlock monture actif.
- **Phase 2 — terminée** : couche **ASCOM Alpaca** — device *Dome*,
  device *SafetyMonitor*, management et découverte UDP 32227. NINA peut
  désormais découvrir et connecter les deux devices.

## Installation

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Lancement

```powershell
.\.venv\Scripts\python.exe -m backend.run_api
```

Le serveur écoute sur `http://localhost:11111` (réglage `server_port`).
C'est aussi le port Alpaca : management, Dome et SafetyMonitor sont exposés
sur ce même port.

## Connexion depuis NINA

Deux possibilités :

1. **Découverte automatique** — NINA diffuse `alpacadiscovery1` sur UDP
   `32227`, le serveur répond `{"AlpacaPort": 11111}`. Le device apparaît
   dans la liste Alpaca.
2. **Saisie manuelle** — adresse `127.0.0.1` (ou l'IP du PC), port `11111`.

Devices exposés :

| Type Alpaca | DeviceNumber | Rôle |
|---|---|---|
| `Dome` | 0 | Toit roulant (ouverture / fermeture) |
| `SafetyMonitor` | 0 | Sécurité météo (`IsSafe`) |

Correspondances du Dome : `OPENED`→0, `CLOSED`→1, `OPENING`→2, `CLOSING`→3,
`STOPPED`/`ERROR`/`UNKNOWN`→4. `AtPark` et `AtHome` signifient « toit fermé ».
Le toit n'a pas de rotation : `Azimuth`/`Altitude` valent 0 et les méthodes
de rotation renvoient `1024` (NotImplemented).

Un refus d'interlock remonte à NINA en **erreur Alpaca 1035**
(InvalidOperation) avec le message explicite. `SetPark`, `FindHome`,
`SlewToAzimuth` et `SyncToAzimuth` renvoient `1024`.

## Mode simulation

`data/config/settings.json` :

```json
"simulation": true
```

- Aucun port série n'est ouvert, aucun appel COM n'est fait.
- Le toit et la monture sont virtuels : idéal pour développer et tester.
- Sur la machine de l'observatoire, passer à `false` **en connaissance de cause**.

Le démarrage sans Arduino est sûr même en mode réel : si `COM4` est absent, le
serveur démarre quand même avec un toit `UNKNOWN` et refuse toute commande.

## Règles de sécurité

1. **Aucun mouvement du toit sans monture parquée** (`AtPark = true`).
2. Si l'état de parkage est **indéterminable** (monture hors tension, driver
   injoignable), le mouvement est **refusé** : une collision coûte plus cher
   qu'une nuit perdue.
3. Le refus lève une **alarme** visible dans `/api/health` et `/api/dome/status`.
4. `close_anyway: false` : le toit ne ferme pas à l'aveugle. Override manuel
   assumé et tracé uniquement.

## API actuelle

### API REST de l'observatoire

| Méthode | Route | Rôle |
|---|---|---|
| GET | `/` | Version + mode simulation |
| GET | `/api/health` | Santé agrégée (toit, monture, météo) |
| GET | `/api/dome/status` | État, position, alarme, liens |
| POST | `/api/dome/open` | Ouvrir (409 si refusé) |
| POST | `/api/dome/close` | Fermer (409 si refusé) |
| POST | `/api/dome/stop` | Arrêter |
| GET | `/api/safety/status` | État du Safety Monitor |
| GET | `/api/safety/device_state` | Détails météo |
| GET | `/api/config` | Réglages courants |
| POST | `/api/config/{clé}/{valeur}` | Modifier un réglage (validé, 400/404) |

### Alpaca

| Route | Rôle |
|---|---|
| `/management/v1/apiversions` | Versions d'API supportées (`[3]`) |
| `/management/v1/description` | Identité du serveur |
| `/management/v1/configureddevices` | Liste des devices + UniqueID |
| `/api/v1/dome/0/...` | Device Dome (InterfaceVersion 3) |
| `/api/v1/safetymonitor/0/...` | Device SafetyMonitor (InterfaceVersion 1) |

Toutes les réponses respectent l'enveloppe Alpaca
(`Value`, `ClientTransactionID`, `ServerTransactionID`, `ErrorNumber`,
`ErrorMessage`).

## Outils manuels

```powershell
# Sur la machine de l'observatoire : demande une confirmation en mode réel
.\.venv\Scripts\python.exe -m backend.dome.manual_control status
.\.venv\Scripts\python.exe -m backend.dome.manual_control open

# Vérifier la chaîne météo / sécurité
.\.venv\Scripts\python.exe -m backend.safety.manual_check
```

## Structure

```
backend/
  app.py                 API FastAPI, aucun accès matériel à l'import
  container.py           construction des services au démarrage
  common/                config validée, état atomique, chemins, santé
  common/alpaca/         management, Dome, SafetyMonitor, découverte UDP
  dome/                  lien série (réel/simulé), service, état, surveillance
  mount/                 lien ASCOM (réel/simulé), interlock de parkage
  safety/                météo Open-Meteo, évaluateur, Safety Monitor
firmware/RoofController.ino   firmware Arduino du toit
```
