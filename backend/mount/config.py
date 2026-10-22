from backend.common.config import (
    get
)


TELESCOPE_DRIVER = get(
    "telescope_driver",
    "EQMOD.Telescope"
)

PARK_TIMEOUT = get(
    "park_timeout",
    300
)