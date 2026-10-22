from backend.common.logs import (
    safety_log
)


def weather_received():

    safety_log(
        "Weather data received"
    )


def weather_error(message):

    safety_log(
        f"Weather error: {message}"
    )


def cache_used(age):

    safety_log(
        f"SAFE | CACHE UTILISE ({age} min)"
    )