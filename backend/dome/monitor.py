"""Surveillance de l'etat du toit.

Une seule boucle, un seul verrou cote DomeService. On ne journalise que les
changements d'etat : l'ancienne version reecrivait tout le fichier de log
chaque seconde.
"""

import logging
import threading


log = logging.getLogger(__name__)

POLL_SECONDS = 1.0


def monitor_loop(dome, stop_event):
    log.info("Surveillance du toit demarree")

    while not stop_event.is_set():
        try:
            dome.sync()
        except Exception:
            log.exception("Erreur pendant la surveillance du toit")

        stop_event.wait(POLL_SECONDS)

    log.info("Surveillance du toit arretee")


def start_monitor(dome, stop_event):
    thread = threading.Thread(
        target=monitor_loop,
        args=(dome, stop_event),
        name="dome-monitor",
        daemon=True,
    )
    thread.start()
    return thread
