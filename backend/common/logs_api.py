"""Lecture des journaux applicatifs pour l'interface.

Trois precisions :

- seuls des noms connus sont acceptes : un nom libre permettrait de lire
  n'importe quel fichier de la machine (`..\\..\\Windows\\...`) ;
- on ne renvoie que la **fin** du fichier, et jamais plus de `MAX_BYTES` :
  `server.log` peut grossir sans limite utile, le navigateur n'a pas besoin
  de tout ;
- la lecture se fait a l'envers par blocs, sans charger le fichier entier en
  memoire.
"""

import os
from datetime import datetime


from backend.common.paths import LOG_DIR


KNOWN_LOGS = (
    "server.log",
    "tray.log",
    "roof.log",
    "meteo_log.txt",
)

DEFAULT_LINES = 200

MAX_LINES = 2000

MAX_BYTES = 512 * 1024

BLOCK_BYTES = 16 * 1024


class UnknownLog(KeyError):
    pass


def _resolve(name):

    if name not in KNOWN_LOGS:
        raise UnknownLog(name)

    return LOG_DIR / name


def list_logs():

    entries = []

    for name in KNOWN_LOGS:

        path = LOG_DIR / name

        try:
            stat = path.stat()
        except OSError:
            entries.append({"name": name, "exists": False, "size": 0, "modified": None})
            continue

        entries.append({
            "name": name,
            "exists": True,
            "size": stat.st_size,
            "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
        })

    return entries


def tail_log(name, lines=DEFAULT_LINES):
    """Retourne (lignes, taille_totale, tronque)."""

    path = _resolve(name)

    try:
        size = path.stat().st_size
    except OSError:
        return [], 0, False

    try:
        lines = max(1, min(int(lines), MAX_LINES))
    except (TypeError, ValueError):
        lines = DEFAULT_LINES

    with open(path, "rb") as handle:

        handle.seek(0, os.SEEK_END)
        position = handle.tell()

        data = b""
        block = BLOCK_BYTES

        while position > 0 and data.count(b"\n") <= lines and len(data) < MAX_BYTES:

            read = min(block, position, MAX_BYTES - len(data))

            if read <= 0:
                break

            position -= read

            handle.seek(position)
            data = handle.read(read) + data

    text = data.decode("utf-8", errors="replace")

    return text.splitlines()[-lines:], size, position > 0
