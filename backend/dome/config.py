from backend.common.config import (
    get
)


SERIAL_PORT = get(
    "serial_port",
    "COM4"
)

BAUDRATE = get(
    "baudrate",
    115200
)

FULL_TRAVEL_TIME = get(
    "full_travel_time",
    45
)