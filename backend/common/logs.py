from backend.common.logger import (
    write_log
)


def dome_log(message):

    write_log(
        "roof.log",
        message
    )


def safety_log(message):

    write_log(
        "meteo_log.txt",
        message
    )