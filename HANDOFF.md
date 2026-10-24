# HANDOFF — état du projet ObservatoryServer

Document de reprise. Il permet à un nouvel agent (ou à vous dans six mois) de
comprendre le projet sans relire tout l'historique.

> **Note de transfert** : la transcription importée peut mentionner d'anciens
> chemins (`C:\Users\ludo\Downloads\...`). Le projet vit désormais dans le
> dossier `ObservatoryServer` de ce paquet. Se fier à ce document et au dépôt
> git, pas aux chemins absolus de la conversation.

## Objectif

Serveur de pilotage d'un observatoire à **toit roulant**, commandé par
**N.I.N.A.** via **ASCOM Alpaca**. À terme : application Windows complète
(`.exe` + installateur) avec interface de configuration et atelier Arduino
(génération et téléversement du firmware).

## Matériel

| Élément | Détail |
|---|---|
| Toit | Moteur 12 V réducté 40 tr/min, driver BTS7960, Arduino |
| Fins de course | Contacts **NF** vers GND, `INPUT_PULLUP` ⇒ HIGH = butée |
| Monture | ASCOM / EQMOD, pilotée par NINA |
| Client | NINA 3.3.x, devices Dome + SafetyMonitor |
| Météo | Open-Meteo (prévision), pas de station physique |

## État d'avancement

| Phase | État | Contenu |
|---|---|---|
| 0 | terminée | sauvegarde, dépôt git |
| 1 | terminée | démarrage sans matériel, config validée, interlock monture |
| 2 | terminée | couche Alpaca : management, Dome, SafetyMonitor, découverte UDP |
| 3 | à faire | firmware robuste (`OK:`/`EVT:`, anti-rebond, rampe, parseur non bloquant, `MAX_TRAVEL_TIME` 55 s) |
| 4 | à faire | thread COM dédié, grâce de parkage 180 s, agent de sauvegarde |
| 5 | à faire | météo fail-safe (données périmées ⇒ UNSAFE) |
| 6 | à faire | journalisation (fin du O(n²) de `write_log`) |
| 7 | à faire | schéma de configuration + chemins compatibles installation |
| 8 | à faire | interface web locale |
| 9 | à faire | tray app, PyInstaller, installateur Inno Setup, démarrage auto |
| 10 | à faire | atelier Arduino via `arduino-cli` |
| 11 | à faire | recette et documentation utilisateur |

## Commits

```
ddfc9d5 Phase 2 : couche ASCOM Alpaca (Dome + SafetyMonitor + decouverte)
3644058 Phase 1 : demarrage sans materiel, config validee, interlock monture
c291117 Sauvegarde initiale avant refonte v3 (etat d'origine)
```

## Décisions structurantes

- **NINA est maître** ; le serveur est un agent de sauvegarde. Le module dôme
  joint EQMOD directement, même si NINA est arrêté.
- **Un seul port Alpaca** : `11111` (HTTP + management + devices).
- **Aucun mouvement du toit sans monture parquée.** État de parkage
  indéterminable ⇒ refus.
- **`close_anyway = false`** : le toit ne ferme pas à l'aveugle. Décision
  explicite : une casse coûte plus cher que la pluie.
- **Simulation par défaut** (`simulation: true`) : aucun accès COM/série à
  l'import, le serveur démarre toujours.
- **Un seul drapeau `simulation`** pilote aujourd'hui toit et monture. La
  séparation `simulation_dome` / `simulation_mount` est prévue.
- Interface finale : **UI web locale** servie par FastAPI, pas de Qt.
- Packaging prévu : **PyInstaller `onedir` + Inno Setup**, en **tray app**
  (jamais un service Windows : l'accès COM/ASCOM exige la session utilisateur).
- Données d'installation : `%ProgramData%\ObservatoryServer\`.

## Sécurité — à ne pas casser

1. `DomeService.open/close` appellent `_interlock()` avant tout mouvement.
2. Un refus lève une alarme persistante (`MOUNT_NOT_PARKED`,
   `MOUNT_UNKNOWN`, `ROOF_LINK`) exposée par `/api/health`.
3. En Alpaca, un refus devient `ErrorNumber 1035` (InvalidOperation) avec le
   message métier, jamais un succès silencieux.
4. Le SafetyMonitor est fail-safe : erreur de lecture ⇒ `IsSafe = false`.
5. `stop()` fige la position au lieu de la laisser dériver.

## Configuration actuelle (`data/config/settings.json`)

- `simulation: true`, `server_port: 11111`
- `serial_port: COM4`, `baudrate: 115200`
- `full_travel_time: 45`, `max_travel_time: 55`
- `telescope_driver: EQMOD_SIM.Telescope` ← **à passer à `EQMOD.Telescope` en réel**
- `mount_check_mode: strict`, `close_anyway: false`
- seuils météo : vent 60, rafales 70, pluie 30 % / 0,1 mm, nuages 80 %, T° 0,5 °C

## Lancement

```powershell
.\.venv\Scripts\python.exe -m backend.run_api
```

- http://localhost:11111/api/health
- http://localhost:11111/docs
- http://localhost:11111/management/v1/configureddevices

## Architecture

```
backend/
  app.py                 FastAPI, lifespan, aucune initialisation matérielle à l'import
  run_api.py             point d'entrée uvicorn
  container.py           construit et démarre les services
  common/
    settings_manager.py  source unique de config, types validés, écriture atomique
    state.py             état persistant atomique
    alpaca/              errors, protocol, management, dome, safetymonitor, discovery, server
    health.py            vue de santé agrégée
  dome/
    serial_link.py       RoofLink : Serial / Simulated / Unavailable
    service.py           commandes + interlock + alarme
    state.py             état du toit, position estimée
    monitor.py           boucle STATUS
    manual_control.py    outil manuel (confirmation en réel)
  mount/
    link.py              MountLink : Ascom (EQMOD) / Simulated
  safety/
    monitor.py           boucle météo
    evaluator.py         seuils
    service.py           façade SafetyService
firmware/RoofController.ino
```

## Tests effectués

- 27 contrôles Phase 1 : démarrage, états, position figée après STOP, config
  invalide (400/404), interlock.
- 45 contrôles Phase 2 : management, métadonnées, enveloppes, transactions,
  tous les `shutterstatus`, erreurs 1024/1035, `connected=false`, SafetyMonitor,
  découverte UDP 32227.
- 8 contrôles d'interlock via Alpaca : refus 1035, alarme, toit immobile.

Scripts : `%TEMP%\opencode\smoke_phase1.py`, `smoke_phase2.py`,
`smoke_phase2_interlock.py` (sur la machine de développement).

## Pièges connus (non corrigés)

- `write_log` réécrit tout le fichier à chaque ligne : O(n²). Phase 6.
- La météo peut rester **SAFE sur un cache périmé** (30 min). Phase 5.
- `datetime.now()` au lieu d'un fuseau explicite (Europe/Paris).
- Prévision : `next_index` au lieu d'un max sur la fenêtre, et
  `wind_gusts_10m` non exploité. Phase 5.
- Appels COM encore dans le thread de la requête. Phase 4.
- Grâce de parkage de 180 s non implémentée : refus immédiat aujourd'hui.

## Prochaines étapes immédiates

1. **Phase 3** : firmware (protocole `OK:`/`EVT:`, anti-rebond, rampe,
   parseur non bloquant, `MAX_TRAVEL_TIME = 55`).
2. **Phase 4** : thread COM dédié + grâce de parkage + agent de sauvegarde.
3. Puis 5 et 6 avant toute mise en service définitive.

## Mise en service réelle — checklist

- [ ] `simulation: false`
- [ ] `serial_port` = vrai port Arduino
- [ ] `telescope_driver` = `EQMOD.Telescope`
- [ ] port COM libre (IDE Arduino fermé)
- [ ] pare-feu : restreindre le port 11111
- [ ] NINA : monter le Dome et le SafetyMonitor via Alpaca
- [ ] tester d'abord `closeshutter`, puis `openshutter`, monture parquée
- [ ] vérifier l'arrêt d'urgence physique
