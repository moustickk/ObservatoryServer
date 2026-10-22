from backend.common.health import (
    set_status
)


def health_ok():

    set_status(
        "safety",
        "OK"
    )


def health_error():

    set_status(
        "safety",
        "ERROR"
    )
