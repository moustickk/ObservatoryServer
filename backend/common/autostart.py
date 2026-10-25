"""Demarrage automatique a l'ouverture de session Windows.

L'application est une icone de notification, pas un service : elle doit
tourner dans la session de l'utilisateur pour acceder a COM et ASCOM. Le
mecanisme est donc un raccourci dans le dossier « Demarrage », que l'interface
peut activer ou desactiver.

Le raccourci est ecrit par `WScript.Shell` (COM). L'operation dure quelques
millisecondes, mais elle est executee dans un thread court pour ne pas faire
d'appel COM dans le thread d'une requete HTTP.
"""

import os
import sys
import threading
from pathlib import Path

from backend.common.paths import APP_DIR, is_frozen


SHORTCUT_NAME = "ObservatoryServer.lnk"

DESCRIPTION = "ObservatoryServer - toit roulant"


def startup_dir():

    appdata = os.environ.get("APPDATA")

    if not appdata:
        appdata = str(Path.home() / "AppData" / "Roaming")

    return (
        Path(appdata)
        / "Microsoft"
        / "Windows"
        / "Start Menu"
        / "Programs"
        / "Startup"
    )


def shortcut_path():
    return startup_dir() / SHORTCUT_NAME


def target():
    """Executable et arguments du raccourci, selon le mode d'execution."""

    if is_frozen():
        return sys.executable, ""

    return sys.executable, f'"{APP_DIR / "launcher.py"}"'


def is_enabled():
    return shortcut_path().is_file()


def _write_shortcut(path):

    import pythoncom
    import win32com.client

    executable, arguments = target()

    pythoncom.CoInitialize()

    shell = None
    shortcut = None

    try:
        # DispatchEx : instance dediee, sans passer par la table des objets
        # en cours. Les references sont explicitement relachees AVANT
        # CoUninitialize : liberer un objet COM apres la fermeture de
        # l'appartement provoque une violation d'acces.
        shell = win32com.client.DispatchEx("WScript.Shell")
        shortcut = shell.CreateShortCut(str(path))

        shortcut.TargetPath = executable
        shortcut.Arguments = arguments
        shortcut.WorkingDirectory = str(APP_DIR)
        shortcut.IconLocation = str(APP_DIR / "assets" / "observatory.ico")
        shortcut.Description = DESCRIPTION

        shortcut.Save()

    finally:
        shortcut = None
        shell = None
        pythoncom.CoUninitialize()


def set_enabled(enabled):
    """Cree ou supprime le raccourci. Retourne l'etat final."""

    path = shortcut_path()

    if enabled:
        path.parent.mkdir(parents=True, exist_ok=True)
        _write_shortcut(path)
    else:
        try:
            path.unlink()
        except FileNotFoundError:
            pass

    return is_enabled()


def set_enabled_threaded(enabled, timeout=10.0):
    """Comme `set_enabled`, mais hors du thread appelant (COM)."""

    result = {}

    def worker():
        try:
            result["value"] = set_enabled(enabled)
        except Exception as ex:  # remonte a l'appelant
            result["error"] = ex

    thread = threading.Thread(target=worker, name="autostart", daemon=True)
    thread.start()
    thread.join(timeout)

    if "error" in result:
        raise result["error"]

    if "value" not in result:
        raise RuntimeError("delai depasse pendant la mise a jour du raccourci")

    return result["value"]
