"""Decouverte des pilotes ASCOM de monture installes.

On lit le registre plutot que d'utiliser le `Chooser` COM d'ASCOM : celui-ci
ouvre une fenetre sur la session du serveur. Depuis un navigateur, elle serait
invisible, la requete HTTP resterait bloquee, et rien ne garantit qu'un
utilisateur puisse la fermer.

Les pilotes sont declares sous
`HKLM\\SOFTWARE\\ASCOM\\Telescope Drivers` : chaque sous-cle est un ProgID,
et sa valeur par defaut est le nom affiche. On interroge les deux vues du
registre, car un pilote 32 bits n'est pas visible depuis la vue 64 bits (et
inversement).
"""

import logging

try:
    import winreg
except ImportError:  # pragma: no cover - hors Windows
    winreg = None


log = logging.getLogger(__name__)

REGISTRY_PATH = r"SOFTWARE\ASCOM\Telescope Drivers"

VIEWS = (
    "KEY_WOW64_32KEY",
    "KEY_WOW64_64KEY",
)


def _read_view(view_name):

    flags = getattr(winreg, view_name, 0)

    try:
        root = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            REGISTRY_PATH,
            0,
            winreg.KEY_READ | flags,
        )
    except OSError:
        return {}

    found = {}

    with root:
        count = winreg.QueryInfoKey(root)[0]

        for index in range(count):
            try:
                prog_id = winreg.EnumKey(root, index)
            except OSError:
                continue

            name = prog_id

            try:
                with winreg.OpenKey(root, prog_id) as sub:
                    try:
                        name, _ = winreg.QueryValueEx(sub, "")
                    except OSError:
                        pass
            except OSError:
                pass

            found[prog_id] = {
                "prog_id": prog_id,
                "name": str(name) or prog_id,
            }

    return found


def list_drivers():
    """Liste des pilotes de monture, triee par nom affiche."""

    if winreg is None:  # pragma: no cover - hors Windows
        return []

    found = {}

    for view_name in VIEWS:
        for prog_id, driver in _read_view(view_name).items():
            found.setdefault(prog_id, driver)

    return sorted(found.values(), key=lambda driver: driver["name"].lower())
