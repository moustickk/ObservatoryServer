"""Demarrage du serveur HTTP, partage entre developpement et executable.

`run_api` (developpement) et `launcher --server` (executable) appellent tous
les deux `run_server()`. Le code de sortie porte une information :

    0   arret normal (l'utilisateur a quitte)
    75  redemarrage demande (le superviseur doit relancer)

Sans cette convention, le superviseur ne saurait pas distinguer un arret
volontaire d'une demande de redemarrage.
"""

import logging
import sys

import uvicorn

from backend.app import app
from backend.common.restart import RESTART_EXIT_CODE, restart_requested
from backend.common.settings_manager import get_int


def _configure_logging():
    """Journalisation adaptee au mode d'execution.

    Dans l'application empaquetee, `sys.stderr` peut valoir None (pas de
    console) : un StreamHandler leve alors une exception a chaque message.
    """

    handlers = []

    if sys.stderr is not None:
        handlers.append(logging.StreamHandler())
    else:  # pragma: no cover - executable sans console
        from backend.common.paths import LOG_DIR

        LOG_DIR.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(LOG_DIR / "server.log", encoding="utf-8"))

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s | %(message)s",
        datefmt="%H:%M:%S",
        handlers=handlers,
    )


def run_server():

    _configure_logging()

    port = get_int("server_port", 11111)

    logging.getLogger(__name__).info(
        "Demarrage du serveur sur le port %s", port
    )

    try:
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=port,
        )
    except KeyboardInterrupt:
        pass

    if restart_requested.is_set():
        return RESTART_EXIT_CODE

    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(run_server())
