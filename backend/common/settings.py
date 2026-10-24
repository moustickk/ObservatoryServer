import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]

SETTINGS_FILE = (
    BASE_DIR
    / "data"
    / "config"
    / "settings.json"
)


def load_settings():

    with open(
        SETTINGS_FILE,
        "r",
        encoding="utf-8"
    ) as f:

        return json.load(f)


settings = load_settings()