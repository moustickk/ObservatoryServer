from backend.common.logs import (
    dome_log
)


def roof_opening():

    dome_log(
        "Roof opening"
    )


def roof_opened():

    dome_log(
        "Roof opened"
    )


def roof_closing():

    dome_log(
        "Roof closing"
    )


def roof_closed():

    dome_log(
        "Roof closed"
    )


def roof_error(message):

    dome_log(
        f"Roof error: {message}"
    )