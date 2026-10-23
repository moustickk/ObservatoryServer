from backend.dome.state import (
    get_state,
    compute_position
)


def get_device_state():

    state = get_state()

    return {
        "state": state["state"],
        "position": compute_position()
    }