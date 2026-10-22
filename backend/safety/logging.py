from backend.common.logs import (
    safety_log
)


def log_safe(weather):

    safety_log(
        f"SAFE | "
        f"Temp={weather.temperature}°C | "
        f"Vent={weather.wind} km/h | "
        f"Nuages={weather.clouds}% | "
        f"Pluie={weather.rain_probability}% "
        f"({weather.rain_mm} mm)"
    )


def log_unsafe(
    weather,
    reasons
):

    safety_log(
        f"UNSAFE [{', '.join(reasons)}] | "
        f"Temp={weather.temperature}°C | "
        f"Vent={weather.wind} km/h | "
        f"Nuages={weather.clouds}% | "
        f"Pluie={weather.rain_probability}% "
        f"({weather.rain_mm} mm)"
    )