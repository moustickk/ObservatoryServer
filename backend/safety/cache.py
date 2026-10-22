from datetime import datetime

from backend.safety.state import (
    last_good_timestamp
)

from backend.safety.config import (
    CACHE_TIMEOUT_MINUTES
)


def cache_valid():

    if last_good_timestamp is None:
        return False

    age = (
        datetime.now()
        - last_good_timestamp
    ).total_seconds() / 60

    return (
        age <= CACHE_TIMEOUT_MINUTES
    )


def cache_age_minutes():

    if last_good_timestamp is None:
        return -1

    return int(
        (
            datetime.now()
            - last_good_timestamp
        ).total_seconds() / 60
    )