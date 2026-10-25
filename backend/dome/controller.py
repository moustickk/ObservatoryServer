"""Thread unique proprietaire de la liaison serie du toit.

Pourquoi un thread dedie
------------------------
NINA interroge le dome une vingtaine de fois par cycle. Si chaque lecture
ouvrait le port serie, une carte lente ou un câble capricieux bloquerait la
requete HTTP, et surtout deux lectures concurrentes pourraient se melanger
sur le fil (`OK:...` d'une commande lue par une autre).

Ici, un seul thread parle au controleur :

 - il envoie les commandes recues dans une file et rend la reponse a
   l'appelant via un `Event` ;
 - entre deux commandes, il interroge `STATUS` a intervalle fixe et publie
   l'etat dans un cache protege par verrou.

Les proprietes Alpaca et l'API REST ne lisent donc que ce cache : elles ne
touchent jamais le port serie et ne peuvent pas etre bloquees par lui.

Le cache porte un horodatage. Si le controleur ne repond plus, l'etat devient
"perime" (`stale`) : le service le traduit en `UNKNOWN`, ce qui est le
comportement attendu cote Alpaca (ShutterStatus = Error).
"""

import logging
import queue
import threading
import time

from backend.dome.serial_link import CommandRejected, LinkError


log = logging.getLogger(__name__)

# Intervalle entre deux interrogations de fond.
POLL_SECONDS = 0.5

# Au-dela, l'etat en cache n'est plus considere comme fiable. Trois fois
# l'intervalle de sondage : tolere un ou deux cycles rates, pas une panne.
STALE_SECONDS = 5.0

# Delai maximal d'attente d'une commande (aller-retour serie compris).
COMMAND_TIMEOUT = 5.0


class _Request:
    """Une commande en attente d'execution par le thread serie."""

    __slots__ = ("command", "done", "state", "error")

    def __init__(self, command):
        self.command = command
        self.done = threading.Event()
        self.state = None
        self.error = None


class RoofController:
    """Serialise tous les echanges serie et publie un etat en cache."""

    def __init__(self, link, poll_seconds=POLL_SECONDS, stale_seconds=STALE_SECONDS):
        self.link = link
        self.description = link.description
        self.poll_seconds = float(poll_seconds)
        self.stale_seconds = float(stale_seconds)

        self._queue = queue.Queue()
        self._lock = threading.Lock()
        self._state = None
        self._updated_at = 0.0
        self._connected = False
        self._last_error = None

        self._stop = threading.Event()
        self._thread = None

    # -- cycle de vie ----------------------------------------------------

    def start(self):
        if self._thread is not None and self._thread.is_alive():
            return

        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop,
            name="roof-serial",
            daemon=True,
        )
        self._thread.start()
        log.info("Thread serie du toit demarre (%s)", self.description)

    def stop(self):
        self._stop.set()

        thread = self._thread
        if thread is not None:
            thread.join(timeout=3.0)

        self._thread = None

    def close(self):
        self.stop()

        try:
            self.link.close()
        except Exception:  # pragma: no cover - fermeture best effort
            log.debug("Fermeture de la liaison toit : erreur ignoree", exc_info=True)

    # -- suspension (atelier Arduino) ------------------------------------

    def pause(self):
        """Libere le port serie pour un televersement.

        Le thread est arrete et le port ferme : avrdude ne peut pas ouvrir
        COM4 tant qu'un autre processus le tient. L'appelant doit avoir
        verifie que le toit est immobile.
        """

        log.warning("Liaison serie suspendue (port libere)")
        self.stop()

        try:
            self.link.close()
        except Exception:
            log.debug("Fermeture du port pendant la suspension", exc_info=True)

    def resume(self):
        """Reprend la liaison apres un televersement."""

        reset = getattr(self.link, "reset_retry", None)

        if callable(reset):
            reset()

        self.start()
        log.warning("Liaison serie reprise")

    # -- API -------------------------------------------------------------

    def command(self, name, timeout=COMMAND_TIMEOUT):
        """Envoie une commande et attend son execution par le thread serie."""

        if self._thread is None or not self._thread.is_alive():
            raise LinkError("thread de liaison toit arrete")

        request = _Request(name)
        self._queue.put(request)

        if not request.done.wait(timeout):
            raise LinkError(
                f"pas de reponse du controleur a {name} apres {timeout:.1f} s"
            )

        if request.error is not None:
            raise request.error

        return request.state

    def snapshot(self):
        """Etat en cache, sans aucun acces au port serie."""

        with self._lock:
            age = (time.monotonic() - self._updated_at) if self._updated_at else None

            return {
                "state": self._state,
                "age": age,
                "stale": age is None or age > self.stale_seconds,
                "connected": self._connected,
                "description": self.description,
                "last_error": self._last_error,
            }

    # -- interne ---------------------------------------------------------

    def _record_state(self, state):
        with self._lock:
            self._state = state
            self._updated_at = time.monotonic()
            self._connected = bool(getattr(self.link, "connected", True))
            self._last_error = None

    def _record_failure(self, error):
        """Panne de liaison : on ne rafraichit PAS l'horodatage.

        C'est ce qui rend l'etat perime au bout de `stale_seconds`, donc
        traduit en UNKNOWN : un dernier etat connu n'est pas une verite
        actuelle.
        """

        with self._lock:
            self._connected = False
            self._last_error = str(error)

    def _execute(self, request):
        try:
            request.state = self.link.send(request.command)
            self._record_state(request.state)

        except CommandRejected as ex:
            request.error = ex
            # Un refus n'est pas une panne : le controleur repond et son
            # etat est valide.
            if ex.state:
                self._record_state(ex.state)
            else:
                self._record_failure(ex)

        except LinkError as ex:
            request.error = ex
            self._record_failure(ex)

        except Exception as ex:  # pragma: no cover - garde-fou
            request.error = LinkError(str(ex))
            self._record_failure(ex)

        finally:
            request.done.set()

    def _poll(self):
        try:
            self._record_state(self.link.send("STATUS", timeout=1.0))

        except CommandRejected as ex:
            if ex.state:
                self._record_state(ex.state)

        except LinkError as ex:
            self._record_failure(ex)

        except Exception as ex:  # pragma: no cover - garde-fou
            self._record_failure(ex)

    def _loop(self):
        while not self._stop.is_set():
            try:
                request = self._queue.get(timeout=self.poll_seconds)
            except queue.Empty:
                request = None

            if request is not None:
                self._execute(request)
                continue

            self._poll()

        # Repondre aux commandes encore en file avant de sortir, pour ne pas
        # laisser un appelant bloque jusqu'a son timeout.
        while True:
            try:
                request = self._queue.get_nowait()
            except queue.Empty:
                break
            request.error = LinkError("liaison toit arretee")
            request.done.set()
