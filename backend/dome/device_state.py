
from backend.dome.state import (
    state,
    position
)


def get_device_state():

    return {
        "state": state,
        "position": position
    }