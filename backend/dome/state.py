import time

from backend.common.state import (
    load_state,
    save_state
)

from backend.dome.config import (
    FULL_TRAVEL_TIME
)


state_data = load_state()


def get_state():

    return state_data


def save_current_state():

    save_state(
        state_data
    )


def initialize_state():

    if "state" not in state_data:

        state_data["state"] = (
            "UNKNOWN"
        )

    if "position" not in state_data:

        state_data["position"] = -1

    if "timestamp" not in state_data:

        state_data["timestamp"] = (
            time.time()
        )


def compute_position():

    state = state_data["state"]

    if state == "OPENED":

        return 100

    if state == "CLOSED":

        return 0

    if state not in [
        "OPENING",
        "CLOSING"
    ]:

        return state_data["position"]

    elapsed = (
        time.time()
        - state_data["timestamp"]
    )

    delta = (
        elapsed /
        FULL_TRAVEL_TIME
    ) * 100

    start = state_data["position"]

    if state == "OPENING":

        return min(
            100,
            int(start + delta)
        )

    return max(
        0,
        int(start - delta)
    )