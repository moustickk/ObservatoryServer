# Firmware du controleur de toit

Arduino Uno ou Nano (ATmega328P) pilotant un moteur 12 V réducté via un
driver **BTS7960**, avec deux fins de course à contact **normalement fermé**.

| Fichier | Rôle |
|---|---|
| `RoofController.ino` | le firmware |
| `roof_config.h` | brochage, temporisations, vitesses — régénérable par l'interface web (phase 10) |

## Câblage

| Arduino | Vers | Remarque |
|---|---|---|
| D2 | fin de course **ouverture** | contact NF entre D2 et GND |
| D3 | fin de course **fermeture** | contact NF entre D3 et GND |
| D5 | BTS7960 `RPWM` | sens + vitesse |
| D6 | BTS7960 `LPWM` | sens + vitesse |
| D7 | BTS7960 `R_EN` | validation demi-pont droit |
| D8 | BTS7960 `L_EN` | validation demi-pont gauche |
| GND | GND commun (Arduino, driver, alimentation) | **indispensable** |
| 5 V | BTS7960 `VCC` (logique) | ne pas confondre avec l'alimentation moteur |

Le moteur et sa batterie ne passent **pas** par l'Arduino : ils sont branchés
sur les bornes de puissance du BTS7960. Masse commune obligatoire, sinon les
entrées de commande flottent.

### Pourquoi des contacts NF

Avec `INPUT_PULLUP` et un contact normalement fermé :

```
toit ailleurs                 circuit fermé   -> LOW
toit en butée                 circuit ouvert  -> HIGH
fil coupé / cosse débranchée  circuit ouvert  -> HIGH
```

**HIGH signifie « en butée ».** Un fil coupé est donc vu comme une butée, ce
qui arrête le mouvement : c'est le sens de sécurité recherché.

Conséquence à connaître : un fil coupé sur le fin de course *fermeture* fait
croire au firmware que le toit est fermé alors qu'il est ouvert. Le défaut est
détecté au premier mouvement (voir `NO_MOTION`), pas avant. Pour une
installation définitive, placer les deux contacts NF **en série dans le
circuit de puissance** du moteur ajoute une sécurité indépendante du logiciel.

Câbler les fins de course en câble blindé ou torsadé, et ajouter un condensateur
de 100 nF entre chaque entrée et GND si les longueurs dépassent quelques mètres.

## Protocole série

115200 bauds, 8N1, une ligne ASCII par message terminée par `\n`.
La casse est indifférente.

### Commandes reçues

| Commande | Effet |
|---|---|
| `PING` | ne fait rien, renvoie l'état |
| `STATUS` | renvoie l'état |
| `OPEN` | démarre l'ouverture |
| `CLOSE` | démarre la fermeture |
| `STOP` | coupe le moteur, fige `STOPPED`, **efface un défaut** |

### Réponses

```
OK:<ETAT>          commande acceptée
ER:<CODE>:<ETAT>   commande refusée
EVT:<QUOI>:<ETAT>  événement asynchrone (jamais une réponse)
```

`<ETAT>` vaut `UNKNOWN`, `OPENING`, `OPENED`, `CLOSING`, `CLOSED`,
`STOPPED` ou `ERROR`. **Tout message se termine par l'état courant**, ce qui
permet au serveur de le lire sans connaître le détail du protocole.

Codes de refus : `BUSY`, `FAULT`, `UNKNOWN_CMD`, `LINE_TOO_LONG`.
Événements : `BOOT`, `OPENED`, `CLOSED`, `TIMEOUT`, `NO_MOTION`, `LIMITS`.

### Règles de comportement

- **Inversion de sens refusée.** `OPEN` pendant `CLOSING` renvoie
  `ER:BUSY:CLOSING`. Il faut `STOP` d'abord. C'est volontaire : une inversion
  brutale est dure pour le driver et la mécanique, et le serveur ne doit pas
  décider seul d'un arrêt.
- **Idempotence.** `OPEN` alors que le toit ouvre déjà renvoie `OK:OPENING`.
  `OPEN` alors qu'il est déjà ouvert renvoie `OK:OPENED`.
- **Défaut bloquant.** Après `TIMEOUT`, `NO_MOTION` ou `LIMITS`, tout
  mouvement est refusé (`ER:FAULT:ERROR`) jusqu'à un `STOP` explicite.
- **STOP est immédiat** en ce qui concerne la logique : l'état passe à
  `STOPPED` tout de suite, le moteur décélère en 200 ms puis est coupé.

## Sécurité dans le firmware

| Protection | Valeur par défaut | Comportement |
|---|---|---|
| Temps de trajet maximal | 60 s (`ROOF_MAX_TRAVEL_MS`) | coupe et passe en `ERROR` (`TIMEOUT`) |
| Non-mouvement | 4 s (`ROOF_NO_MOTION_MS`) | la butée de départ n'est pas relâchée ⇒ moteur bloqué, `ERROR` (`NO_MOTION`) |
| Anti-rebond | 30 ms (`ROOF_DEBOUNCE_MS`) | évite les arrêts parasites dus aux vibrations |
| Temps mort de sens | 400 ms (`ROOF_DIRECTION_DEAD_MS`) | moteur coupé avant tout nouveau départ |
| Butées incohérentes | — | les deux actives ⇒ `ERROR` (`LIMITS`), aucun mouvement |
| Rampe de démarrage | 900 ms, PWM 110 → 255 | évite un appel de courant brutal |
| Rampe d'arrêt | 200 ms sur `STOP` | sur fin de course ou défaut, coupure **immédiate** |

La boucle principale ne bloque jamais : pas de `delay()`, pas de `String`,
pas de `readStringUntil()`, tampon de ligne de taille fixe. Une rafale de
commandes ne peut donc pas retarder un arrêt sur fin de course.

Les fins de course sont lues à chaque itération et priment sur tout le reste.

## Compiler et téléverser

Le dossier `firmware/` ne porte pas le nom du croquis : `arduino-cli` exige
que le dossier s'appelle comme le `.ino`. Copier les deux fichiers dans un
dossier `RoofController/` avant de compiler.

Avec l'IDE Arduino : ouvrir `RoofController.ino`, l'IDE propose de déplacer le
croquis dans un dossier conforme — accepter.

Avec `arduino-cli` (installé avec l'IDE Arduino 2.x) :

```powershell
$cli = "$env:LOCALAPPDATA\Programs\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe"

# compilation seule
& $cli compile --fqbn arduino:avr:uno --warnings all .\RoofController

# téléversement (fermer l'IDE Arduino et le serveur : le port doit être libre)
& $cli upload -p COM4 --fqbn arduino:avr:uno .\RoofController
```

L'ouverture du port redémarre l'Arduino. Le serveur attend 1,5 s après
l'ouverture puis vide le tampon : le message `EVT:BOOT:...` n'est pas
interprété comme une réponse.

Taille mesurée avec le noyau `arduino:avr` 1.8.8 : **4 484 octets de flash
(13 %)**, **345 octets de RAM (16 %)**.

## Essai au banc, avant de monter le toit

À faire **toit débrayé ou sur cales**, alimentation du moteur sous la main.

1. Ouvrir un moniteur série à 115200 bauds, fin de ligne « Nouvelle ligne ».
2. Mettre sous tension : un `EVT:BOOT:<ETAT>` doit apparaître une seule fois.
3. `STATUS` → `OK:<ETAT>` cohérent avec la position réelle.
4. Actionner chaque fin de course **à la main** : l'état doit basculer en
   `OPENED` ou `CLOSED` (avec anti-rebond, donc pas de clignotement).
5. `OPEN` → le moteur démarre en douceur, puis accélère.
6. `STOP` pendant le mouvement → arrêt en ~200 ms, état `STOPPED`.
7. `CLOSE` juste après le `STOP` → accepté, départ après le temps mort de
   400 ms. En revanche `CLOSE` **pendant** l'ouverture renvoie
   `ER:BUSY:OPENING`.
8. Provoquer un défaut : débrancher un fin de course pendant le mouvement.
   Le toit s'arrête, `EVT:NO_MOTION:ERROR` ou `EVT:LIMITS:ERROR`.
   `OPEN` → `ER:FAULT:ERROR`. `STOP` acquitte, puis `OPEN` repart.
9. Mesurer le temps de trajet réel et vérifier qu'il est **inférieur** à
   `ROOF_MAX_TRAVEL_MS` et égal à `full_travel_time` de la configuration.

## Réglages à ajuster sur l'installation réelle

| Symptôme | Réglage |
|---|---|
| Le toit ne démarre pas | augmenter `ROOF_PWM_MIN` |
| Démarrage trop brutal | augmenter `ROOF_RAMP_START_MS` |
| Le toit n'atteint pas la butée en 60 s | augmenter `ROOF_MAX_TRAVEL_MS` **et** `max_travel_time` côté serveur |
| Arrêts parasites en cours de route | augmenter `ROOF_DEBOUNCE_MS` |
| Le moteur « cogne » au changement de sens | augmenter `ROOF_DIRECTION_DEAD_MS` |

`ROOF_MAX_TRAVEL_MS` et `max_travel_time` (serveur) doivent rester **égaux** :
c'est le firmware qui doit trancher, jamais le serveur.

## Limites connues

- **Pas d'encodeur** : la position est déduite du temps de trajet côté
  serveur. Un toit poussé à la main hors tension n'est pas détecté.
- Un seul fin de course par extrémité. Une butée qui reste collée n'est
  détectée qu'en tentant de quitter la position (`NO_MOTION`).
- `analogWrite` sur D5/D6 utilise le timer 0/2 à ~980 Hz : le moteur siffle
  légèrement. Suffisant pour un toit, insuffisant pour un asservissement fin.
- Pas encore de commande de version : elle arrivera avec l'atelier Arduino
  (phase 10), qui générera `roof_config.h` et téléversera.
