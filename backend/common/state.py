import json
import time

from backend.common.paths import (
    STATE_DIR
)


STATE_FILE = (
    STATE_DIR
    / "roof_state.json"
)


def save_state(data):

    with open(
        STATE_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            data,
            f,
            indent=2
        )


def load_state():

    try:

        with open(
            STATE_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            return json.load(f)

    except Exception:

        return {
            "state": "UNKNOWN",
            "position": -1,
            "timestamp": time.time()
        }