"""Lien avec le controleur du toit (Arduino), reel ou simule.

Le reste du code ne connait que `RoofLink`. Deux implementations :
 - SerialRoofLink   : le vrai port serie
 - SimulatedRoofLink: un Arduino virtuel, pour developper sans materiel

Le protocole actuel (texte, une ligne par reponse) est tolere ici, en
attendant le protocole OK:/EVT: de la phase 3.
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


class LinkError(Exception):
    """Le lien avec le controleur est indisponible ou a echoue."""


def parse_state(line):
    """Extrait un etat connu d'une ligne serie, quel que soit son habillage.

    Tolere l'ancien format ("Etat initial : CLOSED", "OPENED") comme le
    futur format prefixe ("OK:OPENED", "EVT:BOOT:CLOSED").
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
        self._connect()

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
        # au boot puis on jette la banniere "Etat initial : ...".
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

            # On lit jusqu'a obtenir un etat reconnaissable : les lignes
            # asynchrones du firmware sont ignorees plutot que confondues
            # avec la reponse a la commande.
            while time.monotonic() < deadline:
                try:
                    self._ser.timeout = max(0.05, deadline - time.monotonic())
                    raw = self._ser.readline()
                except (serial.SerialException, OSError) as ex:
                    self._drop(str(ex))
                    raise LinkError(str(ex)) from ex

                if not raw:
                    break

                line = raw.decode(errors="replace").strip()
                if not line:
                    continue

                state = parse_state(line)
                if state is not None:
                    return state

                log.debug("Ligne serie ignoree : %r", line)

        raise LinkError(f"pas de reponse exploitable a {command}")


class SimulatedRoofLink(RoofLink):
    """Arduino virtuel : reproduit la machine a etats du firmware."""

    description = "simulation"

    def __init__(self, travel_time=45.0, max_travel_time=55.0, initial_state="CLOSED"):
        self.travel_time = float(travel_time)
        self.max_travel_time = float(max_travel_time)
        self._lock = threading.RLock()
        self._state = initial_state if initial_state in KNOWN_STATES else "UNKNOWN"
        self._motion_start = None

    # -- interne ---------------------------------------------------------

    def _advance(self):
        if self._state not in ("OPENING", "CLOSING") or self._motion_start is None:
            return

        elapsed = time.time() - self._motion_start

        if elapsed >= self.max_travel_time:
            self._finish("ERROR")
        elif elapsed >= self.travel_time:
            self._finish("OPENED" if self._state == "OPENING" else "CLOSED")

    def _finish(self, new_state):
        self._state = new_state
        self._motion_start = None

    def _start(self, state):
        self._state = state
        self._motion_start = time.time()

    # -- API -------------------------------------------------------------

    @property
    def connected(self):
        return True

    def send(self, command, timeout=2.0):
        with self._lock:
            self._advance()

            cmd = (command or "").strip().upper()

            if cmd == "STATUS":
                return self._state

            if cmd == "OPEN":
                if self._state not in ("OPENED", "OPENING"):
                    self._start("OPENING")
                return self._state

            if cmd == "CLOSE":
                if self._state not in ("CLOSED", "CLOSING"):
                    self._start("CLOSING")
                return self._state

            if cmd == "STOP":
                self._state = "STOPPED"
                self._motion_start = None
                return self._state

            if cmd == "PING":
                return self._state

            return "ERROR"


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
            travel_time=settings.get("full_travel_time", 45),
            max_travel_time=settings.get("max_travel_time", 55),
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
