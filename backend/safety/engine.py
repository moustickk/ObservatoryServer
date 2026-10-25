from datetime import datetime

from backend.safety.evaluator import (
    evaluate_weather
)

from backend.safety.logging import (
    log_safe,
    log_unsafe
)

from backend.safety.state import (
    state_lock,
    update_cache
)


def process_weather(weather):

    safe, reasons = evaluate_weather(
        weather
    )

    from backend.safety import state

    with state_lock:

        state.weather_data["wind"] = (
            weather["wind"]
        )

        state.weather_data["wind_gust"] = (
            weather.get("wind_gust", 0)
        )

        state.weather_data["clouds"] = (
            weather["clouds"]
        )

        state.weather_data["rain_probability"] = (
            weather["rain_probability"]
        )

        state.weather_data["rain_mm"] = (
            weather["rain_mm"]
        )

        state.weather_data["temperature"] = (
            weather["temperature"]
        )

        state.is_safe = safe

        state.last_weather_update = (
            datetime.now()
        )

        update_cache(weather)

    if safe:

        state.current_status = "SAFE"

        log_safe(weather)

    else:

        state.current_status = (
            f"UNSAFE [{', '.join(reasons)}]"
        )

        log_unsafe(
            weather,
            reasons
        )

    # Une mesure fraiche peut changer le verdict : l'agent ne doit pas
    # attendre le prochain cycle pour agir.
    state.notify_change()

    return safe