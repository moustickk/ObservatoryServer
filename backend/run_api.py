"""Point d'entree du serveur en developpement.

    .\\.venv\\Scripts\\python.exe -m backend.run_api

Equivalent a `launcher.py --server`. Le port est celui de la configuration
(`server_port`, 11111 par defaut) : c'est aussi le port qu'utilise NINA.
"""

import sys

from backend.server import run_server


if __name__ == "__main__":
    sys.exit(run_server())
