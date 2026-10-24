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
| 2b | terminée | conformité Alpaca validée sous NINA 3.3 (0 erreur 404 au polling) |
| 3 | terminée | firmware robuste : `OK:`/`EVT:`, anti-rebond, rampes, parseur non bloquant |
| 4 | terminée | thread COM dédié, grâce de parkage 180 s, agent de sauvegarde |
| 5 | terminée | météo fail-safe : jamais SAFE sur panne, rafales, pire cas de la fenêtre |
| 6 | à faire | journalisation (fin du O(n²) de `write_log`) |
| 7 | à faire | schéma de configuration + chemins compatibles installation |
| 8 | à faire | interface web locale |
| 9 | à faire | tray app, PyInstaller, installateur Inno Setup, démarrage auto |
| 10 | à faire | atelier Arduino via `arduino-cli` |
| 11 | à faire | recette et documentation utilisateur |

## Commits

```
7c930bb Phase 4 : threads dedies serie et COM, grace de parkage, agent de sauvegarde
e23f9c6 Reglages reels mesures sur le toit et securite firmware a 50 s
8f4d42e Phase 3 : firmware robuste et protocole serie strict
201d2ad Conformite Alpaca : proprietes manquantes et management sans version
9a41afe Compatibilite Python 3.15 et document de reprise
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
- **Le firmware est l'autorité sur la sécurité du toit.** Les fins de course,
  le temps de trajet maximal et la détection de non-mouvement sont traités
  par l'Arduino ; le serveur ne fait que demander et lire.
- **Changement de sens refusé** par le firmware (`ER:BUSY`) : il faut un
  `STOP` explicite. Le serveur n'improvise pas d'arrêt à la place de
  l'opérateur.
- **`STOP` acquitte un défaut.** C'est le geste de reprise après un
  `TIMEOUT`, `NO_MOTION` ou `LIMITS`. Aucune autre commande n'efface un
  défaut.
- Interface finale : **UI web locale** servie par FastAPI, pas de Qt.
- Packaging prévu : **PyInstaller `onedir` + Inno Setup**, en **tray app**
  (jamais un service Windows : l'accès COM/ASCOM exige la session utilisateur).
- Données d'installation : `%ProgramData%\ObservatoryServer\`.

## Sécurité — à ne pas casser

1. `DomeService.open/close` appellent `_interlock()` avant tout mouvement.
2. Un refus lève une alarme persistante (`MOUNT_NOT_PARKED`,
   `MOUNT_UNKNOWN`, `ROOF_LINK`, `ROOF_FAULT`) exposée par `/api/health`.
   Seul un `BUSY` du firmware n'alarme pas : le toit est en bon état.
3. En Alpaca, un refus devient `ErrorNumber 1035` (InvalidOperation) avec le
   message métier, jamais un succès silencieux.
4. Le SafetyMonitor est fail-safe : erreur de lecture ⇒ `IsSafe = false`.
5. `stop()` fige la position au lieu de la laisser dériver.
6. Le firmware coupe le moteur sur fin de course **sans rampe** et refuse
   tout mouvement tant qu'un défaut n'est pas acquitté.

## Configuration actuelle (`data/config/settings.json`)

- `simulation: true`, `server_port: 11111`
- `serial_port: COM4`, `baudrate: 115200`
- `full_travel_time: 48`, `max_travel_time: 50` (= `ROOF_MAX_TRAVEL_MS`)
- trajet mesuré : 47,64 s ouverture, 47,11 s fermeture (marge 2,4 s)
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
    controller.py        thread unique propriétaire du port série + cache
    service.py           commandes + interlock + alarme
    state.py             état du toit, position estimée
    monitor.py           recopie du cache dans l'état persistant
    manual_control.py    outil manuel (confirmation en réel)
  mount/
    link.py              MountLink : Ascom (EQMOD) / Simulated
    monitor.py           thread COM dédié + cache de AtPark
  safety/
    monitor.py           boucle météo fail-safe
    agent.py             agent de sauvegarde (ferme sur UNSAFE)
    weather_provider.py  Open-Meteo, pire cas de la fenêtre
    evaluator.py         seuils
    service.py           façade SafetyService
firmware/
  RoofController.ino     firmware du toit (protocole OK:/ER:/EVT:)
  roof_config.h          brochage, temporisations, vitesses
  README.md              câblage, protocole, essai au banc, réglages
tests/
  test_roof_protocol.py  34 tests sans matériel (protocole, simulation, service)
```

## Tests effectués

- 27 contrôles Phase 1 : démarrage, états, position figée après STOP, config
  invalide (400/404), interlock.
- 45 contrôles Phase 2 : management, métadonnées, enveloppes, transactions,
  tous les `shutterstatus`, erreurs 1024/1035, `connected=false`, SafetyMonitor,
  découverte UDP 32227.
- 8 contrôles d'interlock via Alpaca : refus 1035, alarme, toit immobile.
- 15 contrôles sur la machine de production (Python 3.15) après transfert.
- **NINA 3.3 réelle** : 309 requêtes, 0 erreur 404 après ajout des propriétés
  manquantes (`canpark`, `canfindhome`, `cansetpark`, `cansetazimuth`,
  `devicestate`).
- 19 contrôles Phase 3 via Alpaca : ouverture, refus d'inversion (1035 avec
  message métier), arrêt figé, fermeture, `atpark`, absence d'alarme.
- `pytest` : **62 tests** (protocole série, machine à états simulée, threads
  dédiés, agent de sauvegarde, météo fail-safe). Lancer avec
  `.\\.venv\\Scripts\\python.exe -m pytest`.
- Phase 4 vérifiée en conditions réelles de serveur :
  - 20 lectures `shutterstatus` consécutives : médiane **3,4 ms**, max 6,1 ms
    (aucun accès série dans la requête) ;
  - `abortslew` : 200 en **20 ms** ;
  - météo UNSAFE réelle (pluie 100 %) : l'agent a fermé le toit de lui-même
    13 s après un `STOP` manuel (`Agent de sauvegarde : closed`).
- Phase 5 vérifiée contre l'API réelle : rafales **54 km/h** relevées (champ
  ignoré auparavant), fenêtre d'une heure, verdict `UNSAFE` cohérent
  (pluie 100 %, 1,1 mm, nuages 100 %).
- Firmware réellement **compilé** avec `arduino-cli` (noyau `arduino:avr`
  1.8.8, cible Uno) : 4 484 octets de flash, 345 octets de RAM, aucune erreur.
- **Firmware réellement téléversé et exécuté** sur l'Arduino Nano (COM4),
  cible `arduino:avr:nano` :
  - `EVT:BOOT:CLOSED` au démarrage, puis `OK:CLOSED` sur `STATUS` ;
  - ouverture réelle mesurée **47,64 s**, `EVT:OPENED` ;
  - fermeture réelle mesurée **47,11 s**, `EVT:CLOSED` ;
  - aucun `NO_MOTION`, aucun `TIMEOUT`, aucune alarme.
  Les deux fins de course NF sont donc câblées et détectées.

Scripts : `%TEMP%\opencode\smoke_phase1.py`, `smoke_phase2.py`,
`smoke_phase2_interlock.py`, `smoke_conformite.py`, `smoke_phase3.py`.

## Pièges connus (non corrigés)

- `write_log` réécrit tout le fichier à chaque ligne : O(n²). Phase 6.
- Le firmware n'a pas d'encodeur : un toit déplacé à la main hors tension
  n'est pas détecté (la position serveur reste l'ancienne).
- Une butée collée n'est détectée qu'en tentant de quitter la position
  (`NO_MOTION`), pas au repos.
- `analogWrite` sur D5/D6 est à ~980 Hz : léger sifflement du moteur.
- Un état `STOPPED` n'est pas durable : il est levé par une butée ou une
  commande. Ne pas s'appuyer dessus pour une décision de sécurité.
- L'agent de sauvegarde ferme aussi un toit que l'opérateur vient d'arrêter
  si la météo est UNSAFE. C'est le comportement voulu, mais il faut le savoir
  avant un essai manuel : pour travailler toit ouvert, il faut une météo sûre
  ou arrêter le serveur.

## Prochaines étapes immédiates

1. **Phase 6** : journaux (`write_log` en O(n²), un fichier réécrit à chaque
   ligne).
2. Essai réel du toit depuis NINA : il demande `simulation_dome` /
   `simulation_mount` séparés et un moyen de neutraliser l'agent de
   sauvegarde pendant l'essai.
3. Essai au banc du firmware sur l'Arduino, avec la procédure de
   `firmware/README.md` (les deux sens ont déjà été validés).

## Mise en service réelle — checklist

- [x] flasher le firmware et dérouler l'essai au banc (`firmware/README.md`)
- [x] mesurer le temps de trajet réel, ajuster `full_travel_time` (48 s)
- [ ] `simulation: false`
- [ ] `serial_port` = vrai port Arduino
- [ ] `telescope_driver` = `EQMOD.Telescope`
- [ ] port COM libre (IDE Arduino fermé)
- [ ] pare-feu : restreindre le port 11111
- [ ] NINA : monter le Dome et le SafetyMonitor via Alpaca
- [ ] tester d'abord `closeshutter`, puis `openshutter`, monture parquée
- [ ] vérifier l'arrêt d'urgence physique
