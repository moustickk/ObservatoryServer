from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]

DATA_DIR = (
    BASE_DIR
    / "data"
)

CONFIG_DIR = (
    DATA_DIR
    / "config"
)

LOG_DIR = (
    DATA_DIR
    / "logs"
)

STATE_DIR = (
    DATA_DIR
    / "state"
)

CONFIG_DIR.mkdir(
    parents=True,
    exist_ok=True
)

LOG_DIR.mkdir(
    parents=True,
    exist_ok=True
)

STATE_DIR.mkdir(
    parents=True,
    exist_ok=True
)
