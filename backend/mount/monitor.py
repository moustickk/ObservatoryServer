"""Surveillance de la monture dans un thread dedie.

Les appels ASCOM (EQMOD) sont des appels COM : ils peuvent prendre des
centaines de millisecondes, voire bloquer si le driver est occupe par NINA.
Les faire depuis le thread d'une requete HTTP revient a bloquer NINA.

Ici, un seul thread interroge `AtPark` a intervalle fixe et publie la reponse
dans un cache. Le reste du programme lit ce cache : `at_park()` ne peut donc
plus bloquer.

Le thread initialise lui-meme son appartement COM (`CoInitialize`) et le
libere en sortant : c'est la condition pour que `win32com` fonctionne hors du
thread principal. Les methodes de `AscomMountLink` supposent donc etre
appelees depuis ce thread, et uniquement depuis lui.
"""

import logging
import queue
import threading
import time

try:
    import pythoncom
except ImportError:  # pragma: no cover - hors Windows
    pythoncom = None


log = logging.getLogger(__name__)

POLL_SECONDS = 2.0

# Au-dela, la derniere valeur connue n'est plus consideree comme actuelle.
# Une monture dont l'etat est inconnu interdit tout mouvement du toit : il
# vaut mieux refuser que parier sur une valeur vieille de dix secondes.
STALE_SECONDS = 8.0


class _ParkRequest:

    __slots__ = ("timeout", "done", "ok", "error")

    def __init__(self, timeout):
        self.timeout = timeout
        self.done = threading.Event()
        self.ok = False
        self.error = None


class MountMonitor:
    """Cache l'etat de parkage, rafraichi par un thread COM dedie."""

    def __init__(self, link, poll_seconds=POLL_SECONDS, stale_seconds=STALE_SECONDS):
        self.link = link
        self.poll_seconds = float(poll_seconds)
        self.stale_seconds = float(stale_seconds)

        # RLock : `snapshot()` appelle `at_park()`, qui prend le meme verrou.
        self._lock = threading.RLock()
        self._at_park = None
        self._updated_at = 0.0
        self._error = None

        self._requests = queue.Queue()
        self._stop = threading.Event()
        self._thread = None

    # -- cycle de vie ----------------------------------------------------

    def start(self):
        if self._thread is not None and self._thread.is_alive():
            return

        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop,
            name="mount-com",
            daemon=True,
        )
        self._thread.start()
        log.info("Thread monture demarre (%s)", self.link.description)

    def stop(self):
        self._stop.set()

        thread = self._thread
        if thread is not None:
            thread.join(timeout=5.0)

        self._thread = None

    # -- lecture ---------------------------------------------------------

    @property
    def description(self):
        return self.link.description

    @property
    def available(self):
        return bool(getattr(self.link, "available", False))

    @property
    def last_error(self):
        with self._lock:
            return self._error

    def at_park(self):
        """True / False, ou None si l'information n'est pas actuelle."""

        with self._lock:
            if not self._updated_at:
                return None

            if (time.monotonic() - self._updated_at) > self.stale_seconds:
                return None

            return self._at_park

    def snapshot(self):
        with self._lock:
            age = (time.monotonic() - self._updated_at) if self._updated_at else None

            return {
                "at_park": self.at_park(),
                "age": age,
                "stale": age is None or age > self.stale_seconds,
                "available": bool(getattr(self.link, "available", False)),
                "description": self.link.description,
                "error": self._error,
            }

    # -- commandes -------------------------------------------------------

    def park(self, timeout=None):
        """Demande le parkage et attend le resultat (appel borne dans le temps)."""

        if self._thread is None or not self._thread.is_alive():
            return False

        request = _ParkRequest(timeout)
        self._requests.put(request)

        wait_for = float(timeout if timeout is not None else 60.0) + 5.0
        if not request.done.wait(wait_for):
            return False

        if request.error:
            log.warning("Parkage impossible : %s", request.error)

        return request.ok

    # -- interne ---------------------------------------------------------

    def _publish(self, value, error=None):
        with self._lock:
            self._at_park = value
            self._updated_at = time.monotonic()
            self._error = error

    def _poll(self):
        try:
            self._publish(self.link.at_park())

        except Exception as ex:  # driver absent, COM en vrac...
            self._publish(None, str(ex))

    def _handle_park(self, request):
        try:
            request.ok = bool(self.link.park(request.timeout))
            # Un parkage confirme est une valeur connue, pas une inconnue :
            # publier None ici ferait croire a un etat indetermine pendant
            # tout un cycle de sondage (et bloquerait le toit au passage).
            self._publish(True if request.ok else None)
        except Exception as ex:
            request.error = str(ex)
            request.ok = False
            self._publish(None)
        finally:
            request.done.set()

    def _loop(self):
        if pythoncom is not None:
            pythoncom.CoInitialize()

        try:
            while not self._stop.is_set():
                try:
                    request = self._requests.get(timeout=self.poll_seconds)
                except queue.Empty:
                    request = None

                if request is not None:
                    self._handle_park(request)
                    continue

                self._poll()

        finally:
            if pythoncom is not None:
                try:
                    pythoncom.CoUninitialize()
                except Exception:  # pragma: no cover
                    pass
