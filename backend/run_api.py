"""Point d'entree du serveur.

A lancer depuis la racine du projet :

    .\\.venv\\Scripts\\python.exe -m backend.run_api

Le port est celui de la configuration (`server_port`, 11111 par defaut) :
c'est aussi le port que NINA utilisera pour Alpaca.
"""

import logging

import uvicorn

from backend.app import app
from backend.common.settings_manager import get_int


if __name__ == "__main__":

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )

    port = get_int("server_port", 11111)

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
    )
