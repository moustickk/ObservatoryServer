from backend.common.logs import (
    safety_log
)


def cache_expired(age):

    safety_log(
        f"UNSAFE | Cache expiré ({age} min)"
    )


def cache_valid(age):

    safety_log(
        f"SAFE | Cache utilisé ({age} min)"
    )