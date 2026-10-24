"""Chemins de donnees, compatibles developpement et installation.

Trois cas, dans cet ordre :

1. `OBSERVATORY_DATA_DIR` est defini : il fait foi. Utile pour les tests, une
   installation portable, ou deux instances sur la meme machine.
2. L'application tourne depuis un executable (PyInstaller, `sys.frozen`) :
   le code est dans un dossier temporaire en lecture seule, et le dossier
   d'installation n'est pas forcement inscriptible. Les donnees vont donc
   dans `%ProgramData%\\ObservatoryServer`, comme le veut Windows.
3. Sinon (developpement) : `<projet>/data`, pour que rien ne sorte du depot.

Tous les modules doivent importer ces chemins plutot que de recalculer
`__file__.parents[...]` : c'est ce qui garantit qu'une installation ne
finira pas par ecrire dans le dossier du programme.
"""

import os
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[2]

DATA_DIR_NAME = "ObservatoryServer"

OVERRIDE_ENV = "OBSERVATORY_DATA_DIR"


def is_frozen():
    """True si l'on tourne depuis un executable empaquete."""

    return bool(getattr(sys, "frozen", False))


def default_data_dir():
    """Dossier de donnees, selon le mode d'execution."""

    override = os.environ.get(OVERRIDE_ENV)

    if override:
        return Path(override).expanduser()

    if is_frozen():
        base = os.environ.get("PROGRAMDATA") or r"C:\ProgramData"
        return Path(base) / DATA_DIR_NAME

    return APP_DIR / "data"


DATA_DIR = default_data_dir()

CONFIG_DIR = DATA_DIR / "config"

LOG_DIR = DATA_DIR / "logs"

STATE_DIR = DATA_DIR / "state"


def ensure_dirs():
    """Cree l'arborescence de donnees (idempotent)."""

    for directory in (CONFIG_DIR, LOG_DIR, STATE_DIR):
        directory.mkdir(parents=True, exist_ok=True)


ensure_dirs()
