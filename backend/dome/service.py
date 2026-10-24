"""Commandes du toit, avec interlock de parkage de la monture.

Regle de securite (decision projet) : le toit ne bouge jamais au-dessus d'une
monture non parquee. Si l'etat de la monture est indeterminable, on refuse
aussi (une collision coute plus cher qu'une nuit perdue). Le refus leve une
alarme explicite, exposee par l'API et, plus tard, par Alpaca.
"""

import logging
import threading

from backend.dome.logging import log_close, log_open, log_stop
from backend.dome.serial_link import LinkError
from backend.dome.state import RoofState


log = logging.getLogger(__name__)


class DomeService:

    def __init__(self, roof_link, mount_link, settings):
        self.roof = roof_link
        self.mount = mount_link
        self.settings = settings
        self.state = RoofState(travel_time=settings.get("full_travel_time", 45))
        self.mount_check_mode = settings.get("mount_check_mode", "strict")
        self.close_anyway = bool(settings.get("close_anyway", False))
        self._lock = threading.RLock()

    # -- resultats -------------------------------------------------------

    def _result(self, ok, code=None, message=None):
        result = {
            "ok": ok,
            "state": self.state.get("state"),
            "position": self.state.position(),
            "alarm": self.state.alarm,
        }
        if code is not None:
            result["code"] = code
        if message is not None:
            result["message"] = message
        return result

    def _link_failure(self, action, error):
        message = f"Liaison toit indisponible pendant {action} : {error}"
        self.state.raise_alarm("ROOF_LINK", message)
        self.state.set_state("UNKNOWN")
        self.state.save()
        log.error(message)
        return self._result(False, "ROOF_LINK", message)

    # -- interlock -------------------------------------------------------

    def _interlock(self, action):
        """Retourne un resultat de refus, ou None si le mouvement est permis."""

        if self.mount_check_mode == "disabled":
            return None

        at_park = self.mount.at_park()

        if at_park is True:
            return None

        if at_park is False:
            code = "MOUNT_NOT_PARKED"
            message = (
                "Monture non parquee : mouvement du toit refuse "
                "(protection anti-collision)"
            )
        else:
            code = "MOUNT_UNKNOWN"
            message = (
                "Etat de parkage de la monture indeterminable "
                f"({self.mount.description}) : mouvement refuse"
            )

        # Seule exception explicite : fermer malgre tout, si l'utilisateur
        # l'a active en configuration.
        if action == "close" and self.close_anyway:
            log.warning("%s mais close_anyway est actif : fermeture forcee", message)
            return None

        self.state.raise_alarm(code, message)
        log.critical("Toit %s refuse : %s", action, message)
        return self._result(False, code, message)

    # -- commandes -------------------------------------------------------

    def open(self):
        with self._lock:
            refusal = self._interlock("open")
            if refusal is not None:
                return refusal

            try:
                state = self.roof.send("OPEN")
            except LinkError as ex:
                return self._link_failure("open", ex)

            self.state.set_state(state)
            self.state.clear_alarm()
            self.state.save()
            log_open()
            log.info("Ouverture demandee, etat=%s", state)
            return self._result(True)

    def close(self):
        with self._lock:
            refusal = self._interlock("close")
            if refusal is not None:
                return refusal

            try:
                state = self.roof.send("CLOSE")
            except LinkError as ex:
                return self._link_failure("close", ex)

            self.state.set_state(state)
            self.state.clear_alarm()
            self.state.save()
            log_close()
            log.info("Fermeture demandee, etat=%s", state)
            return self._result(True)

    def stop(self):
        with self._lock:
            try:
                state = self.roof.send("STOP")
            except LinkError as ex:
                return self._link_failure("stop", ex)

            # Arret : la position est figee, pas de derive par temps de trajet.
            self.state.set_state(state or "STOPPED")
            self.state.save()
            log_stop()
            log.info("Arret demande, etat=%s", state)
            return self._result(True)

    # -- surveillance ----------------------------------------------------

    def sync(self):
        """Interroge le controleur et met l'etat a jour. Retourne l'etat."""

        with self._lock:
            try:
                state = self.roof.send("STATUS")
            except LinkError as ex:
                if self.roof.connected:
                    log.warning("STATUS impossible : %s", ex)
                previous = self.state.get("state")
                self.state.set_state("UNKNOWN")
                if previous != "UNKNOWN":
                    self.state.save()
                return "UNKNOWN"

            previous = self.state.get("state")
            if state != previous:
                self.state.set_state(state)
                self.state.save()
                log.info("Etat du toit : %s -> %s", previous, state)

            return state

    # -- etat ------------------------------------------------------------

    def status(self):
        snapshot = self.state.snapshot()
        return {
            "state": snapshot["state"],
            "position": snapshot["position"],
            "alarm": snapshot["alarm"],
            "link": {
                "connected": self.roof.connected,
                "description": self.roof.description,
            },
            "mount": {
                "available": self.mount.available,
                "at_park": self.mount.at_park(),
                "description": self.mount.description,
            },
        }
