from backend.dome.service import (
    DomeService
)

from backend.dome.state import (
    state_data,
    save_current_state,
    compute_position
)

from backend.dome.logging import (
    log_state
)


dome = DomeService()


def sync_state():

    try:

        arduino_state = dome.status()

        log_state(
            f"Arduino returned: '{arduino_state}'"
        )

        if arduino_state == "OPENED":

            state_data["state"] = (
                "OPENED"
            )

            state_data["position"] = 100

        elif arduino_state == "CLOSED":

            state_data["state"] = (
                "CLOSED"
            )

            state_data["position"] = 0

        elif arduino_state == "STOPPED":

            state_data["position"] = (
                compute_position()
            )

        elif arduino_state == "ERROR":

            state_data["position"] = (
                compute_position()
            )

            state_data["state"] = (
                "ERROR"
            )

        elif arduino_state == "UNKNOWN":

            state_data["state"] = (
                "UNKNOWN"
            )

        elif arduino_state == "OPENING":

            state_data["state"] = (
                "OPENING"
            )

        elif arduino_state == "CLOSING":

            state_data["state"] = (
                "CLOSING"
            )

        save_current_state()

        return arduino_state

    except Exception as ex:

        log_state(
            f"Exception: {ex}"
        )

        return "ERROR"
