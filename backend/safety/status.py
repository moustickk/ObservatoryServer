from backend.safety import state


def get_status():

    return {
        "safe": state.is_safe,
        "status": state.current_status,
        "weather": state.weather_data,
        "data_age_minutes": (
            state.weather_age_minutes()
        ),
        "last_weather_update": (
            state.last_weather_update.strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            if state.last_weather_update
            else None
        )
    }