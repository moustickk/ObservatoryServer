"""Journalisation applicative (toit, monture, meteo).

Ancienne implementation : chaque ligne relisait tout le fichier, filtrait les
entrees de plus de 48 heures puis reecrivait l'ensemble. Cout O(n) par ligne,
donc O(n^2) sur la duree, et aucune protection contre deux threads qui
ecrivent en meme temps : les deux reecritures se marchaient dessus et des
lignes disparaissaient.

Ici :

 - ecriture en **ajout** : O(1) par ligne, le fichier n'est jamais relu pour
   ecrire ;
 - un **verrou par fichier** : plusieurs threads peuvent journaliser sans se
   perdre de lignes ;
 - la purge des entrees de plus de 48 heures n'a lieu qu'**une fois par
   heure**, par reecriture dans un fichier temporaire puis remplacement. Le
   cout O(n) est amorti sur des milliers d'ecritures.

Les lignes non horodatees (ajoutees a la main, ou venues d'un autre outil)
sont conservees telles quelles : on ne detruit pas des donnees qu'on ne sait
pas dater.
"""

import os
import threading
import time
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]

LOG_DIR = (
    BASE_DIR
    / "data"
    / "logs"
)

LOG_DIR.mkdir(
    parents=True,
    exist_ok=True
)

TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

RETENTION_SECONDS = 48 * 3600

PURGE_INTERVAL_SECONDS = 3600

_locks = {}
_locks_guard = threading.Lock()

_last_purge = {}


def _lock_for(filename):

    with _locks_guard:

        lock = _locks.get(filename)

        if lock is None:

            lock = threading.Lock()

            _locks[filename] = lock

        return lock


def _parse_timestamp(line):

    if not line.startswith("[") or len(line) < 21:

        return None

    try:

        return datetime.strptime(
            line[1:20],
            TIMESTAMP_FORMAT
        )

    except ValueError:

        return None


def _purge(log_file, retention_seconds=RETENTION_SECONDS):
    """Reecrit le fichier sans les lignes trop anciennes. Retourne le nombre
    de lignes conservees (0 si la purge a echoue)."""

    try:

        with open(log_file, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

    except FileNotFoundError:

        return 0

    except OSError:

        return 0

    now = datetime.now()

    kept = []

    for line in lines:

        moment = _parse_timestamp(line)

        if moment is None:

            kept.append(line)

            continue

        if (now - moment).total_seconds() <= retention_seconds:

            kept.append(line)

    tmp = log_file.with_name(log_file.name + ".tmp")

    try:

        with open(tmp, "w", encoding="utf-8") as f:

            f.writelines(kept)

            f.flush()

            os.fsync(f.fileno())

        os.replace(tmp, log_file)

    except OSError:

        # Sur Windows, remplacer un fichier ouvert par un autre processus
        # peut echouer. On reecrit alors sur place : moins atomique, mais la
        # purge est une operation d'entretien, pas une ecriture de securite.
        try:

            tmp.unlink()

        except OSError:

            pass

        try:

            with open(log_file, "w", encoding="utf-8") as f:

                f.writelines(kept)

        except OSError:

            return 0

    return len(kept)


def _purge_if_due(filename, log_file, retention_seconds):

    now = time.monotonic()

    last = _last_purge.get(filename, 0.0)

    if now - last < PURGE_INTERVAL_SECONDS:

        return

    _last_purge[filename] = now

    _purge(log_file, retention_seconds)


def write_log(
    filename,
    message,
    retention_seconds=RETENTION_SECONDS
):

    log_file = LOG_DIR / filename

    # Un message multiligne casserait le format « une ligne = une entree ».
    message = str(message).replace("\r", " ").replace("\n", " | ")

    line = (
        f"[{datetime.now().strftime(TIMESTAMP_FORMAT)}] "
        f"{message}\n"
    )

    with _lock_for(filename):

        with open(log_file, "a", encoding="utf-8") as f:

            f.write(line)

            f.flush()

        _purge_if_due(filename, log_file, retention_seconds)
