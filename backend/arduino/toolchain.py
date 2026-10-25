"""Acces a `arduino-cli` : detection, compilation, televersement.

`arduino-cli` est fourni avec l'IDE Arduino 2.x, mais il peut aussi etre
installe seul. On le cherche dans cet ordre : reglage explicite, variable
d'environnement, emplacements connus de l'IDE, puis PATH.

Toutes les executions se font sans fenetre (`CREATE_NO_WINDOW`) et avec une
sortie texte : l'atelier l'affiche dans l'interface.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


CANDIDATES = (
    r"%LOCALAPPDATA%\Programs\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe",
    r"%PROGRAMFILES%\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe",
    r"%PROGRAMFILES(X86)%\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe",
    r"C:\Program Files\Arduino\arduino-cli.exe",
    r"C:\Program Files (x86)\Arduino\arduino-cli.exe",
)

ENV_VAR = "ARDUINO_CLI"

DEFAULT_TIMEOUT = 300


class ToolchainError(Exception):
    pass


def find_cli(settings=None):
    """Chemin d'arduino-cli, ou None s'il est introuvable."""

    settings = settings or {}

    explicit = str(settings.get("arduino_cli_path") or "").strip()

    if explicit:
        path = Path(os.path.expandvars(explicit))
        return path if path.is_file() else None

    from_env = os.environ.get(ENV_VAR)

    if from_env and Path(from_env).is_file():
        return Path(from_env)

    for candidate in CANDIDATES:
        path = Path(os.path.expandvars(candidate))
        if path.is_file():
            return path

    found = shutil.which("arduino-cli")

    return Path(found) if found else None


def run(cli, args, timeout=DEFAULT_TIMEOUT):
    """Execute arduino-cli. Retourne (code, sortie)."""

    command = [str(cli)] + [str(arg) for arg in args]

    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=flags,
        )
    except FileNotFoundError as ex:
        raise ToolchainError(f"arduino-cli introuvable : {cli}") from ex
    except subprocess.TimeoutExpired as ex:
        raise ToolchainError(
            f"arduino-cli n'a pas repondu en {timeout} s"
        ) from ex

    output = (completed.stdout or "") + (completed.stderr or "")

    return completed.returncode, output.strip()


def version(cli):

    code, output = run(cli, ["version"], timeout=30)

    if code != 0:
        return None

    for line in output.splitlines():
        if "Version:" in line:
            return line.split("Version:", 1)[1].strip().split()[0]

    return output.splitlines()[0].strip() if output else None


def cores(cli):
    """Plateformes installees (identifiant, version, nom)."""

    code, output = run(cli, ["core", "list"], timeout=60)

    if code != 0:
        return []

    result = []

    for line in output.splitlines()[1:]:

        parts = line.split()

        if len(parts) < 2 or ":" not in parts[0]:
            continue

        result.append({
            "id": parts[0],
            "installed": parts[1],
            "name": " ".join(parts[3:]) if len(parts) > 3 else "",
        })

    return result


def ports(cli):
    """Ports serie detectes par arduino-cli."""

    code, output = run(cli, ["board", "list", "--format", "json"], timeout=60)

    if code != 0:
        return []

    try:
        data = json.loads(output)
    except ValueError:
        return []

    result = []

    for entry in data.get("detected_ports") or []:

        port = entry.get("port") or {}
        address = port.get("address")

        if not address:
            continue

        boards = entry.get("matching_boards") or []
        board = boards[0].get("name") if boards else None

        result.append({
            "address": address,
            "label": port.get("label") or address,
            "protocol": port.get("protocol_label") or port.get("protocol"),
            "board": board,
        })

    return result


def has_core(cli, fqbn):
    """Verifie que le noyau demande par le FQBN est installe."""

    if ":" not in fqbn:
        return False

    package = ":".join(fqbn.split(":")[:2])

    return any(core["id"] == package for core in cores(cli))


def python_platform():  # pragma: no cover - information seule
    return sys.platform
