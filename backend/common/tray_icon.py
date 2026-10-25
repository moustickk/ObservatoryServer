"""Visibilite de l'icone dans la zone de notification.

Windows 10/11 cache par defaut les nouvelles icones dans la zone repliee
(le chevron). Il n'existe pas d'API documentee pour forcer l'affichage : le
choix est stocke **par icone** dans

    HKCU\\Control Panel\\NotifyIconSettings\\<identifiant>

sous forme d'une valeur `IsPromoted` (1 = affichee dans la barre, 0 = repliee),
accompagnee du chemin de l'executable.

On lit donc ces entrees pour connaitre l'etat reel, et on ecrit `IsPromoted`
quand l'utilisateur demande l'affichage. Deux limites a connaitre :

- l'entree n'existe qu'apres que Windows a vu l'icone au moins une fois ;
- le changement peut n'etre pris en compte qu'a la prochaine ouverture de
  session (voire apres redemarrage de l'Explorateur).

Le chemin stocke peut commencer par un GUID de dossier connu
(`{6D809377-...}\\...` pour Program Files) : on le developpe avant comparaison.
"""

import ctypes
import sys
from ctypes import wintypes
from pathlib import Path

try:
    import winreg
except ImportError:  # pragma: no cover - hors Windows
    winreg = None


from backend.common.paths import is_frozen


SETTINGS_KEY = r"Control Panel\NotifyIconSettings"

VALUE_NAME = "IsPromoted"


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]


def _guid(value):

    text = value.strip("{}")

    try:
        parts = text.split("-")
        # Le dernier groupe du GUID fait 12 caracteres hexa, soit 6 octets :
        # Data4 en compte 8, les deux premiers venant du groupe precedent.
        data4 = bytes.fromhex(parts[3]) + bytes.fromhex(parts[4])
        return GUID(
            int(parts[0], 16),
            int(parts[1], 16),
            int(parts[2], 16),
            (ctypes.c_ubyte * 8)(*data4),
        )
    except (IndexError, ValueError):
        return None


def known_folder(value):
    """Chemin d'un dossier connu a partir de son GUID, ou None."""

    identifier = _guid(value)

    if identifier is None:
        return None

    pointer = ctypes.c_wchar_p()

    result = ctypes.windll.shell32.SHGetKnownFolderPath(
        ctypes.byref(identifier),
        0,
        None,
        ctypes.byref(pointer),
    )

    if result != 0:
        return None

    try:
        return pointer.value
    finally:
        ctypes.windll.ole32.CoTaskMemFree(pointer)


def expand_path(stored):
    """Developpe un chemin eventuellement prefixe par un GUID de dossier."""

    if not stored:
        return None

    if stored.startswith("{"):
        separator = stored.find("}")

        if separator > 0:
            base = known_folder(stored[: separator + 1])

            if base:
                return str(Path(base) / stored[separator + 2 :])

    return stored


def matches(stored, executable):
    """Vrai si l'entree designe cet executable."""

    expanded = expand_path(stored)

    if not expanded:
        return False

    try:
        return Path(expanded).resolve() == Path(executable).resolve()
    except OSError:
        return False


def executable():
    return sys.executable


def supported():
    """L'operation n'a de sens que dans l'application installee."""

    return is_frozen()


def entries():
    """Entrees du registre concernant cet executable."""

    if winreg is None:  # pragma: no cover - hors Windows
        return []

    result = []

    try:
        root = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            SETTINGS_KEY,
            0,
            winreg.KEY_READ,
        )
    except OSError:
        return []

    with root:
        count = winreg.QueryInfoKey(root)[0]

        for index in range(count):
            try:
                name = winreg.EnumKey(root, index)
            except OSError:
                continue

            try:
                with winreg.OpenKey(root, name) as sub:
                    stored, _ = winreg.QueryValueEx(sub, "ExecutablePath")
                    promoted, _ = winreg.QueryValueEx(sub, "IsPromoted")
            except OSError:
                continue

            if matches(stored, executable()):
                result.append({
                    "key": name,
                    "path": expand_path(stored),
                    "promoted": int(promoted) == 1,
                })

    return result


def status():

    if not supported():
        return {
            "supported": False,
            "known": False,
            "promoted": False,
            "reason": "disponible dans l'application installée",
        }

    found = entries()

    return {
        "supported": True,
        "known": bool(found),
        "promoted": any(entry["promoted"] for entry in found),
        "reason": None if found else "Windows n'a pas encore enregistré l'icône",
    }


def set_promoted(enabled):
    """Ecrit IsPromoted sur les entrees de cet executable."""

    if winreg is None or not supported():  # pragma: no cover
        return status()

    value = 1 if enabled else 0

    for entry in entries():
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                f"{SETTINGS_KEY}\\{entry['key']}",
                0,
                winreg.KEY_SET_VALUE,
            ) as key:
                winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_DWORD, value)
        except OSError:
            continue

    return status()
