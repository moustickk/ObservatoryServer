import time
from datetime import datetime

from backend.common.logs import (
    safety_log
)

from backend.safety.config import (
    CACHE_TIMEOUT_MINUTES,
    UPDATE_INTERVAL
)

from backend.safety.state import (
    state_lock,
    is_safe,
    current_status,
    last_good_timestamp,
    last_weather_update
)

from backend.safety.weather_provider import (
    get_weather
)


def weather_monitor():

    safety_log(
        "Weather monitor started"
    )

    while True:

        try:

            data = get_weather()

            safety_log(
                "Weather data received"
            )

            with state_lock:

                globals()["last_weather_update"] = (
                    datetime.now()
                )

                globals()["last_good_timestamp"] = (
                    datetime.now()
                )

        except Exception as