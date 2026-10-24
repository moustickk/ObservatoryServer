"""Etat du toit, protege par un verrou.

La position est une estimation par temps de trajet : elle sert a l'affichage,
pas a la securite (celle-ci repose sur les fins de course du firmware).
Un arret ou une erreur fige la position au lieu de la laisser deriver.
"""

import threading
import time

from backend.common.state import load_state, save_state


MOTION_STATES = ("OPENING", "CLOSING")


class RoofState:

    def __init__(self, travel_time=45.0):
        self._lock = threading.RLock()
        self.travel_time = max(1.0, float(travel_time))
        self._data = load_state()
        self._alarm = None
        self._normalise()

    # -- interne ---------------------------------------------------------

    def _normalise(self):
        self._data.setdefault("state", "UNKNOWN")
        self._data.setdefault("position", -1)
        self._data.setdefault("timestamp", time.time())

    # -- lecture ---------------------------------------------------------

    def snapshot(self):
        with self._lock:
            data = dict(self._data)
            data["position"] = self.position()
            data["alarm"] = dict(self._alarm) if self._alarm else None
            return data

    def get(self, key, default=None):
        with self._lock:
            return self._data.get(key, default)

    def position(self):
        with self._lock:
            return _estimate_position(self._data, self.travel_time)

    # -- ecriture --------------------------------------------------------

    def set_state(self, state, position=None):
        with self._lock:
            previous = _estimate_position(self._data, self.travel_time)

            if state in MOTION_STATES:
                start = previous if position is None else position
            elif state == "OPENED":
                start = 100
            elif state == "CLOSED":
                start = 0
            else:
                start = previous if position is None else position

            self._data["state"] = state
            self._data["position"] = int(start)
            self._data["timestamp"] = time.time()

    def save(self):
        with self._lock:
            save_state(dict(self._data))

    # -- alarme ----------------------------------------------------------

    @property
    def alarm(self):
        with self._lock:
            return dict(self._alarm) if self._alarm else None

    def raise_alarm(self, code, message):
        with self._lock:
            self._alarm = {
                "code": code,
                "message": message,
                "since": time.strftime("%Y-%m-%d %H:%M:%S"),
            }

    def clear_alarm(self):
        with self._lock:
            self._alarm = None


def _estimate_position(data, travel_time):
    """Position 0-100 deduite de l'etat et du temps de trajet."""

    state = data.get("state", "UNKNOWN")

    if state == "OPENED":
        return 100

    if state == "CLOSED":
        return 0

    stored = data.get("position", -1)

    if state not in MOTION_STATES:
        return int(stored)

    if stored < 0:
        return -1

    elapsed = max(0.0, time.time() - data.get("timestamp", time.time()))
    delta = (elapsed / travel_time) * 100

    if state == "OPENING":
        return int(min(100, stored + delta))

    return int(max(0, stored - delta))
