import json

from backend.common.paths import (
    CONFIG_DIR
)


SETTINGS_FILE = (
    CONFIG_DIR
    / "settings.json"
)


def load_settings():

    with open(
        SETTINGS_FILE,
        "r",
        encoding="utf-8"
    ) as f:

        return json.load(f)


def save_settings(settings):

    with open(
        SETTINGS_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            settings,
            f,
            indent=2
        )