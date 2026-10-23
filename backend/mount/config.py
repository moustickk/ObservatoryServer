from backend.common.config import (
    get
)


TELESCOPE_DRIVER = get(
    "telescope_driver",
    "EQMOD_SIM.Telescope"
)

PARK_TIMEOUT = get(
    "park_timeout",
    300
)