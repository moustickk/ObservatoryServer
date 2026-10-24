"""Agent de sauvegarde : ferme le toit quand la meteo devient dangereuse.

NINA est le maitre d'oeuvre, mais il peut etre ferme, plante, ou simplement
en train d'executer une autre sequence. Si la meteo passe en UNSAFE, le toit
doit se fermer meme sans lui : c'est le role de cet agent.

Regles
------
1. **Jamais a l'aveugle.** L'agent ne fait rien tant qu'aucune donnee meteo
   n'a ete recue (`data_age_minutes < 0`) : au demarrage, l'etat par defaut
   est UNSAFE, il ne doit pas provoquer une fermeture intempestive.
2. **Grace de parkage.** Si la monture n'est pas encore parquee, l'agent lui
   laisse `park_grace_seconds` (180 s par defaut) pour finir son parkage. Une
   monture qui se parque pendant deux minutes est normale ; un toit qui se
   ferme sur elle ne l'est pas.
3. **Pas d'acharnement.** Une tentative ratee est retentee apres un delai de
   repos, et l'agent ne se re-arme qu'au retour du SAFE.
4. **L'interlock reste maitre.** L'agent appelle `DomeService.close()`, donc
   les memes verifications s'appliquent. Il ne force jamais rien.
"""

import logging
import threading
import time


log = logging.getLogger(__name__)

# Frequence de lecture de l'etat meteo (variable locale, pas d'appel reseau).
CHECK_SECONDS = 15.0

# Delai avant de retenter une fermeture qui a echoue.
RETRY_SECONDS = 120.0

# Pas de la boucle d'attente du parkage.
GRACE_POLL_SECONDS = 2.0

MOTION_DONE_STATES = ("CLOSED", "CLOSING")


class BackupAgent:

    def __init__(self, dome, safety, settings, stop_event=None,
                 grace_poll_seconds=GRACE_POLL_SECONDS):
        self.dome = dome
        self.safety = safety
        self.grace_seconds = float(settings.get("park_grace_seconds", 180))
        self.grace_poll_seconds = float(grace_poll_seconds)
        self.stop_event = stop_event or threading.Event()

        self._handled = False
        self._last_attempt = 0.0

    # -- cycle de vie ----------------------------------------------------

    def start(self):
        thread = threading.Thread(
            target=self._loop,
            name="safety-agent",
            daemon=True,
        )
        thread.start()
        return thread

    # -- boucle ----------------------------------------------------------

    def _loop(self):
        log.info(
            "Agent de sauvegarde demarre (grace de parkage %.0f s)",
            self.grace_seconds,
        )

        while not self.stop_event.is_set():
            try:
                action = self.tick()
                if action not in (None, "safe", "no_data", "already"):
                    log.info("Agent de sauvegarde : %s", action)
            except Exception:
                log.exception("Agent de sauvegarde : erreur inattendue")

            self.stop_event.wait(CHECK_SECONDS)

        log.info("Agent de sauvegarde arrete")

    # -- decision --------------------------------------------------------

    def tick(self, now=None):
        """Un tour de decision. Retourne une chaine courte (utile aux tests)."""

        status = self.safety.status()
        safe = status.get("safe")
        age = status.get("data_age_minutes", -1)

        if age is None or age < 0:
            return "no_data"

        if safe:
            self._handled = False
            return "safe"

        state = self.dome.state.get("state")

        if state in MOTION_DONE_STATES:
            return "already"

        if now is None:
            now = time.monotonic()

        if self._handled and (now - self._last_attempt) < RETRY_SECONDS:
            return "backoff"

        self._last_attempt = now
        self._handled = True

        # Une ouverture en cours doit etre interrompue avant de fermer : le
        # firmware refuse une inversion directe (ER:BUSY).
        if state == "OPENING":
            self.dome.stop()

        if not self._wait_for_park():
            message = (
                "Meteo dangereuse et monture non parquee apres "
                f"{self.grace_seconds:.0f} s : le toit n'a pas ete ferme "
                "(close_anyway = false)"
            )
            self.dome.state.raise_alarm("ROOF_UNSAFE_NOT_PARKED", message)
            log.error(message)
            return "not_parked"

        result = self.dome.close()

        if result.get("ok"):
            return "closed"

        log.warning(
            "Fermeture de sauvegarde refusee : %s",
            result.get("message") or result.get("code"),
        )
        return "refused"

    # -- attente de parkage ----------------------------------------------

    def _wait_for_park(self):
        """True si la monture est parquee (ou si l'interlock est desactive)."""

        if getattr(self.dome, "mount_check_mode", "strict") == "disabled":
            return True

        deadline = time.monotonic() + self.grace_seconds
        logged = False

        while True:
            if self.dome.mount.at_park() is True:
                return True

            if time.monotonic() >= deadline:
                return False

            if not logged:
                log.warning(
                    "Meteo dangereuse : attente du parkage de la monture "
                    "(jusqu'a %.0f s)",
                    self.grace_seconds,
                )
                logged = True

            if self.stop_event.wait(self.grace_poll_seconds):
                return False
