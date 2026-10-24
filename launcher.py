"""Point d'entree de l'application installee.

    ObservatoryServer.exe            -> icone de notification (superviseur)
    ObservatoryServer.exe --server   -> le serveur lui-meme

En developpement, le meme fichier sert :

    .\\.venv\\Scripts\\python.exe launcher.py

La separation est volontaire : le serveur ne doit jamais etre un service
Windows (l'acces COM/ASCOM exige la session de l'utilisateur), et le
superviseur doit pouvoir relancer le serveur sans perdre l'icone.
"""

import sys


def main():
    if "--server" in sys.argv[1:]:
        from backend.server import run_server

        return run_server()

    from backend.tray import run_tray

    return run_tray()


if __name__ == "__main__":
    sys.exit(main())
