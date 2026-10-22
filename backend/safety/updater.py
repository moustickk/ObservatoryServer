from datetime import datetime

from backend.safety.state import (
    state_lock,
    last_weather_update,
    last_good_timestamp,
    last_good_data,
    current_status,
    is_safe
)


def update_success(data):

    with state_lock:

        globals()["last_weather_update"] = (
            datetime.now()
        )

        globals()["last_good_timestamp"] = (
            datetime.now()
        )

        globals()["last_good_data"] = (
            data
        )


def update_status(
    safe,
    status
):

    with state_lock:

        globals()["is_safe"] = safe

        globals()["current_status"] = status