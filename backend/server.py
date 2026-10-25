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
from copy import deepcopy

import uvicorn
from uvicorn.config import LOGGING_CONFIG

from backend.app import app
from backend.common.constants import LOG_ACCESS_FORMAT, LOG_DATE_FORMAT, LOG_FORMAT
from backend.common.restart import RESTART_EXIT_CODE, restart_requested
from backend.common.settings_manager import get_int


def _uvicorn_log_config():
    """Journalisation d'uvicorn au meme format que le reste.

    Par defaut, uvicorn n'horodate pas ses lignes d'acces et n'affiche que
    l'heure pour les autres : dans un fichier, c'est inexploitable.
    """

    config = deepcopy(LOGGING_CONFIG)

    config["formatters"]["default"]["fmt"] = LOG_FORMAT
    config["formatters"]["default"]["datefmt"] = LOG_DATE_FORMAT

    config["formatters"]["access"]["fmt"] = LOG_ACCESS_FORMAT
    config["formatters"]["access"]["datefmt"] = LOG_DATE_FORMAT

    return config


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
        format=LOG_FORMAT,
        datefmt=LOG_DATE_FORMAT,
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
            log_config=_uvicorn_log_config(),
        )
    except KeyboardInterrupt:
        pass

    if restart_requested.is_set():
        return RESTART_EXIT_CODE

    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(run_server())
