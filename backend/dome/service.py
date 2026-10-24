"""Commandes du toit, avec interlock de parkage de la monture.

Regle de securite (decision projet) : le toit ne bouge jamais au-dessus d'une
monture non parquee. Si l'etat de la monture est indeterminable, on refuse
aussi (une collision coute plus cher qu'une nuit perdue). Le refus leve une
alarme explicite, exposee par l'API et, plus tard, par Alpaca.
"""

import logging
import threading

from backend.dome.logging import log_close, log_open, log_stop
from backend.dome.serial_link import CommandRejected, LinkError
from backend.dome.state import RoofState


log = logging.getLogger(__name__)

# Refus benins : le controleur repond, le toit est en bon etat, il faut
# simplement reessayer au bon moment. Ils ne declenchent pas d'alarme.
BENIGN_REJECTIONS = ("BUSY",)

# Traduction des refus du firmware en consignes utilisables par l'operateur
# (le message remonte tel quel dans NINA).
REJECTION_MESSAGES = {
    "BUSY": "un mouvement de sens oppose est en cours : arreter le toit "
            "d'abord (Stop / Abort), puis relancer la commande",
    "FAULT": "le controleur est en defaut (fin de course, temps de trajet "
             "depasse ou moteur bloque) : acquitter par STOP apres verification",
    "LINE_TOO_LONG": "commande trop longue recue par le controleur",
    "UNKNOWN_CMD": "commande inconnue du firmware : verifier que le "
                   "controleur a bien la version attendue",
}


class DomeService:

    def __init__(self, roof_link, mount_link, settings):
        self.roof = roof_link
        self.mount = mount_link
        self.settings = settings
        self.state = RoofState(travel_time=settings.get("full_travel_time", 45))
        self.mount_check_mode = settings.get("mount_check_mode", "strict")
        self.close_anyway = bool(settings.get("close_anyway", False))
        self.park_timeout = float(settings.get("park_timeout", 300))
        self._lock = threading.RLock()
        self._parking = False

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

    def _rejected(self, action, error):
        """Refus venu du controleur : ce n'est pas une panne de liaison.

        Le toit repond et son etat est connu : on le conserve au lieu de le
        declarer UNKNOWN, et on n'alarme que si le refus signale un defaut
        (un BUSY est un simple concours de commandes).
        """

        if error.state:
            self.state.set_state(error.state)

        detail = REJECTION_MESSAGES.get(error.code, str(error))
        message = f"Toit : {detail}"

        if error.code in BENIGN_REJECTIONS:
            log.warning("Toit %s : %s", action, message)
        else:
            self.state.raise_alarm(f"ROOF_{error.code}", message)
            log.error("Toit %s : %s", action, message)

        self.state.save()
        return self._result(False, error.code, message)

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
                state = self.roof.command("OPEN")
            except CommandRejected as ex:
                return self._rejected("open", ex)
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
                state = self.roof.command("CLOSE")
            except CommandRejected as ex:
                return self._rejected("close", ex)
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
                state = self.roof.command("STOP")
            except CommandRejected as ex:
                return self._rejected("stop", ex)
            except LinkError as ex:
                return self._link_failure("stop", ex)

            # Arret : la position est figee, pas de derive par temps de trajet.
            self.state.set_state(state or "STOPPED")
            self.state.save()
            log_stop()
            log.info("Arret demande, etat=%s", state)
            return self._result(True)

    # -- monture ---------------------------------------------------------

    def park_mount(self, timeout=None):
        """Demande le parkage de la monture, sans bloquer l'appelant.

        Le parkage peut durer plusieurs minutes : le faire dans la requete
        HTTP bloquerait NINA. On lance un thread dedie et on repond tout de
        suite ; l'etat reel se lit ensuite via `mount.at_park()`.
        """

        if not hasattr(self.mount, "park"):
            return self._result(False, "MOUNT_PARK_UNAVAILABLE")

        with self._lock:
            if self._parking:
                return self._result(True, "PARKING", "parkage deja en cours")

            self._parking = True

        thread = threading.Thread(
            target=self._park_mount_worker,
            args=(timeout,),
            name="mount-park",
            daemon=True,
        )
        thread.start()

        log.info("Parkage de la monture demande")
        return self._result(True, "PARKING", "parkage demande")

    def _park_mount_worker(self, timeout):
        try:
            if self.mount.park(timeout if timeout is not None else self.park_timeout):
                log.info("Monture parquee sur demande")
            else:
                log.warning("Parkage de la monture non confirme")
        except Exception:
            log.exception("Erreur pendant le parkage de la monture")
        finally:
            with self._lock:
                self._parking = False

    # -- surveillance ----------------------------------------------------
    def sync(self):
        """Recopie l'etat publie par le thread serie. Aucun acces au port.

        Le thread dedie interroge le controleur en continu ; ici on ne fait
        que lire son cache. Un cache perime signifie que le controleur ne
        repond plus : on le traduit en UNKNOWN plutot que de presenter un
        etat qui n'est peut-etre plus vrai.
        """

        snapshot = self.roof.snapshot()
        previous = self.state.get("state")

        if snapshot["stale"]:
            # Aucune donnee encore recue (premier sondage en cours) : ce
            # n'est pas une panne, on ne journalise rien et on ne sauvegarde
            # pas un UNKNOWN qui n'a pas de sens.
            if snapshot["age"] is None:
                return "UNKNOWN"

            if previous != "UNKNOWN":
                self.state.set_state("UNKNOWN")
                self.state.save()
                log.warning(
                    "Etat du toit perime (%s) : %s -> UNKNOWN",
                    snapshot["last_error"] or "sans reponse",
                    previous,
                )
            return "UNKNOWN"

        state = snapshot["state"]

        if state and state != previous:
            self.state.set_state(state)
            self.state.save()
            log.info("Etat du toit : %s -> %s", previous, state)

        return state or "UNKNOWN"

    # -- etat ------------------------------------------------------------

    def status(self):
        snapshot = self.state.snapshot()
        link = self.roof.snapshot()

        if hasattr(self.mount, "snapshot"):
            mount = self.mount.snapshot()
        else:  # pragma: no cover - liaison sans cache
            mount = {
                "at_park": self.mount.at_park(),
                "available": self.mount.available,
                "description": self.mount.description,
            }

        return {
            "state": snapshot["state"],
            "position": snapshot["position"],
            "alarm": snapshot["alarm"],
            "link": {
                "connected": link["connected"],
                "description": link["description"],
                "stale": link["stale"],
                "last_error": link["last_error"],
            },
            "mount": {
                "available": mount["available"],
                "at_park": mount["at_park"],
                "description": mount["description"],
                "stale": mount.get("stale", False),
            },
        }
