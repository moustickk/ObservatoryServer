from backend.safety.state import (
    weather_data,
    is_safe,
    current_status,
    last_weather_update
)


def get_status():

    return {
        "safe": is_safe,
        "status": current_status,
        "weather": weather_data,
        "last_weather_update": (
            str(last_weather_update)
            if last_weather_update
            else None
        )
    }