"""Persistance de l'etat du toit.

Ecriture atomique : un arret brutal ne peut plus laisser un JSON tronque.
"""

import json
import os
import time

from backend.common.paths import STATE_DIR


STATE_FILE = STATE_DIR / "roof_state.json"


def _default_state():
    return {
        "state": "UNKNOWN",
        "position": -1,
        "timestamp": time.time(),
    }


def save_state(data):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".json.tmp")

    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())

    os.replace(tmp, STATE_FILE)


def load_state():
    try:
        # Meme raison que pour settings.json : un BOM ne doit pas faire
        # passer le toit pour inconnu au demarrage.
        with open(STATE_FILE, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return _default_state()

    if not isinstance(data, dict):
        return _default_state()

    merged = _default_state()
    merged.update(data)
    return merged
