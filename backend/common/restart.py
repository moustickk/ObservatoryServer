"""Redemarrage du serveur, sans intervention de l'operateur.

Un reglage modifie ne s'applique qu'au redemarrage : les modules metier lisent
la configuration a l'import (seuils meteo, port serie, driver ASCOM...). Ce
module permet a l'interface web de proposer le redemarrage au lieu de laisser
l'utilisateur chercher une fenetre de console.

Mecanisme :

1. on lance un petit processus **detache** dont le seul role est d'attendre
   que le port soit libre, puis de relancer `backend.run_api` ;
2. on demande au serveur courant de s'arreter proprement (SIGINT, donc
   lifespan et fermeture du port serie) ;
3. si l'arret gracieux traine, une sortie forcee intervient au bout de
   quelques secondes.

Pourquoi un processus intermediaire : le nouveau serveur ne peut pas se lier
au port tant que l'ancien le tient. Le detachement lui permet de survivre a
la mort du processus courant.

Limite : ce mecanisme suppose un lancement par `python -m backend.run_api`.
L'executable empaquete (phase 9) devra etre relance par la tray app, qui est
deja un superviseur naturel.
"""

import logging
import os
import signal
import subprocess
import sys
import threading

from backend.common.paths import APP_DIR, LOG_DIR


log = logging.getLogger(__name__)

RESTART_DELAY_SECONDS = 0.7

FORCE_EXIT_SECONDS = 6.0

PORT_WAIT_SECONDS = 30.0


_RESTARTER = r"""
import socket
import subprocess
import sys
import time

port = int(sys.argv[1])
root = sys.argv[2]
deadline = time.time() + float(sys.argv[3])
log_path = sys.argv[4]
parent = int(sys.argv[5])

# 1. Attendre la FIN du processus courant, pas seulement la liberation du
#    port HTTP. Pendant son arret, uvicorn cesse d'ecouter avant que le
#    lifespan n'ait ferme le port serie : demarrer a ce moment-la donne un
#    PermissionError sur COM4 et un serveur sans toit.
try:
    import ctypes

    SYNCHRONIZE = 0x00100000
    handle = ctypes.windll.kernel32.OpenProcess(SYNCHRONIZE, False, parent)
    if handle:
        ctypes.windll.kernel32.WaitForSingleObject(handle, 20000)
        ctypes.windll.kernel32.CloseHandle(handle)
except Exception:
    pass

# 2. Verifier malgre tout que le port est libre.
while time.time() < deadline:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        # Volontairement sans SO_REUSEADDR : sous Windows, cette option
        # permettrait de se lier a un port encore ecoute.
        sock.bind(("127.0.0.1", port))
    except OSError:
        sock.close()
        time.sleep(0.2)
        continue

    sock.close()
    break
else:
    sys.exit(1)

time.sleep(0.5)

# Le nouveau serveur n'a pas de console : on conserve sa sortie dans un
# fichier, sinon tout diagnostic serait perdu apres un redemarrage.
with open(log_path, "a", encoding="utf-8", buffering=1) as output:
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    subprocess.Popen(
        [sys.executable, "-m", "backend.run_api"],
        cwd=root,
        stdout=output,
        stderr=subprocess.STDOUT,
        creationflags=flags,
    )
"""


def restarter_source():
    """Source du processus intermediaire (utile aux tests)."""

    return _RESTARTER


def _spawn_restarter(port, wait_seconds=PORT_WAIT_SECONDS):

    flags = 0

    if os.name == "nt":
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP

    return subprocess.Popen(
        [
            sys.executable,
            "-c",
            _RESTARTER,
            str(int(port)),
            str(APP_DIR),
            str(float(wait_seconds)),
            str(LOG_DIR / "server.log"),
            str(os.getpid()),
        ],
        cwd=str(APP_DIR),
        creationflags=flags,
        close_fds=True,
    )


def _shutdown():

    try:
        signal.raise_signal(signal.SIGINT)
    except Exception:
        log.exception("Signal d'arret impossible : sortie forcee")
        _force_exit()


def _force_exit():

    logging.shutdown()
    os._exit(0)


def schedule_restart(port, delay=RESTART_DELAY_SECONDS):
    """Programme l'arret gracieux puis la relance. Retourne immediatement."""

    log.warning("Redemarrage du serveur demande (port %s)", port)

    _spawn_restarter(port)

    graceful = threading.Timer(delay, _shutdown)
    graceful.daemon = True
    graceful.start()

    forced = threading.Timer(delay + FORCE_EXIT_SECONDS, _force_exit)
    forced.daemon = True
    forced.start()
