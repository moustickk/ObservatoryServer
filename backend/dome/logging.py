from backend.common.logs import (
    dome_log
)


def log_open():

    dome_log(
        "OPEN command"
    )


def log_close():

    dome_log(
        "CLOSE command"
    )


def log_stop():

    dome_log(
        "STOP command"
    )


def log_state(state):

    dome_log(
        f"STATE={state}"
    )