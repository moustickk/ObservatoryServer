from backend.common.health import (
    set_status
)


def health_ok():

    set_status(
        "dome",
        "OK"
    )


def health_error():

    set_status(
        "dome",
        "ERROR"
    )