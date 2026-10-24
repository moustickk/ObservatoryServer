"""Lien avec le controleur du toit (Arduino), reel ou simule.

Le reste du code ne connait que `RoofLink`. Deux implementations :
 - SerialRoofLink   : le vrai port serie
 - SimulatedRoofLink: un Arduino virtuel, pour developper sans materiel

Protocole du firmware (voir `firmware/RoofController.ino`) :

    commande            reponse
    PING / STATUS   ->  OK:<ETAT>
    OPEN / CLOSE    ->  OK:<ETAT>        ou  ER:BUSY:<ETAT>
    STOP            ->  OK:<ETAT>
    (inconnue)      ->  ER:UNKNOWN_CMD:<ETAT>

    messages asynchrones : EVT:<QUOI>:<ETAT>

Deux consequences pour ce module :

1. Une reponse de commande commence TOUJOURS par `OK:` ou `ER:`. Les lignes
   `EVT:` peuvent arriver a tout moment et ne doivent jamais etre prises
   pour la reponse a la commande en cours : c'est pourquoi elles sont
   ecartees explicitement au lieu d'etre confondues avec un etat.

2. Un refus du controleur (`ER:`) n'est pas une panne de liaison : le toit
   est joignable et son etat est connu. On leve `CommandRejected`, que le
   service traduit en refus propre, sans alarme de liaison.
"""

import logging
import threading
import time

import serial


log = logging.getLogger(__name__)

KNOWN_STATES = (
    "OPENED",
    "OPENING",
    "CLOSED",
    "CLOSING",
    "STOPPED",
    "ERROR",
    "UNKNOWN",
)

MOTION_STATES = ("OPENING", "CLOSING")

OK_PREFIX = "OK:"
ERROR_PREFIX = "ER:"
EVENT_PREFIX = "EVT:"


class LinkError(Exception):
    """Le lien avec le controleur est indisponible ou a echoue."""


class CommandRejected(LinkError):
    """Le controleur a refuse la commande, mais il repond.

    Distinct de `LinkError` : il n'y a pas de panne, seulement un etat qui
    interdit l'action (mouvement en cours, defaut non acquitte...).
    """

    def __init__(self, code, state=None):
        self.code = (code or "ERREUR").strip().upper()
        self.state = state if state in KNOWN_STATES else None

        detail = f"refus du controleur ({self.code})"
        if self.state:
            detail += f", etat {self.state}"

        super().__init__(detail)


def parse_state(line):
    """Extrait un etat connu d'une ligne serie, quel que soit son habillage.

    Le format du firmware termine toujours la ligne par l'etat courant, ce
    qui permet de le lire sans connaitre le detail du message.
    """

    if not line:
        return None

    tokens = [
        token.strip().upper()
        for token in str(line).split(":")
        if token.strip()
    ]

    for token in reversed(tokens):
        if token in KNOWN_STATES:
            return token

    return None


def parse_response(line):
    """Analyse une reponse de commande.

    Retourne `("ok", None, etat)` ou `("error", code, etat)`, ou None si la
    ligne n'est pas une reponse de commande.
    """

    if line.startswith(OK_PREFIX):
        return ("ok", None, parse_state(line))

    if line.startswith(ERROR_PREFIX):
        parts = line.split(":")
        code = parts[1].strip().upper() if len(parts) > 1 else ""
        return ("error", code or "ERREUR", parse_state(line))

    return None


class RoofLink:
    """Interface commune aux liaisons toit."""

    description = "inconnu"

    @property
    def connected(self):
        raise NotImplementedError

    def send(self, command, timeout=2.0):
        raise NotImplementedError

    def close(self):
        pass


class SerialRoofLink(RoofLink):
    """Liaison serie reelle, avec reconnexion a la demande."""

    RETRY_DELAY = 5.0

    def __init__(self, port, baudrate):
        self.port = port
        self.baudrate = baudrate
        self.description = f"{port}@{baudrate}"
        self._lock = threading.RLock()
        self._ser = None
        self._last_error = None
        self._last_attempt = 0.0

        # On tente l'ouverture, mais un echec n'est PAS definitif : le port
        # peut etre encore tenu par l'instance precedente (redemarrage) ou
        # l'Arduino debranche. Le thread serie retentera, et le serveur se
        # remettra seul en ligne quand le port redeviendra disponible.
        try:
            self._connect()
        except Exception as ex:
            self._last_error = str(ex)
            log.warning(
                "Ouverture de %s impossible (%s) : nouvelle tentative au "
                "prochain cycle",
                self.description,
                ex,
            )

    # -- interne ---------------------------------------------------------

    def _connect(self):
        self._last_attempt = time.monotonic()

        ser = serial.Serial(
            self.port,
            self.baudrate,
            timeout=1.0,
            write_timeout=2.0,
        )

        # L'ouverture du port redemarre l'Arduino (DTR) : on laisse le temps
        # au boot puis on jette la banniere EVT:BOOT:..., qui ne repond a
        # aucune commande.
        time.sleep(1.5)
        ser.reset_input_buffer()

        self._ser = ser
        log.info("Lien serie ouvert sur %s", self.description)

    def _drop(self, reason):
        self._last_error = reason
        if self._ser is not None:
            try:
                self._ser.close()
            except Exception:
                pass
        self._ser = None
        log.warning("Lien serie perdu : %s", reason)

    def _ensure_connected(self):
        if self._ser is not None and self._ser.is_open:
            return

        if time.monotonic() - self._last_attempt < self.RETRY_DELAY:
            raise LinkError(
                f"{self.description} indisponible ({self._last_error or 'hors ligne'})"
            )

        try:
            self._connect()
        except Exception as ex:
            self._last_error = str(ex)
            raise LinkError(f"reconnexion impossible : {ex}") from ex

    # -- API -------------------------------------------------------------

    @property
    def connected(self):
        return self._ser is not None and self._ser.is_open

    @property
    def last_error(self):
        return self._last_error

    def send(self, command, timeout=2.0):
        deadline = time.monotonic() + timeout

        with self._lock:
            self._ensure_connected()

            try:
                self._ser.write(f"{command}\n".encode())
                self._ser.flush()
            except (serial.SerialException, OSError) as ex:
                self._drop(str(ex))
                raise LinkError(str(ex)) from ex

            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break

                try:
                    self._ser.timeout = max(0.05, remaining)
                    raw = self._ser.readline()
                except (serial.SerialException, OSError) as ex:
                    self._drop(str(ex))
                    raise LinkError(str(ex)) from ex

                if not raw:
                    break

                line = raw.decode(errors="replace").strip()
                if not line:
                    continue

                if line.startswith(EVENT_PREFIX):
                    # Evenement du firmware : informatif, jamais une reponse.
                    log.debug("Toit, evenement : %s", line)
                    continue

                parsed = parse_response(line)

                if parsed is None:
                    if parse_state(line) is not None:
                        raise LinkError(
                            "reponse sans prefixe OK:/ER: : le firmware du "
                            "controleur est trop ancien, il faut le reflasher"
                        )
                    log.debug("Ligne serie ignoree : %r", line)
                    continue

                kind, code, state = parsed

                if kind == "ok":
                    if state is None:
                        raise LinkError(f"Reponse sans etat exploitable : {line!r}")
                    return state

                raise CommandRejected(code, state)

        raise LinkError(f"pas de reponse exploitable a {command}")


class SimulatedRoofLink(RoofLink):
    """Arduino virtuel : reproduit les regles visibles du firmware.

    Ce qui est reproduit : refus d'inversion de sens sans arret prealable,
    defaut bloquant, acquittement par STOP, arret de securite sur depassement
    du temps de trajet. Ce qui ne l'est pas : les rampes, l'anti-rebond et
    la detection de non-mouvement, qui demandent un vrai moteur.
    """

    description = "simulation"

    def __init__(self, travel_time=48.0, max_travel_time=50.0, initial_state="CLOSED"):
        self.travel_time = float(travel_time)
        self.max_travel_time = float(max_travel_time)
        self._lock = threading.RLock()
        self._state = initial_state if initial_state in KNOWN_STATES else "UNKNOWN"
        self._motion_start = None
        self._fault = False

    # -- interne ---------------------------------------------------------

    def _advance(self):
        if self._state not in MOTION_STATES or self._motion_start is None:
            return

        elapsed = time.time() - self._motion_start

        if elapsed >= self.max_travel_time:
            self._finish("ERROR")
            self._fault = True
        elif elapsed >= self.travel_time:
            self._finish("OPENED" if self._state == "OPENING" else "CLOSED")

    def _finish(self, new_state):
        self._state = new_state
        self._motion_start = None

    def _start(self, state):
        self._state = state
        self._motion_start = time.time()

    def _move(self, command):
        target = "OPENED" if command == "OPEN" else "CLOSED"
        moving = "OPENING" if command == "OPEN" else "CLOSING"

        if self._fault:
            raise CommandRejected("FAULT", self._state)

        if self._state == moving:
            return  # deja dans ce sens : idempotent

        if self._state in MOTION_STATES:
            # Le firmware refuse une inversion directe : STOP d'abord.
            raise CommandRejected("BUSY", self._state)

        if self._state == target:
            return

        self._start(moving)

    # -- API -------------------------------------------------------------

    @property
    def connected(self):
        return True

    def send(self, command, timeout=2.0):
        with self._lock:
            self._advance()

            cmd = (command or "").strip().upper()

            if cmd in ("STATUS", "PING"):
                return self._state

            if cmd in ("OPEN", "CLOSE"):
                self._move(cmd)
                return self._state

            if cmd == "STOP":
                # Seule commande qui acquitte un defaut.
                self._fault = False
                self._state = "STOPPED"
                self._motion_start = None
                return self._state

            raise CommandRejected("UNKNOWN_CMD", self._state)


class UnavailableRoofLink(RoofLink):
    """Lien volontairement inactif : le serveur demarre quand meme.

    Consequence : le toit est vu UNKNOWN et toute commande est refusee.
    """

    def __init__(self, reason):
        self.reason = reason
        self.description = f"indisponible ({reason})"

    @property
    def connected(self):
        return False

    def send(self, command, timeout=2.0):
        raise LinkError(self.reason)


def build_roof_link(settings):
    """Instancie la liaison adaptee a la configuration."""

    if settings.get("simulation"):
        log.info("Toit en SIMULATION (aucun mouvement physique)")
        return SimulatedRoofLink(
            travel_time=settings.get("full_travel_time", 48),
            max_travel_time=settings.get("max_travel_time", 50),
        )

    port = settings.get("serial_port", "COM4")
    baudrate = settings.get("baudrate", 115200)

    try:
        return SerialRoofLink(port, baudrate)
    except Exception as ex:
        log.error(
            "Ouverture de %s impossible (%s) : le serveur demarre sans toit",
            port,
            ex,
        )
        return UnavailableRoofLink(str(ex))
