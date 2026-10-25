"""Demarrage du serveur HTTP, partage entre developpement et executable.

`run_api` (developpement) et `launcher --server` (executable) appellent tous
les deux `run_server()`. Le code de sortie porte une information :

    0   arret normal (l'utilisateur a quitte)
    75  redemarrage demande (le superviseur doit relancer)

Sans cette convention, le superviseur ne saurait pas distinguer un arret
volontaire d'une demande de redemarrage.

Journalisation
--------------
Chaque requete HTTP est journalisee : l'interface interroge `/api/health`
toutes les deux secondes, ce qui produit plusieurs dizaines de milliers de
lignes par jour. Le fichier doit donc tourner, sinon il atteint des gigabytes
en quelques mois. `server.log` est limite a 5 Mo x 5 fichiers (25 Mo au total).

Uvicorn n'a pas de configuration de journalisation propre (`log_config=None`) :
ses messages remontent au logger racine, donc au meme fichier et au meme
formateur. Un seul gestionnaire, donc une seule rotation coherente.
"""

import logging
import sys
from logging.handlers import RotatingFileHandler

import uvicorn

from backend.app import app
from backend.common.constants import LOG_DATE_FORMAT, LOG_FORMAT
from backend.common.paths import LOG_DIR, is_frozen
from backend.common.restart import RESTART_EXIT_CODE, restart_requested
from backend.common.settings_manager import get_int


LOG_MAX_BYTES = 5 * 1024 * 1024

LOG_BACKUPS = 5


def file_handler():
    """Gestionnaire tournant de `server.log` (5 Mo x 5)."""

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    handler = RotatingFileHandler(
        LOG_DIR / "server.log",
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUPS,
        encoding="utf-8",
    )

    handler.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT))

    return handler


def _configure_logging():
    """Console en developpement, fichier tournant dans l'application."""

    if is_frozen():
        handlers = [file_handler()]
    else:
        handlers = [logging.StreamHandler()]

    logging.basicConfig(
        level=logging.INFO,
        format=LOG_FORMAT,
        datefmt=LOG_DATE_FORMAT,
        handlers=handlers,
        force=True,
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
            log_config=None,
        )
    except KeyboardInterrupt:
        pass

    if restart_requested.is_set():
        return RESTART_EXIT_CODE

    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(run_server())
