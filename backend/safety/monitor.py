import time

from backend.safety.config import (
    UPDATE_INTERVAL,
    CACHE_TIMEOUT_MINUTES
)

from backend.safety.weather_provider import (
    get_weather
)

from backend.safety.engine import (
    process_weather
)

from backend.safety.state import (
    cache_valid,
    weather_age_minutes,
    set_safe,
    set_unsafe
)

from backend.common.logs import (
    safety_log
)


def weather_monitor():

    safety_log(
        "Weather monitor started"
    )

    while True:

        try:

            weather = get_weather()
            
            print("Weather receveid:")
            print(weather)
            
            process_weather(
                weather
            )

            print("Weather processed")

        except Exception as ex:

            if cache_valid(
                CACHE_TIMEOUT_MINUTES
            ):

                age = (
                    weather_age_minutes()
                )

                set_safe(
                    f"SAFE | CACHE UTILISE ({age} min)"
                )

                safety_log(
                    f"SAFE | CACHE UTILISE ({age} min)"
                )

            else:

                set_unsafe(
                    f"UNSAFE | {ex}"
                )
                
                print(f"ERROR: {ex}")
                
                safety_log(
                    f"UNSAFE | {ex}"
                )

        time.sleep(
            UPDATE_INTERVAL
        )