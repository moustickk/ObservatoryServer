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
- **Phase 2 — à venir** : couche Alpaca (Dome + SafetyMonitor, découverte UDP).
  Tant qu'elle n'est pas là, NINA ne voit pas encore les devices.

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
C'est aussi le port qui servira à Alpaca.

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
  dome/                  lien série (réel/simulé), service, état, surveillance
  mount/                 lien ASCOM (réel/simulé), interlock de parkage
  safety/                météo Open-Meteo, évaluateur, Safety Monitor
firmware/RoofController.ino   firmware Arduino du toit
```
