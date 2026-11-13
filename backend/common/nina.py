"""Demarrage automatique de NINA apres le serveur du toit.

Le superviseur (icone de notification) attend que l'API du toit reponde,
puis lance NINA. Le lancement est fait une seule fois par demarrage du
superviseur : si NINA est deja ouvert, on ne cree pas de second processus.

Le chemin est detecte dans Program Files ; il peut etre force dans les
reglages (utile pour une installation dans un autre dossier).
"""

import logging
import os
import subprocess
import time
import urllib.request

from pathlib import Path

from backend.common.settings_manager import get, get_bool


log = logging.getLogger(__name__)

READY_TIMEOUT_SECONDS = 120.0

# Laisse aux services Alpaca le temps de finir de s'initialiser avant que
# NINA ne commence a interroger les devices.
LAUNCH_DELAY_SECONDS = 5.0

EXE_NAMES = ("NINA.exe", "N.I.N.A.exe")

FOLDER_NAMES = (
    "N.I.N.A. - Nighttime Imaging 'N' Astronomy",
    "N.I.N.A.",
    "NINA",
)


def _roots():
    """Dossiers ou NINA peut etre installe."""

    result = []

    for variable in ("ProgramFiles", "ProgramFiles(x86)"):

        value = os.environ.get(variable)

        if value:
            result.append(Path(value))

    local = os.environ.get("LOCALAPPDATA")

    if local:
        result.append(Path(local) / "Programs")

    return result


def candidate_paths():
    """Chemins essayes, du plus explicite au plus general."""

    configured = str(get("nina_path", "") or "").strip()

    if configured:
        yield Path(configured)

    for root in _roots():

        for folder in FOLDER_NAMES:

            for exe in EXE_NAMES:
                yield root / folder / exe

        try:
            entries = list(root.iterdir())
        except OSError:
            continue

        for entry in entries:

            if not entry.is_dir():
                continue

            name = entry.name.upper()

            if "N.I.N.A" not in name and "NIGHTTIME" not in name and name != "NINA":
                continue

            for exe in EXE_NAMES:
                yield entry / exe


def detect_path():
    """Retourne le chemin de NINA.exe, ou None."""

    for path in candidate_paths():

        try:
            if path.is_file():
                return str(path)
        except OSError:
            continue

    return None


def is_running():
    """Vrai si un processus NINA est deja present."""

    try:

        result = subprocess.run(
            ["tasklist", "/FO", "CSV", "/NH"],
            capture_output=True,
            timeout=5,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

        # Pas de decodage : la sortie de tasklist est en OEM (cp850/cp1252),
        # et un nom de processus accentue fait echouer un decodage UTF-8.
        output = (result.stdout or b"").lower()

        return any(name.lower().encode() in output for name in EXE_NAMES)

    except Exception:
        return False


def launch(path=None):
    """Lance NINA si necessaire. Retourne True si un processus a ete cree."""

    path = path or detect_path()

    if not path:

        log.warning(
            "NINA introuvable : renseigner le chemin dans "
            "l'onglet Systeme, sinon le demarrage automatique est inactif"
        )
        return False

    if is_running():

        log.info("NINA est deja en cours : pas de second lancement")
        return False

    try:

        subprocess.Popen(
            [path],
            cwd=str(Path(path).parent),
            close_fds=True,
        )

    except OSError as ex:

        log.error("Lancement de NINA impossible (%s) : %s", path, ex)
        return False

    log.info("NINA lance : %s", path)
    return True


def server_ready(port, timeout=READY_TIMEOUT_SECONDS):
    """Attend que l'API du toit reponde sur la machine locale."""

    url = f"http://127.0.0.1:{port}/api/health"

    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:

        try:

            with urllib.request.urlopen(url, timeout=2.0) as response:

                if response.status == 200:
                    return True

        except Exception:
            pass

        time.sleep(1.0)

    return False


def autostart(port):
    """Point d'entree du thread lance par le superviseur."""

    if not get_bool("nina_autostart", False):

        log.info("Demarrage automatique de NINA desactive")
        return False

    if not server_ready(port):

        log.warning(
            "Serveur du toit injoignable apres %.0f s : NINA non lance",
            READY_TIMEOUT_SECONDS,
        )
        return False

    time.sleep(LAUNCH_DELAY_SECONDS)

    return launch()
