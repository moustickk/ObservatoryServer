"""Localisation et redemarrage du processus d'un driver ASCOM.

Certains drivers (EQMOD notamment) restent bloques apres une perte de la
liaison serie : ils acceptent `Connected = True` mais ne se connectent jamais.
La seule sortie est de terminer leur processus et d'en demarrer un neuf.

Le ProgID et son CLSID ne sont pas toujours dans la meme vue du registre :
EQMOD declare `ProgID\\CLSID` en 64 bits, mais son `LocalServer32` est en
32 bits. On interroge donc les deux vues.
"""

import subprocess
import time

try:
    import winreg
except ImportError:  # pragma: no cover - hors Windows
    winreg = None


VIEWS_READ = ()

if winreg is not None:
    VIEWS_READ = (
        getattr(winreg, "KEY_WOW64_64KEY", 0),
        getattr(winreg, "KEY_WOW64_32KEY", 0),
    )


def parse_server_path(value):
    """Extrait l'executable d'une valeur LocalServer32."""

    value = (value or "").strip()

    if not value:
        return None

    if value.startswith('"'):
        end = value.find('"', 1)
        if end > 0:
            return value[1:end]

    # Chemin non quote, parfois suivi d'arguments : on coupe apres « .exe ».
    index = value.lower().find(".exe")

    if index > 0:
        return value[: index + 4]

    return value.split(" ")[0]


def _default_value(path, view=0):

    try:
        with winreg.OpenKey(
            winreg.HKEY_CLASSES_ROOT,
            path,
            0,
            winreg.KEY_READ | view,
        ) as key:
            value, _ = winreg.QueryValueEx(key, "")
            return value
    except OSError:
        return None


def executable(prog_id):
    """Chemin du serveur local du driver, ou None (driver DLL par exemple)."""

    if winreg is None:  # pragma: no cover - hors Windows
        return None

    clsid = None

    for view in VIEWS_READ:
        clsid = _default_value(f"{prog_id}\\CLSID", view)
        if clsid:
            break

    if not clsid:
        return None

    for view in VIEWS_READ:
        value = _default_value(rf"CLSID\{clsid}\LocalServer32", view)
        if value:
            return parse_server_path(value)

    return None


def restart(prog_id, wait_seconds=2.0):
    """Termine le processus du driver. Retourne True si un nom a ete trouve."""

    path = executable(prog_id)

    if not path:
        return False

    name = path.replace("/", "\\").rsplit("\\", 1)[-1]

    if not name:
        return False

    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    subprocess.run(
        ["taskkill", "/F", "/IM", name],
        capture_output=True,
        creationflags=flags,
    )

    time.sleep(wait_seconds)

    return True
